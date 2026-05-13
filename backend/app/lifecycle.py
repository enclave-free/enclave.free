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

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

import auth
import database
from data_deletion import (
    deletion_target_skipped,
    deletion_target_succeeded,
    summarize_deletion_results,
)
import ingest
import ingest_db
import query


router = APIRouter(prefix="/admin/lifecycle", tags=["lifecycle"])
logger = logging.getLogger("sanctum.lifecycle")


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
            "status": "not_started",
            "summary": "Session Memory lifecycle actions are not yet represented in the Audit Log.",
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
    return {"data_classes": deepcopy(DATA_CLASSES)}


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


async def run_retention(request: RetentionRunRequest, admin: dict) -> dict:
    now = datetime.utcnow()
    conversation_cutoff = now - timedelta(days=request.stale_conversation_days)
    document_cutoff = now - timedelta(days=request.document_artifact_days)
    results = []
    retained = {
        "stale_conversations": [],
        "document_artifacts": [],
    }

    with query._sessions_lock:
        stale_session_ids = []
        for session_id, session in list(query._sessions.items()):
            created_at = _parse_timestamp(session.get("created_at"))
            if created_at and created_at <= conversation_cutoff:
                stale_session_ids.append(session_id)

        for session_id in stale_session_ids:
            query._sessions.pop(session_id, None)
            retained["stale_conversations"].append(session_id)
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
        updated_at = _parse_timestamp(job.get("updated_at") or job.get("created_at"))
        if updated_at and updated_at > document_cutoff:
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


@router.post("/retention/run", response_model=dict)
async def run_admin_retention(
    request: RetentionRunRequest,
    admin: dict = Depends(auth.require_admin),
):
    return await run_retention(request, admin)
