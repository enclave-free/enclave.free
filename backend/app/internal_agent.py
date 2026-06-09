"""
Private Enclave Control Plane endpoints for the Sage Agent Runtime.

These endpoints are intentionally not exposed through the public gateway.
They let Sage reuse Enclave Control Plane facts and actions such as auth
hydration, Document Access, User Profile context, Retrieval, and safe admin DB
reads without reimplementing those product rules in Rust.
"""

import os
import re
import time
import logging
from typing import Optional, Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

import database
import ingest_db
from query import _build_context, _build_search_query, _process_search_results
from scoped_config_context import (
    ScopedConfigAuthorizationError,
    ScopedConfigMode,
    ScopedConfigScope,
    build_scoped_config_context,
)
from sql_safety import validate_sql_allowed_tables
from store import embed_texts, COLLECTION_NAME, QDRANT_HOST, QDRANT_PORT

logger = logging.getLogger("enclave.internal_agent")

router = APIRouter(prefix="/internal/agent", tags=["internal-agent"])

INTERNAL_AGENT_TOKEN = os.getenv("INTERNAL_AGENT_TOKEN", "").strip()
DOCUMENT_OVERVIEW_OPENING_CHUNKS_PER_DOCUMENT = 2
MAX_OVERVIEW_DOCS = 5
DEFAULT_RESOURCE_SEARCH_LIMIT = 5
MAX_RESOURCE_SEARCH_LIMIT = 25
READ_ONLY_SELECT_FORBIDDEN_KEYWORDS = (
    "ALTER",
    "ATTACH",
    "CREATE",
    "DELETE",
    "DETACH",
    "DROP",
    "INSERT",
    "PRAGMA",
    "REPLACE",
    "TRUNCATE",
    "UPDATE",
    "VACUUM",
)


class InternalActorContext(BaseModel):
    id: int
    type: Literal["admin", "user"]
    approved: bool = True
    pubkey: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    user_type_id: Optional[int] = None
    dev_mode: bool = False


class InternalDocumentSearchRequest(BaseModel):
    query: str
    user: InternalActorContext
    top_k: int = 8
    job_ids: Optional[list[str]] = None
    jurisdiction: Optional[str] = None
    situation_details: Optional[str] = None


class InternalDocumentSearchResponse(BaseModel):
    sources: list[dict]
    context: str
    search_query: str
    top_k: int


class InternalResourceSearchRequest(BaseModel):
    help_type: str
    jurisdiction: Optional[str] = None
    language: Optional[str] = None
    limit: int = 5


class InternalResourceSearchResponse(BaseModel):
    resources: list[dict]
    resolved_country_code: Optional[str] = None
    help_type: str


class InternalAdminDbQueryRequest(BaseModel):
    sql: str


class InternalScopedConfigContextRequest(BaseModel):
    query: str
    actor: InternalActorContext
    mode: ScopedConfigMode = "auto"
    requested_scopes: Optional[list[ScopedConfigScope]] = None


class InternalScopedConfigContextSection(BaseModel):
    scope: str
    title: str
    content: str
    fields: list[dict[str, str]] = []


class InternalScopedConfigSecretPolicy(BaseModel):
    mode: Literal["masked"] = "masked"


class InternalScopedConfigContextResponse(BaseModel):
    version: int
    primary_scope: ScopedConfigScope
    included_scopes: list[ScopedConfigScope]
    context_text: str
    sections: list[InternalScopedConfigContextSection]
    warnings: list[str]
    generated_at: str
    secret_policy: InternalScopedConfigSecretPolicy


class InternalUserRecordResponse(BaseModel):
    id: int
    type: Literal["user"] = "user"
    approved: bool = True
    email: Optional[str] = None
    name: Optional[str] = None
    user_type_id: Optional[int] = None
    dev_mode: bool = False


class InternalAdminRecordResponse(BaseModel):
    id: int
    type: Literal["admin"] = "admin"
    pubkey: str
    session_nonce: int = 0


class InternalUserTypeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    display_order: int = 0
    created_at: Optional[str] = None


def _require_internal_token(x_internal_agent_token: Optional[str] = Header(None)) -> None:
    if not INTERNAL_AGENT_TOKEN:
        raise HTTPException(status_code=503, detail="Internal agent token not configured")
    if not x_internal_agent_token or x_internal_agent_token != INTERNAL_AGENT_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid internal agent token")


def _build_accessible_job_ids(user: InternalActorContext, requested_job_ids: Optional[list[str]]) -> list[str]:
    if user.type == "admin":
        available_job_ids = set(database.get_available_documents())
        if requested_job_ids:
            return [job_id for job_id in requested_job_ids if job_id in available_job_ids]
        return list(available_job_ids)

    if user.user_type_id is None:
        return []

    available_job_ids = set(database.get_available_documents_for_user_type(user.user_type_id))
    if requested_job_ids:
        return [job_id for job_id in requested_job_ids if job_id in available_job_ids]
    return list(available_job_ids)


def _filter_results_to_accessible_jobs(search_results: list[dict], accessible_job_ids: list[str]) -> list[dict]:
    allowed = set(accessible_job_ids)
    return [
        result
        for result in search_results
        if result.get("payload", {}).get("job_id") in allowed
    ]


def _is_document_overview_query(query: str) -> bool:
    normalized = query.lower()
    material_terms = (
        "uploaded",
        "document",
        "doc",
        "pdf",
        "book",
        "file",
        "resource",
    )
    overview_terms = (
        "read",
        "learn about",
        "overview",
        "basic understanding",
        "understanding",
        "summarize",
        "summary",
        "my org",
        "our org",
        "organization",
    )
    return any(term in normalized for term in material_terms) and any(
        term in normalized for term in overview_terms
    )


def _opening_chunk_texts_for_documents(job_ids: list[str], seen_chunk_ids: set[str]) -> list[str]:
    opening_texts: list[str] = []
    for job_id in job_ids:
        rows = ingest_db.list_retrieval_chunks(
            job_id,
            limit=DOCUMENT_OVERVIEW_OPENING_CHUNKS_PER_DOCUMENT,
        )
        for row in rows:
            chunk_id = str(row.get("chunk_id") or "")
            if not chunk_id or chunk_id in seen_chunk_ids:
                continue
            chunk = ingest_db.get_retrieval_chunk(chunk_id)
            text = (chunk or {}).get("text")
            if text:
                opening_texts.append(str(text))
                seen_chunk_ids.add(chunk_id)
    return opening_texts


def _execute_safe_select(sql: str) -> dict:
    normalized = sql.strip()
    if not re.match(r"^SELECT\b", normalized, re.IGNORECASE):
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "executionTimeMs": 0,
            "error": "Only SELECT queries are allowed. Use the CRUD endpoints for modifications.",
        }
    if ";" in normalized:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "executionTimeMs": 0,
            "error": "Only a single SELECT statement is allowed.",
        }

    for keyword in READ_ONLY_SELECT_FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized, re.IGNORECASE):
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "executionTimeMs": 0,
                "error": "Query contains forbidden keyword",
            }

    is_allowed, error = validate_sql_allowed_tables(normalized)
    if not is_allowed:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "executionTimeMs": 0,
            "error": error,
        }

    start_time = time.time()
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute(normalized)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "executionTimeMs": int((time.time() - start_time) * 1000),
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "executionTimeMs": int((time.time() - start_time) * 1000),
            "error": str(exc),
        }


@router.get("/users/{user_id}", response_model=InternalUserRecordResponse, dependencies=[Depends(_require_internal_token)])
async def get_user_record(user_id: int) -> InternalUserRecordResponse:
    user = database.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User not found: {user_id}")

    return InternalUserRecordResponse(
        id=int(user["id"]),
        approved=bool(user.get("approved", True)),
        email=user.get("email"),
        name=user.get("name"),
        user_type_id=user.get("user_type_id"),
        dev_mode=bool(user.get("dev_mode", False)),
    )


@router.get("/admins/by-pubkey/{pubkey}", response_model=InternalAdminRecordResponse, dependencies=[Depends(_require_internal_token)])
async def get_admin_record(pubkey: str) -> InternalAdminRecordResponse:
    admin = database.get_admin_by_pubkey(pubkey)
    if not admin:
        raise HTTPException(status_code=404, detail=f"Admin not found: {pubkey}")

    return InternalAdminRecordResponse(
        id=int(admin["id"]),
        pubkey=admin["pubkey"],
        session_nonce=int(admin.get("session_nonce", 0) or 0),
    )


@router.get("/user-types/{user_type_id}", response_model=InternalUserTypeResponse, dependencies=[Depends(_require_internal_token)])
async def get_user_type_record(user_type_id: int) -> InternalUserTypeResponse:
    user_type = database.get_user_type(user_type_id)
    if not user_type:
        raise HTTPException(status_code=404, detail=f"User type not found: {user_type_id}")

    return InternalUserTypeResponse(
        id=int(user_type["id"]),
        name=user_type["name"],
        description=user_type.get("description"),
        icon=user_type.get("icon"),
        display_order=int(user_type.get("display_order", 0) or 0),
        created_at=user_type.get("created_at"),
    )


@router.post("/document-search", response_model=InternalDocumentSearchResponse, dependencies=[Depends(_require_internal_token)])
async def document_search(payload: InternalDocumentSearchRequest) -> InternalDocumentSearchResponse:
    session_stub = {
        "jurisdiction": payload.jurisdiction,
        "situation_details": payload.situation_details,
    }
    search_query = _build_search_query(payload.query, session_stub)

    search_filter = None
    accessible_job_ids = _build_accessible_job_ids(payload.user, payload.job_ids)

    if not accessible_job_ids:
        return InternalDocumentSearchResponse(
            sources=[],
            context="",
            search_query=search_query,
            top_k=payload.top_k,
        )

    query_embedding = embed_texts([f"query: {search_query}"])[0]

    search_filter = {
        "should": [{"key": "job_id", "match": {"value": job_id}} for job_id in accessible_job_ids]
    }

    qdrant_url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{COLLECTION_NAME}/points/search"
    search_payload = {
        "vector": query_embedding,
        "limit": payload.top_k,
        "with_payload": True,
    }
    if search_filter:
        search_payload["filter"] = search_filter

    response = httpx.post(qdrant_url, json=search_payload, timeout=30.0)
    response.raise_for_status()
    search_results = response.json().get("result", [])
    search_results = _filter_results_to_accessible_jobs(search_results, accessible_job_ids)
    sources, _, chunk_texts = _process_search_results(search_results)
    if _is_document_overview_query(payload.query):
        seen_chunk_ids = {str(source.get("chunk_id") or "") for source in sources}
        overview_job_ids = sorted(accessible_job_ids)[:MAX_OVERVIEW_DOCS]
        opening_chunk_texts = _opening_chunk_texts_for_documents(
            overview_job_ids,
            seen_chunk_ids,
        )
        chunk_texts = opening_chunk_texts + chunk_texts
    context = _build_context(chunk_texts, sources)
    return InternalDocumentSearchResponse(
        sources=sources,
        context=context,
        search_query=search_query,
        top_k=payload.top_k,
    )


@router.post(
    "/resources/search",
    response_model=InternalResourceSearchResponse,
    dependencies=[Depends(_require_internal_token)],
)
async def resources_search(payload: InternalResourceSearchRequest) -> InternalResourceSearchResponse:
    """Faceted lookup of trusted real-world resources by region + help type.

    Returns only `ready` resources whose coverage scope contains the user's country,
    ranked by scope specificity (in-country first), then verified, then language match.
    """
    help_type = payload.help_type.strip()
    if not help_type:
        raise HTTPException(status_code=400, detail="help_type is required")
    effective_limit = max(
        0,
        min(payload.limit or DEFAULT_RESOURCE_SEARCH_LIMIT, MAX_RESOURCE_SEARCH_LIMIT),
    )
    resolved = database.normalize_jurisdiction(payload.jurisdiction)
    resources = database.search_resources(
        jurisdiction=payload.jurisdiction,
        help_type=help_type,
        language=payload.language,
        limit=effective_limit,
    )
    return InternalResourceSearchResponse(
        resources=resources,
        resolved_country_code=resolved,
        help_type=help_type,
    )


@router.get("/document-access", dependencies=[Depends(_require_internal_token)])
async def document_access(user_type_id: Optional[int] = None):
    return {
        "user_type_id": user_type_id,
        "available_document_ids": database.get_available_documents_for_user_type(user_type_id),
        "default_document_ids": database.get_active_documents_for_user_type(user_type_id),
    }


@router.get("/user-profile-context/{user_id}", dependencies=[Depends(_require_internal_token)])
async def user_profile_context(user_id: int, user_type_id: Optional[int] = None):
    return {
        "user_id": user_id,
        "user_type_id": user_type_id,
        "profile": database.get_user_chat_context_values(user_id=user_id, user_type_id=user_type_id),
    }


@router.post("/admin-db-query", dependencies=[Depends(_require_internal_token)])
async def admin_db_query(request: InternalAdminDbQueryRequest):
    return _execute_safe_select(request.sql)


@router.get("/health", dependencies=[Depends(_require_internal_token)])
async def internal_agent_health():
    return {"status": "healthy"}


@router.post(
    "/scoped-config-context",
    response_model=InternalScopedConfigContextResponse,
    dependencies=[Depends(_require_internal_token)],
)
async def scoped_config_context(
    payload: InternalScopedConfigContextRequest,
) -> InternalScopedConfigContextResponse:
    try:
        result = build_scoped_config_context(
            query=payload.query,
            actor=payload.actor.model_dump(),
            mode=payload.mode,
            requested_scopes=payload.requested_scopes,
        )
    except ScopedConfigAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return InternalScopedConfigContextResponse(**result)
