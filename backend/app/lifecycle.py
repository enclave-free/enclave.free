"""
Operator-Controlled Privacy lifecycle status.

This module is the product-facing registry for current Data Retention,
Data Deletion, and Audit Log coverage. It intentionally describes current
coverage, including gaps, instead of implying complete guarantees.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import logging
import os

from fastapi import APIRouter, Depends
from fastapi import HTTPException
import httpx
from pydantic import BaseModel, Field

import auth
import database
from data_deletion import (
    deletion_target_failed,
    deletion_target_skipped,
    deletion_target_succeeded,
    summarize_deletion_results,
)
import ingest
import ingest_db
import query


router = APIRouter(prefix="/admin/lifecycle", tags=["lifecycle"])
logger = logging.getLogger("sanctum.lifecycle")
_warned_missing_internal_agent_token = False


def _session_last_activity(session: dict) -> datetime | None:
    messages = session.get("messages") or []
    last_activity = None
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_time = _parse_timestamp(message.get("timestamp"))
        if message_time and (last_activity is None or message_time > last_activity):
            last_activity = message_time
    if last_activity:
        return last_activity
    return _parse_timestamp(session.get("created_at"))


DATA_CLASSES = [
    {
        "key": "user_profiles",
        "label": "User Profiles",
        "owner": "Enclave Control Plane",
        "storage_targets": ["SQLite"],
        "deletion": {
            "status": "complete",
            "summary": "User deletion removes the active User Profile, approval/access state, User Memory, and active Conversation state covered by this prototype.",
        },
        "retention": {
            "status": "partial",
            "summary": "Operators can invoke retention execution for stale active Conversation state.",
        },
        "audit": {
            "status": "partial",
            "summary": "User approval changes, auto-approval setting changes, and User Type administration are audited; deletion audit coverage remains separate.",
        },
        "notes": [
            "User Profile data is owned by the Enclave Control Plane.",
            "User Profile must remain distinct from Sage-owned User Memory.",
        ],
    },
    {
        "key": "user_memory",
        "label": "User Memory",
        "owner": "Sage",
        "storage_targets": ["SQLite"],
        "deletion": {
            "status": "complete",
            "summary": "Deleting a User purges Sage-owned User Memory for that subject User before the profile leaves active product surfaces.",
        },
        "retention": {
            "status": "not_started",
            "summary": "No operator-controlled Data Retention rule is currently enforced for User Memory.",
        },
        "audit": {
            "status": "partial",
            "summary": "Admin-confirmed User Memory creates, supersedes, deletes, and User deletion outcomes are audited; ambient Sage memory capture remains outside operator audit posture.",
        },
        "notes": [
            "User Memory is Sage-owned context and remains distinct from User Profile fields.",
        ],
    },
    {
        "key": "document_library",
        "label": "Document Library",
        "owner": "Enclave Control Plane",
        "storage_targets": ["SQLite", "uploads"],
        "deletion": {
            "status": "complete",
            "summary": "Active Document deletion removes library metadata, access defaults, uploaded artifact, retrieval entries, and runtime state.",
        },
        "retention": {
            "status": "partial",
            "summary": "Operators can invoke retention cleanup for failed and superseded Document ingestion artifacts.",
        },
        "audit": {
            "status": "partial",
            "summary": "Document upload, replacement, deletion, cleanup, and access/default changes are audited; some lower-level retrieval mutations are not direct operator events.",
        },
        "notes": [
            "Document Replacement keeps the current Document active until replacement succeeds.",
        ],
    },
    {
        "key": "retrieval_index",
        "label": "Retrieval Index",
        "owner": "Enclave Control Plane",
        "storage_targets": ["Qdrant"],
        "deletion": {
            "status": "complete",
            "summary": "Active Document deletion removes its derived Retrieval entries and reports the per-target result.",
        },
        "retention": {
            "status": "partial",
            "summary": "Retention execution removes retrieval points when failed or superseded Document artifacts are cleaned up.",
        },
        "audit": {
            "status": "partial",
            "summary": "Retrieval index deletion outcomes are represented in Data Deletion audit events, but individual retrieval writes are not directly audited.",
        },
        "notes": [
            "Retrieval selects knowledge from the Document Library for Sage Conversations.",
        ],
    },
    {
        "key": "uploaded_document_artifacts",
        "label": "Uploaded Document Artifacts",
        "owner": "Enclave Control Plane",
        "storage_targets": ["uploads"],
        "deletion": {
            "status": "complete",
            "summary": "Active Document deletion and lifecycle cleanup remove uploaded artifacts for current, failed, and superseded Document ingestion jobs.",
        },
        "retention": {
            "status": "partial",
            "summary": "Operators can run retention cleanup for failed and superseded artifacts; scheduled retention execution is not implemented.",
        },
        "audit": {
            "status": "partial",
            "summary": "Lifecycle cleanup and Document deletion audit uploaded artifact outcomes; raw upload artifact writes are represented by Document upload events.",
        },
        "notes": [
            "Uploaded files and chunk payload text are currently plaintext at rest.",
        ],
    },
    {
        "key": "sage_session_memory",
        "label": "Sage Session Memory",
        "owner": "Sage",
        "storage_targets": ["Postgres"],
        "deletion": {
            "status": "complete",
            "summary": "Conversation deletion removes the public session record and associated Sage Session Memory.",
        },
        "retention": {
            "status": "partial",
            "summary": "Operators can invoke retention execution for stale active Conversation state; persistent Sage Session Memory retention is not implemented.",
        },
        "audit": {
            "status": "partial",
            "summary": "Retention, User deletion, public Conversation deletion, and tombstone retry record privacy-preserving Session Memory lifecycle evidence.",
        },
        "notes": [
            "Session Memory belongs to the Agent Runtime.",
            "Session Memory Deletion is distinct from deleting a public session record.",
        ],
    },
    {
        "key": "audit_log",
        "label": "Audit Log",
        "owner": "Enclave Control Plane",
        "storage_targets": ["SQLite"],
        "deletion": {
            "status": "not_started",
            "summary": "Audit Log deletion is not implemented as a product workflow.",
        },
        "retention": {
            "status": "not_started",
            "summary": "Audit Log retention policy is not currently configurable.",
        },
        "audit": {
            "status": "partial",
            "summary": "The Audit Log is tamper-evident for covered actions, including approval, User Type governance, Document actions, and Data Deletion workflows, but coverage is partial.",
        },
        "notes": [
            "The Audit Log is operator-visible governance data, not a debug/server log.",
        ],
    },
]


class RetentionRunRequest(BaseModel):
    stale_conversation_days: int = Field(default=30, ge=0)
    document_artifact_days: int = Field(default=0, ge=0)


def get_lifecycle_status() -> dict:
    """Return the current Instance data lifecycle posture."""
    return {
        "data_classes": deepcopy(DATA_CLASSES),
        "deletion_tombstones": database.summarize_deletion_tombstones(),
    }


def _lifecycle_error_category(detail: object) -> str:
    if isinstance(detail, (httpx.TimeoutException, httpx.ConnectError)):
        return "target_unavailable"
    if isinstance(detail, httpx.HTTPStatusError):
        status_code = detail.response.status_code
        if status_code in (401, 403):
            return "unauthorized_internal_contract"
        if status_code == 404:
            return "not_found"
        if status_code in (409, 410):
            return "already_deleted"
        if 500 <= status_code:
            return "target_unavailable"
    text = str(detail or "").lower()
    if "unavailable" in text or "connection refused" in text or "timed out" in text:
        return "target_unavailable"
    if "not found" in text or "404" in text:
        return "not_found"
    if "already" in text and "deleted" in text:
        return "already_deleted"
    if "unauthorized" in text or "forbidden" in text or "401" in text or "403" in text:
        return "unauthorized_internal_contract"
    return "target_error"


def categorize_error(detail: object) -> str:
    return _lifecycle_error_category(detail)


def _sanitize_lifecycle_deletion(deletion: dict) -> dict:
    sanitized = deepcopy(deletion)
    sanitized["results"] = []
    for result in deletion.get("results", []):
        sanitized_result = dict(result)
        if sanitized_result.get("status") == "failed":
            sanitized_result["detail"] = _lifecycle_error_category(sanitized_result.get("detail"))
        sanitized["results"].append(sanitized_result)
    return sanitized


async def post_sage_session_memory_delete(payload: dict) -> dict:
    global _warned_missing_internal_agent_token
    sage_url = os.getenv("SAGE_WEB_URL", "http://sage:3000").rstrip("/")
    token = os.getenv("INTERNAL_AGENT_TOKEN", "")
    if not token and not _warned_missing_internal_agent_token:
        logger.warning(
            "INTERNAL_AGENT_TOKEN is unset; Sage lifecycle requests will be sent without X-Internal-Agent-Token."
        )
        _warned_missing_internal_agent_token = True
    headers = {"X-Internal-Agent-Token": token} if token else {}
    timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{sage_url}/internal/lifecycle/session-memory/delete",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        body = response.json()
        if "deletion" not in body:
            raise ValueError(
                f"Sage session-memory delete response missing deletion key: "
                f"status={response.status_code} body={body}"
            )
        return body["deletion"]


async def delete_session_memory_for_conversation(session: dict) -> dict:
    """Delete Sage Session Memory for a Conversation.

    The Python fallback only knows about legacy in-memory Conversation state.
    Sage-backed deletion will replace this boundary through the internal
    lifecycle contract.
    """
    session_id = str(session.get("id", "unknown"))
    if session.get("agent_runtime") == "sage":
        try:
            deletion = await post_sage_session_memory_delete({"conversation_id": session_id})
            return _sanitize_lifecycle_deletion(deletion)
        except Exception as exc:
            return summarize_deletion_results([
                deletion_target_failed(
                    target_kind="session_memory",
                    target_id=session_id,
                    action="delete_session_memory",
                    detail=categorize_error(exc),
                    retryable=True,
                )
            ])
    return summarize_deletion_results([
        deletion_target_succeeded(
            target_kind="session_memory",
            target_id=session_id,
            action="delete_session_memory",
            detail="No separate Sage Session Memory target exists for this legacy Conversation.",
        )
    ])


def _former_subject_ref(session: dict) -> str | None:
    owner_type = session.get("owner_type")
    owner_id = session.get("owner_id")
    if owner_type == "user" and owner_id:
        return f"deleted_user:{owner_id}"
    if owner_type == "admin" and owner_id:
        return f"admin:{owner_id}"
    return None


def _create_session_memory_tombstone(
    *,
    session: dict,
    source: str,
    workflow: str,
    deletion: dict,
) -> None:
    database.create_deletion_tombstone(
        lifecycle_data_class="sage_session_memory",
        conversation_id=str(session.get("id", "unknown")),
        former_subject_ref=_former_subject_ref(session),
        status="incomplete",
        source=source,
        workflow=workflow,
        deletion=deletion,
    )


def create_session_memory_tombstone(
    *,
    session: dict,
    source: str,
    workflow: str,
    deletion: dict,
) -> None:
    _create_session_memory_tombstone(
        session=session,
        source=source,
        workflow=workflow,
        deletion=deletion,
    )


def _parse_timestamp(value: object) -> datetime | None:
    """Parse an ISO timestamp string into a naive UTC datetime."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def _audit_retention_run(*, changed_by: str, deletion: dict) -> None:
    try:
        database.log_config_audit_event(
            table_name="data_deletion",
            config_key=f"retention:{datetime.utcnow().isoformat()}",
            old_value=None,
            new_value=json.dumps({
                "workflow": "run_retention",
                "status": deletion["status"],
                "retryable": deletion["retryable"],
                "counts": deletion["counts"],
                "results": deletion["results"],
            }, sort_keys=True),
            changed_by=changed_by,
        )
    except Exception as exc:
        logger.warning(
            "Failed to audit retention run changed_by=%s deletion_status=%s: %s",
            changed_by,
            deletion.get("status"),
            exc,
            exc_info=True,
        )


def _audit_deletion_tombstone_retry(*, changed_by: str, tombstone: dict, deletion: dict) -> None:
    try:
        database.log_config_audit_event(
            table_name="data_deletion",
            config_key=f"deletion_tombstone:{tombstone['id']}:retry:{datetime.utcnow().isoformat()}",
            old_value=None,
            new_value=json.dumps({
                "workflow": "retry_deletion_tombstone",
                "status": deletion["status"],
                "retryable": deletion["retryable"],
                "tombstone_id": tombstone["id"],
                "conversation_id": tombstone["conversation_id"],
                "lifecycle_data_class": tombstone["lifecycle_data_class"],
                "counts": deletion["counts"],
                "results": deletion["results"],
            }, sort_keys=True),
            changed_by=changed_by,
        )
    except Exception as exc:
        logger.warning(
            "Failed to audit deletion tombstone retry tombstone_id=%s status=%s: %s",
            tombstone.get("id"),
            deletion.get("status"),
            exc,
            exc_info=True,
        )


def audit_lifecycle_deletion(
    *,
    config_key: str,
    changed_by: str,
    workflow: str,
    target_id: str,
    deletion: dict,
) -> None:
    try:
        database.log_config_audit_event(
            table_name="data_deletion",
            config_key=config_key,
            old_value=None,
            new_value=json.dumps({
                "workflow": workflow,
                "target_id": target_id,
                "status": deletion["status"],
                "retryable": deletion["retryable"],
                "counts": deletion["counts"],
                "results": deletion["results"],
            }, sort_keys=True),
            changed_by=changed_by,
        )
    except Exception as exc:
        logger.warning(
            "Failed to audit lifecycle deletion config_key=%s workflow=%s target_id=%s: %s",
            config_key,
            workflow,
            target_id,
            exc,
            exc_info=True,
        )


async def run_retention(request: RetentionRunRequest, admin: dict) -> dict:
    now = datetime.utcnow()
    conversation_cutoff = now - timedelta(days=request.stale_conversation_days)
    document_cutoff = now - timedelta(days=request.document_artifact_days)
    results = []
    retained = {
        "stale_conversations": [],
        "skipped_conversations": [],
        "document_artifacts": [],
    }

    stale_sessions = []
    with query._sessions_lock:
        stale_session_ids = []
        for session_id, session in list(query._sessions.items()):
            with query._session_lock(session):
                last_activity = _session_last_activity(session)
            if last_activity and last_activity <= conversation_cutoff:
                stale_session_ids.append(session_id)

        for session_id in stale_session_ids:
            if database.has_incomplete_deletion_tombstone_for_conversation(session_id):
                retained["skipped_conversations"].append(session_id)
                results.append(deletion_target_skipped(
                    target_kind="conversation",
                    target_id=session_id,
                    action="retention_skip_tombstoned_conversation",
                    detail="Skipped Conversation because an incomplete Deletion Tombstone already tracks its lifecycle deletion.",
                ))
                continue
            session = query._sessions.pop(session_id, None)
            if session is not None:
                stale_sessions.append((session_id, session))

    for session_id, session in stale_sessions:
        with query._session_lock(session):
            last_activity = _session_last_activity(session)
            became_active = bool(last_activity and last_activity > conversation_cutoff)
        if became_active:
            with query._sessions_lock:
                query._sessions[session_id] = session
            retained["skipped_conversations"].append(session_id)
            results.append(deletion_target_skipped(
                target_kind="conversation",
                target_id=session_id,
                action="retention_skip_active_conversation",
                detail="Skipped Conversation because it became active before retention deletion.",
            ))
            continue

        retained["stale_conversations"].append(session_id)
        session_memory_deletion = await delete_session_memory_for_conversation(session)
        if session_memory_deletion["status"] != "succeeded":
            create_session_memory_tombstone(
                session=session,
                source="retention_execution",
                workflow="run_retention",
                deletion=session_memory_deletion,
            )
        results.extend(session_memory_deletion["results"])
        results.append(deletion_target_succeeded(
            target_kind="conversation",
            target_id=session_id,
            action="retention_delete_stale_conversation",
            detail="Deleted stale active Conversation state.",
        ))

    job_limit = 1000
    job_offset = 0
    jobs_to_check = []
    while True:
        jobs = ingest_db.list_jobs(limit=job_limit, offset=job_offset)
        if not jobs:
            break
        jobs_to_check.extend(jobs)
        if len(jobs) < job_limit:
            break
        job_offset += job_limit

    for job in jobs_to_check:
        reason = ingest._document_artifact_cleanup_reason(job)
        if not reason:
            continue
        updated_at = _parse_timestamp(job.get("updated_at"))
        if updated_at is None:
            logger.warning(
                "Skipping retention cleanup for document job with missing or invalid updated_at",
                extra={"job_id": job.get("job_id"), "updated_at": job.get("updated_at")},
            )
            continue
        if updated_at > document_cutoff:
            continue

        job_id = job["job_id"]
        deletion_response = await ingest._delete_document_job_artifacts(job_id, job)
        retained["document_artifacts"].append({
            "job_id": job_id,
            "filename": job.get("filename", "unknown"),
            "reason": reason,
            "deletion": deletion_response["deletion"],
        })
        results.extend(deletion_response["deletion"]["results"])

    if not results:
        results.append(deletion_target_skipped(
            target_kind="retention",
            target_id="run",
            action="run_retention",
            detail="No supported data classes were eligible for retention cleanup.",
        ))

    deletion = summarize_deletion_results(results)
    _audit_retention_run(
        changed_by=admin.get("pubkey", "unknown"),
        deletion=deletion,
    )
    return {
        "status": deletion["status"],
        "retained": retained,
        "deletion": deletion,
    }


@router.get("/status", response_model=dict)
async def get_admin_lifecycle_status(_admin: dict = Depends(auth.require_admin)):
    return get_lifecycle_status()


@router.get("/deletion-tombstones", response_model=dict)
async def list_admin_deletion_tombstones(
    status: str | None = None,
    _admin: dict = Depends(auth.require_admin),
):
    if status is not None and status not in {"incomplete", "completed"}:
        raise HTTPException(status_code=400, detail="Unsupported deletion tombstone status")
    return {"tombstones": database.list_deletion_tombstones(status=status)}


@router.post("/deletion-tombstones/{tombstone_id}/retry", response_model=dict)
async def retry_admin_deletion_tombstone(
    tombstone_id: int,
    admin: dict = Depends(auth.require_admin),
):
    tombstone = database.get_deletion_tombstone(tombstone_id)
    if not tombstone:
        raise HTTPException(status_code=404, detail="Deletion tombstone not found")
    if tombstone["lifecycle_data_class"] != "sage_session_memory":
        raise HTTPException(status_code=400, detail="Unsupported deletion tombstone class")
    if tombstone["status"] == "completed":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Deletion tombstone is already completed",
                "tombstone": tombstone,
            },
        )
    deletion = await delete_session_memory_for_conversation({
        "id": tombstone["conversation_id"],
        "agent_runtime": "sage",
        "owner_type": "tombstone",
        "owner_id": tombstone.get("former_subject_ref"),
    })
    new_status = "completed" if deletion["status"] == "succeeded" else "incomplete"
    updated = database.update_deletion_tombstone_after_retry(
        tombstone_id,
        status=new_status,
        deletion=deletion,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Deletion tombstone not found")
    _audit_deletion_tombstone_retry(
        changed_by=admin.get("pubkey", "unknown"),
        tombstone=updated,
        deletion=deletion,
    )
    return {
        "status": deletion["status"],
        "retryable": deletion["retryable"],
        "tombstone": updated,
        "deletion": deletion,
    }


@router.post("/retention/run", response_model=dict)
async def run_admin_retention(
    request: RetentionRunRequest,
    admin: dict = Depends(auth.require_admin),
):
    return await run_retention(request, admin)
