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
from ai_config import get_session_defaults
from query import _build_context, _build_search_query, _process_search_results
from sql_safety import validate_sql_allowed_tables
from store import embed_texts, COLLECTION_NAME, QDRANT_HOST, QDRANT_PORT

logger = logging.getLogger("enclave.internal_agent")

router = APIRouter(prefix="/internal/agent", tags=["internal-agent"])

INTERNAL_AGENT_TOKEN = os.getenv("INTERNAL_AGENT_TOKEN", "").strip()


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


class InternalAdminDbQueryRequest(BaseModel):
    sql: str


class InternalAIConfigResponse(BaseModel):
    prompt_sections: dict[str, object]
    parameters: dict[str, object]
    defaults: dict[str, object]
    compiled_prompt: str


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


def _serialize_ai_config_value(value_type: str, value: str):
    if value_type == "number":
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return value
        return int(parsed) if float(parsed).is_integer() else parsed
    if value_type == "boolean":
        return str(value).strip().lower() == "true"
    if value_type == "json":
        try:
            import json
            return json.loads(value)
        except Exception:
            return value
    return value


def _build_compiled_prompt(user_type_id: Optional[int]) -> str:
    effective = database.get_effective_ai_config(user_type_id)
    by_key = {row["key"]: _serialize_ai_config_value(row["value_type"], row["value"]) for row in effective}
    rules = by_key.get("prompt_rules", [])
    forbidden = by_key.get("prompt_forbidden", [])

    lines = [
        "PROFILE: enclave_web_v1",
        "",
        "=== TONE ===",
        str(by_key.get("prompt_tone", "")),
        "",
        "=== RULES ===",
    ]

    if isinstance(rules, list) and rules:
        lines.extend(f"{idx}. {rule}" for idx, rule in enumerate(rules, start=1))
    else:
        lines.append("1. Be accurate, concise, and operationally useful.")

    lines.extend(["", "=== FORBIDDEN ==="])
    if isinstance(forbidden, list) and forbidden:
        lines.extend(f"- {rule}" for rule in forbidden)
    else:
        lines.append("- None configured")

    lines.extend(
        [
            "",
            "=== DEFAULTS ===",
            f"temperature={by_key.get('temperature', 0.1)}",
            f"top_k={by_key.get('top_k', 8)}",
            f"web_search_default={by_key.get('web_search_default', False)}",
        ]
    )
    return "\n".join(lines)


def _build_accessible_job_ids(user: InternalActorContext, requested_job_ids: Optional[list[str]]) -> list[str]:
    if user.type == "admin":
        return list(requested_job_ids or [])

    if user.user_type_id is None:
        return []

    available_job_ids = set(database.get_available_documents_for_user_type(user.user_type_id))
    if requested_job_ids:
        return [job_id for job_id in requested_job_ids if job_id in available_job_ids]
    return list(available_job_ids)


def _execute_safe_select(sql: str) -> dict:
    normalized = sql.strip()
    if not normalized.upper().startswith("SELECT"):
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "executionTimeMs": 0,
            "error": "Only SELECT queries are allowed. Use the CRUD endpoints for modifications.",
        }

    dangerous_patterns = [
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bTRUNCATE\b",
        r"\bATTACH\b",
        r"\bDETACH\b",
        r"\bPRAGMA\b",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
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
    query_embedding = embed_texts([f"query: {search_query}"])[0]

    search_filter = None
    accessible_job_ids = _build_accessible_job_ids(payload.user, payload.job_ids)

    if payload.user.type == "admin":
        if accessible_job_ids:
            search_filter = {
                "should": [{"key": "job_id", "match": {"value": job_id}} for job_id in accessible_job_ids]
            }
    else:
        if not accessible_job_ids:
            search_filter = {"must": [{"key": "job_id", "match": {"value": "__impossible__"}}]}
        else:
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
    sources, _, chunk_texts = _process_search_results(search_results)
    context = _build_context(chunk_texts, sources)
    return InternalDocumentSearchResponse(
        sources=sources,
        context=context,
        search_query=search_query,
        top_k=payload.top_k,
    )


@router.get("/document-access", dependencies=[Depends(_require_internal_token)])
async def document_access(user_type_id: Optional[int] = None):
    return {
        "user_type_id": user_type_id,
        "available_document_ids": database.get_available_documents_for_user_type(user_type_id),
        "default_document_ids": database.get_active_documents_for_user_type(user_type_id),
    }


@router.get("/session-defaults", dependencies=[Depends(_require_internal_token)])
async def internal_session_defaults(user_type_id: Optional[int] = None):
    defaults = get_session_defaults(user_type_id)
    default_docs = (
        database.get_active_documents_for_user_type(user_type_id)
        if user_type_id is not None
        else database.get_default_active_documents()
    )
    return {
        "web_search_enabled": defaults.get("web_search_default", False),
        "default_document_ids": default_docs,
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


@router.get("/ai-config/effective", response_model=InternalAIConfigResponse, dependencies=[Depends(_require_internal_token)])
async def effective_ai_config(user_type_id: Optional[int] = None) -> InternalAIConfigResponse:
    effective = database.get_effective_ai_config(user_type_id)
    prompt_sections: dict[str, object] = {}
    parameters: dict[str, object] = {}
    defaults: dict[str, object] = {}

    for row in effective:
        parsed = _serialize_ai_config_value(row["value_type"], row["value"])
        if row["category"] == "prompt_section":
            prompt_sections[row["key"]] = parsed
        elif row["category"] == "parameter":
            parameters[row["key"]] = parsed
        elif row["category"] == "default":
            defaults[row["key"]] = parsed

    return InternalAIConfigResponse(
        prompt_sections=prompt_sections,
        parameters=parameters,
        defaults=defaults,
        compiled_prompt=_build_compiled_prompt(user_type_id),
    )


@router.get("/health", dependencies=[Depends(_require_internal_token)])
async def internal_agent_health():
    return {"status": "healthy"}
