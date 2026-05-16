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
from pathlib import Path
import tempfile
import secrets

from fastapi import APIRouter, Depends
from fastapi import Header, HTTPException
import httpx
from pydantic import BaseModel, Field

import auth
import content_artifacts
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
import store


router = APIRouter(prefix="/admin/lifecycle", tags=["lifecycle"])
logger = logging.getLogger("enclave.lifecycle")
_warned_missing_internal_agent_token = False
_sage_client: httpx.AsyncClient | None = None
_sage_client_timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=10.0, pool=5.0)
RETENTION_AUTOMATION_ACTOR = "machine:scheduled-retention"


def _get_sage_client() -> httpx.AsyncClient:
    global _sage_client
    if _sage_client is None or _sage_client.is_closed:
        _sage_client = httpx.AsyncClient(timeout=_sage_client_timeout)
    return _sage_client


def _require_retention_automation_actor(
    x_retention_automation_token: str | None = Header(default=None),
) -> dict:
    configured_token = os.getenv("RETENTION_AUTOMATION_TOKEN", "").strip()
    if not configured_token:
        raise HTTPException(status_code=503, detail="Retention Automation Token is not configured")
    if not x_retention_automation_token or not secrets.compare_digest(
        x_retention_automation_token,
        configured_token,
    ):
        raise HTTPException(status_code=401, detail="Invalid Retention Automation Token")
    return {
        "type": "machine",
        "pubkey": RETENTION_AUTOMATION_ACTOR,
        "actor": RETENTION_AUTOMATION_ACTOR,
    }


async def close_sage_client() -> None:
    global _sage_client
    if _sage_client is not None:
        await _sage_client.aclose()
        _sage_client = None


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
            "status": "partial",
            "summary": "Operators can invoke age-based Data Retention for stale active User Memory without exposing raw memory content in lifecycle evidence.",
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
            "New Retrieval Index points store vectors and minimal metadata; encrypted chunk text lives in SQLite.",
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
            "New uploaded artifacts are encrypted by default when a Content Encryption Key is configured.",
            "Retrieval chunk text is stored separately from uploaded artifacts.",
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
        "key": "inference_verification_records",
        "label": "Inference Verification Records",
        "owner": "Enclave Control Plane",
        "storage_targets": ["SQLite"],
        "deletion": {
            "status": "not_started",
            "summary": "Deletion controls for Inference Verification Records are not implemented yet.",
        },
        "retention": {
            "status": "indefinite",
            "summary": "Inference Verification Records are retained indefinitely by default until configurable retention and deletion controls are implemented.",
        },
        "audit": {
            "status": "partial",
            "summary": "Manual verification and blocked protected inference create concise Audit Log events without storing full attestation material in the Audit Log.",
        },
        "notes": [
            "Full provider attestation material remains in the Inference Verification Record, not in the Audit Log.",
            "These records support operator repair and historical evidence for protected Model Provider calls.",
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
            "status": "partial",
            "summary": "Audit Log retention can compact sensitive detail while preserving lifecycle evidence; ordinary full Audit Log deletion is not exposed.",
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


UNSUPPORTED_DEPLOYMENT_SURFACES = [
    {
        "key": "docker_logs",
        "label": "Docker Logs",
        "category": "runtime_logs",
        "summary": "Container stdout/stderr logs are managed by the deployment runtime, not product lifecycle controls.",
    },
    {
        "key": "gateway_logs",
        "label": "Gateway Logs",
        "category": "runtime_logs",
        "summary": "Gateway and reverse-proxy logs are operational records outside application retention/deletion workflows.",
    },
    {
        "key": "host_backups",
        "label": "Host Backups",
        "category": "host_storage",
        "summary": "Host-level backups must be governed by operator backup policy outside the product.",
    },
    {
        "key": "host_snapshots",
        "label": "Host Snapshots",
        "category": "host_storage",
        "summary": "Filesystem, VM, and volume snapshots are outside active-storage lifecycle control.",
    },
    {
        "key": "sqlite_wal",
        "label": "SQLite WAL",
        "category": "database_wal",
        "summary": "SQLite write-ahead-log files are database runtime artifacts, not product lifecycle records.",
    },
    {
        "key": "postgres_wal",
        "label": "Postgres WAL",
        "category": "database_wal",
        "summary": "Postgres write-ahead-log files are database runtime artifacts managed by the database operator.",
    },
    {
        "key": "provider_traces",
        "label": "Provider-Side Traces",
        "category": "provider_records",
        "summary": "LLM, email, search, or infrastructure provider traces are governed by those providers and deployment contracts.",
    },
]


ENFORCED_RETENTION_DATA_CLASS_KEYS = {
    "sage_session_memory",
    "uploaded_document_artifacts",
    "user_memory",
    "audit_log",
}


SECURE_ERASE_SCOPE = {
    "status": "unsupported",
    "summary": (
        "Secure Erase is out of scope for v1; lifecycle controls apply to stated "
        "active-storage targets and exclude unsupported Deployment Surfaces such as logs, "
        "WAL, backups, snapshots, and provider traces."
    ),
}


class RetentionRunRequest(BaseModel):
    stale_conversation_days: int = Field(default=30, ge=0)
    document_artifact_days: int = Field(default=0, ge=0)


class ScheduledRetentionRunRequest(BaseModel):
    retry_limit: int = Field(default=3, ge=0)


class RetentionPolicyUpdateRequest(BaseModel):
    enabled: bool
    retention_window_days: int = Field(ge=1)
    scheduled_enforcement_enabled: bool


class UnsupportedSurfaceAcknowledgementRequest(BaseModel):
    acknowledged: bool = True


class ArtifactEncryptionPostureUpdateRequest(BaseModel):
    posture: str


LIFECYCLE_SCOPE = {
    "key": "active_storage_lifecycle",
    "label": "Active Storage Lifecycle",
    "summary": (
        "Lifecycle controls apply to supported Lifecycle Data Classes in active product storage. "
        "Unsupported Deployment Surfaces remain disclosed separately."
    ),
    "excludes": "Deployment Surfaces such as runtime logs, WAL, backups, snapshots, and provider traces.",
}


RETENTION_SCHEDULER_SCOPE = {
    "status": "external_or_manual",
    "summary": (
        "Scheduled Retention Policy can mark Lifecycle Data Classes for scheduled Retention Execution; "
        "the product does not yet include its own Retention Scheduler, so execution is manual or externally invoked."
    ),
}


def _data_class_keys() -> set[str]:
    return {
        data_class["key"]
        for data_class in DATA_CLASSES
        if data_class["key"] in ENFORCED_RETENTION_DATA_CLASS_KEYS
    }


def _default_retention_policy(data_class_key: str) -> dict:
    return {
        "lifecycle_data_class": data_class_key,
        "enabled": False,
        "retention_window_days": 30,
        "scheduled_enforcement_enabled": False,
    }


def _stored_retention_policies() -> dict[str, dict]:
    raw_value = database.get_setting("lifecycle_retention_policies")
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    policies = {}
    valid_keys = _data_class_keys()
    for key, value in parsed.items():
        if key not in valid_keys or not isinstance(value, dict):
            continue
        policy = _default_retention_policy(key)
        policy["enabled"] = bool(value.get("enabled", policy["enabled"]))
        try:
            retention_window_days = int(value.get("retention_window_days", policy["retention_window_days"]))
        except (TypeError, ValueError):
            retention_window_days = policy["retention_window_days"]
        policy["retention_window_days"] = max(1, retention_window_days)
        policy["scheduled_enforcement_enabled"] = bool(
            value.get("scheduled_enforcement_enabled", policy["scheduled_enforcement_enabled"])
        )
        policies[key] = policy
    return policies


def _retention_policy_for(data_class_key: str) -> dict:
    return {
        **_default_retention_policy(data_class_key),
        **_stored_retention_policies().get(data_class_key, {}),
    }


def _data_classes_with_retention_policies() -> list[dict]:
    stored_policies = _stored_retention_policies()
    classes = []
    for data_class in DATA_CLASSES:
        class_copy = deepcopy(data_class)
        class_copy["confidentiality"] = _confidentiality_posture_for_data_class(data_class["key"])
        if data_class["key"] in _data_class_keys():
            class_copy["retention_policy"] = {
                **_default_retention_policy(data_class["key"]),
                **stored_policies.get(data_class["key"], {}),
            }
        classes.append(class_copy)
    return classes


def _confidentiality_posture_for_data_class(data_class_key: str) -> dict:
    artifact_status = _artifact_encryption_status()
    if data_class_key == "uploaded_document_artifacts":
        return {
            "status": artifact_status["status"],
            "summary": artifact_status["summary"],
        }
    if data_class_key == "document_library":
        return {
            "status": "partial" if artifact_status["status"] != "encrypted" else "encrypted",
            "summary": "Document metadata is stored separately from uploaded artifact content; artifact content posture is reported under Uploaded Document Artifacts.",
        }
    if data_class_key == "retrieval_index":
        retrieval_status = _retrieval_index_confidentiality_status()
        if retrieval_status["status"] != "partial":
            return retrieval_status
        return {
            "status": "partial",
            "summary": "New Qdrant Retrieval Index entries store vector data and minimal metadata; legacy plaintext payloads may remain until confidentiality migration lands.",
        }
    if data_class_key == "user_profiles":
        return {
            "status": "encrypted",
            "summary": "User PII fields are encrypted at rest in SQLite.",
        }
    if data_class_key == "user_memory":
        return {
            "status": "partial",
            "summary": "Initial User Memory is low-sensitivity Sage context and may be stored without content encryption.",
        }
    if data_class_key == "sage_session_memory":
        return {
            "status": "partial",
            "summary": "Sage Session Memory uses active-storage lifecycle controls; Secure Erase and full historical/log retention remain unsupported.",
        }
    if data_class_key == "inference_verification_records":
        return {
            "status": "partial",
            "summary": "Attestation material is encrypted at rest when the deployment secret is configured; Audit Log references intentionally omit full attestation material.",
        }
    if data_class_key == "audit_log":
        return {
            "status": "partial",
            "summary": "Audit Log detail can be compacted by retention while lifecycle evidence is preserved.",
        }
    return {
        "status": "unsupported",
        "summary": "No confidentiality posture is defined for this Lifecycle Data Class.",
    }


def _artifact_encryption_status() -> dict:
    status = content_artifacts.artifact_encryption_status()
    if status["status"] != "encrypted":
        return status

    inventory = _active_artifact_confidentiality_inventory()
    if inventory["plaintext_artifacts"]:
        return {
            "posture": "required",
            "status": "mixed",
            "summary": (
                f"Artifact encryption is required, but {len(inventory['plaintext_artifacts'])} active uploaded "
                "artifact(s) still appear to be legacy plaintext."
            ),
            "legacy_plaintext_artifacts": inventory["plaintext_artifacts"],
        }
    if inventory["missing_artifacts"]:
        return {
            "posture": "required",
            "status": "mixed",
            "summary": (
                f"Artifact encryption is required, but {len(inventory['missing_artifacts'])} active uploaded "
                "artifact path(s) could not be verified."
            ),
            "missing_artifacts": inventory["missing_artifacts"],
        }
    return {
        **status,
        "summary": "Uploaded Document artifacts are encrypted in active storage for new writes and verified active artifacts.",
    }


def _active_artifact_confidentiality_inventory() -> dict:
    plaintext_artifacts = []
    encrypted_artifacts = []
    missing_artifacts = []
    offset = 0
    limit = 1000
    active_statuses = {"completed", "completed_with_errors", "processing", "pending"}
    while True:
        jobs = ingest_db.list_jobs(limit=limit, offset=offset)
        if not jobs:
            break
        for job in jobs:
            if job.get("status") not in active_statuses:
                continue
            if job.get("is_current") in (0, False):
                continue
            if job.get("replaced_by_job_id"):
                continue
            file_path = job.get("file_path")
            if not file_path:
                continue
            try:
                with open(file_path, "rb") as artifact:
                    content = artifact.read(64)
            except FileNotFoundError:
                missing_artifacts.append(_document_artifact_result(job, "missing"))
                continue
            except OSError as exc:
                missing_artifacts.append({**_document_artifact_result(job, "unreadable"), "error": str(exc)})
                continue
            if content_artifacts.is_encrypted_artifact(content):
                encrypted_artifacts.append(_document_artifact_result(job, "encrypted"))
            else:
                plaintext_artifacts.append(_document_artifact_result(job, "legacy_plaintext"))
        if len(jobs) < limit:
            break
        offset += limit
    return {
        "plaintext_artifacts": plaintext_artifacts,
        "encrypted_artifacts": encrypted_artifacts,
        "missing_artifacts": missing_artifacts,
    }


def _document_artifact_result(job: dict, status: str) -> dict:
    return {
        "job_id": job.get("job_id"),
        "filename": job.get("filename"),
        "file_path": job.get("file_path"),
        "status": status,
    }


def _atomic_replace_bytes(path: Path, content: bytes) -> None:
    temp_path: Path | None = None
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as temp:
        temp.write(content)
        temp.flush()
        os.fsync(temp.fileno())
        temp_path = Path(temp.name)
    try:
        temp_path.replace(path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _retrieval_index_confidentiality_status() -> dict:
    detection = store.detect_legacy_plaintext_payloads()
    if detection.get("legacy_plaintext_payloads"):
        return {
            "status": "mixed",
            "summary": (
                "Retrieval Index has minimized encrypted chunk storage for new writes, but legacy plaintext "
                f"Qdrant payload text remains in {detection['legacy_plaintext_payloads']} inspected point(s)."
            ),
            "legacy_plaintext_payloads": detection["legacy_plaintext_payloads"],
        }
    if detection.get("checked"):
        return {
            "status": "encrypted",
            "summary": "Qdrant Retrieval Index payloads are minimized; encrypted chunk text is hydrated from product-owned storage.",
        }
    return {
        "status": "partial",
        "summary": detection.get(
            "summary",
            "Qdrant Retrieval Index payload confidentiality could not be verified from this process.",
        ),
    }


def preview_confidentiality_migration() -> dict:
    artifact_status = _artifact_encryption_status()
    artifact_inventory = _active_artifact_confidentiality_inventory()
    try:
        legacy_payloads = store.list_legacy_plaintext_payloads()
        qdrant_available = True
        qdrant_error = None
    except Exception as exc:
        legacy_payloads = []
        qdrant_available = False
        qdrant_error = str(exc)

    artifact_actions = []
    for artifact in artifact_inventory["plaintext_artifacts"]:
        artifact_actions.append({
            **artifact,
            "target": "uploaded_document_artifact",
            "action": "encrypt_artifact",
            "eligible": artifact_status["status"] != "not_configured",
            "skip_reason": None if artifact_status["status"] != "not_configured" else "content_encryption_key_not_configured",
        })

    retrieval_actions = []
    for payload in legacy_payloads:
        retrieval_actions.append({
            "target": "retrieval_payload",
            "action": "backfill_chunk_and_minimize_qdrant_payload",
            "point_id": str(payload.get("point_id")),
            "chunk_id": payload.get("chunk_id"),
            "job_id": payload.get("job_id"),
            "source_file": payload.get("source_file"),
            "eligible": bool(payload.get("chunk_id") and payload.get("job_id") and payload.get("text")),
            "skip_reason": None if payload.get("chunk_id") and payload.get("job_id") and payload.get("text") else "missing_recoverable_chunk_metadata",
        })

    skipped = []
    if not qdrant_available:
        skipped.append({
            "target": "retrieval_payload",
            "action": "inspect_qdrant_payloads",
            "status": "skipped",
            "reason": qdrant_error,
        })

    documents: dict[str, dict] = {}
    for action in artifact_actions + retrieval_actions:
        job_id = action.get("job_id")
        if not job_id:
            continue
        documents.setdefault(job_id, {
            "job_id": job_id,
            "filename": action.get("filename") or action.get("source_file"),
            "actions": [],
        })["actions"].append(action)

    return {
        "status": "ready" if artifact_actions or retrieval_actions else "nothing_to_migrate",
        "artifact_encryption": artifact_status,
        "affected_documents": list(documents.values()),
        "artifacts": artifact_actions,
        "retrieval_payloads": retrieval_actions,
        "skipped": skipped,
        "expected_actions": artifact_actions + retrieval_actions,
        "secure_erase_claimed": False,
        "summary": (
            f"Preview found {len(artifact_actions)} plaintext artifact(s) and "
            f"{len(retrieval_actions)} legacy Retrieval payload(s). No Secure Erase claim is made."
        ),
    }


def execute_confidentiality_migration(*, actor: str) -> dict:
    preview = preview_confidentiality_migration()
    results = []

    for artifact in preview["artifacts"]:
        if not artifact["eligible"]:
            results.append({**artifact, "status": "skipped", "reason": artifact["skip_reason"]})
            continue
        try:
            path = Path(artifact["file_path"])
            content = path.read_bytes()
            if content_artifacts.is_encrypted_artifact(content):
                status = "skipped"
                reason = "already_encrypted"
            else:
                encrypted_content = content_artifacts.encrypt_bytes(content)
                _atomic_replace_bytes(path, encrypted_content)
                status = "succeeded"
                reason = None
            results.append({**artifact, "status": status, "reason": reason})
        except Exception as exc:
            results.append({**artifact, "status": "failed", "reason": str(exc)})

    try:
        legacy_payloads = store.list_legacy_plaintext_payloads()
    except Exception as exc:
        legacy_payloads = []
        results.append({
            "target": "retrieval_payload",
            "action": "inspect_qdrant_payloads",
            "status": "failed",
            "reason": str(exc),
        })

    for payload in legacy_payloads:
        action = {
            "target": "retrieval_payload",
            "action": "backfill_chunk_and_minimize_qdrant_payload",
            "point_id": str(payload.get("point_id")),
            "chunk_id": payload.get("chunk_id"),
            "job_id": payload.get("job_id"),
            "source_file": payload.get("source_file"),
        }
        if not (payload.get("chunk_id") and payload.get("job_id") and payload.get("text")):
            results.append({**action, "status": "skipped", "reason": "missing_recoverable_chunk_metadata"})
            continue
        try:
            ingest_db.upsert_retrieval_chunk(
                chunk_id=payload["chunk_id"],
                job_id=payload["job_id"],
                chunk_index=int(payload.get("payload", {}).get("chunk_index") or 0),
                source_file=payload.get("source_file") or "",
                text=payload["text"],
            )
            store.rewrite_payload_without_plaintext(payload["point_id"], payload.get("payload") or {})
            results.append({**action, "status": "succeeded", "reason": None})
        except Exception as exc:
            results.append({**action, "status": "failed", "reason": str(exc)})

    database.update_setting_with_audit(
        "confidentiality_migration_last_run",
        json.dumps({"actor": actor, "result_count": len(results), "secure_erase_claimed": False}),
        changed_by=actor,
    )

    return {
        "status": "completed_with_errors" if any(result["status"] == "failed" for result in results) else "completed",
        "results": results,
        "summary": "Confidentiality migration completed without making any Secure Erase claim.",
        "secure_erase_claimed": False,
        "post_migration_status": get_lifecycle_status(),
    }


def _update_retention_policy(data_class_key: str, request: RetentionPolicyUpdateRequest, *, changed_by: str) -> dict:
    if data_class_key not in _data_class_keys():
        raise HTTPException(status_code=404, detail="Lifecycle Data Class not found")
    policies = _stored_retention_policies()
    policies[data_class_key] = {
        "lifecycle_data_class": data_class_key,
        "enabled": request.enabled,
        "retention_window_days": request.retention_window_days,
        "scheduled_enforcement_enabled": request.scheduled_enforcement_enabled,
    }
    database.update_setting_with_audit(
        "lifecycle_retention_policies",
        json.dumps(policies, sort_keys=True),
        changed_by=changed_by,
    )
    return _retention_policy_for(data_class_key)


def _acknowledged_unsupported_surface_keys() -> set[str]:
    raw_value = database.get_setting("lifecycle_unsupported_surface_acknowledgements")
    if not raw_value:
        return set()
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return set()
    if not isinstance(parsed, list):
        return set()
    valid_keys = {surface["key"] for surface in UNSUPPORTED_DEPLOYMENT_SURFACES}
    return {
        key
        for key in parsed
        if isinstance(key, str) and key in valid_keys
    }


def _unsupported_deployment_surfaces() -> list[dict]:
    acknowledged_keys = _acknowledged_unsupported_surface_keys()
    surfaces = []
    for surface in UNSUPPORTED_DEPLOYMENT_SURFACES:
        surfaces.append({
            **deepcopy(surface),
            "status": "unsupported",
            "acknowledged": surface["key"] in acknowledged_keys,
        })
    return surfaces


def _set_unsupported_surface_acknowledgement(surface_key: str, acknowledged: bool, *, changed_by: str) -> list[dict]:
    valid_keys = {surface["key"] for surface in UNSUPPORTED_DEPLOYMENT_SURFACES}
    if surface_key not in valid_keys:
        raise HTTPException(status_code=404, detail="Unsupported deployment surface not found")
    acknowledged_keys = _acknowledged_unsupported_surface_keys()
    if acknowledged:
        acknowledged_keys.add(surface_key)
    else:
        acknowledged_keys.discard(surface_key)
    database.update_setting_with_audit(
        "lifecycle_unsupported_surface_acknowledgements",
        json.dumps(sorted(acknowledged_keys)),
        changed_by=changed_by,
    )
    return _unsupported_deployment_surfaces()


def get_lifecycle_status() -> dict:
    """Return the current Instance data lifecycle posture."""
    policies = _stored_retention_policies()
    return {
        "lifecycle_scope": deepcopy(LIFECYCLE_SCOPE),
        "data_classes": _data_classes_with_retention_policies(),
        "content_encryption": content_artifacts.content_encryption_status(),
        "artifact_encryption": _artifact_encryption_status(),
        "secure_erase": deepcopy(SECURE_ERASE_SCOPE),
        "unsupported_deployment_surfaces": _unsupported_deployment_surfaces(),
        "scheduled_retention": {
            "enabled_classes": sorted([
                key
                for key, policy in policies.items()
                if policy.get("enabled") and policy.get("scheduled_enforcement_enabled")
            ]),
        },
        "retention_scheduler": deepcopy(RETENTION_SCHEDULER_SCOPE),
        "audit_coverage": get_audit_coverage_inventory(),
        "deletion_tombstones": database.summarize_deletion_tombstones(),
    }


AUDIT_COVERAGE_INVENTORY = [
    {
        "key": "user_approval_changes",
        "label": "User approval changes",
        "status": "audited",
        "event_family": "user_approval",
        "surface": "ordinary_admin",
    },
    {
        "key": "instance_settings_changes",
        "label": "Instance settings changes",
        "status": "audited",
        "event_family": "instance_settings",
        "surface": "ordinary_admin",
    },
    {
        "key": "user_type_governance",
        "label": "User Type governance",
        "status": "audited",
        "event_family": "user_types",
        "surface": "ordinary_admin",
    },
    {
        "key": "document_actions",
        "label": "Document upload, replacement, access, cleanup, and deletion",
        "status": "audited",
        "event_family": "document_actions",
        "surface": "ordinary_admin",
    },
    {
        "key": "data_deletion_workflows",
        "label": "Lifecycle deletion, retention, and tombstone retry workflows",
        "status": "audited",
        "event_family": "data_deletion",
        "surface": "ordinary_admin",
    },
    {
        "key": "user_memory_admin_actions",
        "label": "Admin-confirmed User Memory create, supersede, and delete",
        "status": "audited",
        "event_family": "user_memories",
        "surface": "ordinary_admin",
    },
    {
        "key": "inference_verification_events",
        "label": "Inference Verification events",
        "status": "audited",
        "event_family": "inference_verification",
        "surface": "operator_security",
    },
    {
        "key": "retrieval_index_internal_writes",
        "label": "Low-level Retrieval Index writes",
        "status": "documented_exception",
        "event_family": None,
        "surface": "internal_reconciliation",
        "exception": "Represented by higher-level Document action and Data Deletion audit events.",
    },
    {
        "key": "read_only_inspection",
        "label": "Constrained read-only inspection paths",
        "status": "documented_exception",
        "event_family": None,
        "surface": "read_only",
        "exception": "Read-only inspection does not mutate Instance state.",
    },
]


def get_audit_coverage_inventory() -> dict:
    items = deepcopy(AUDIT_COVERAGE_INVENTORY)
    missing = [item for item in items if item.get("status") not in {"audited", "documented_exception"}]
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "audited": len([item for item in items if item.get("status") == "audited"]),
            "documented_exceptions": len([
                item for item in items if item.get("status") == "documented_exception"
            ]),
            "missing": len(missing),
            "guardrail_passed": len(missing) == 0,
        },
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
    response = await _get_sage_client().post(
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


def create_session_memory_tombstone(
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


def _retention_policy_days(data_class_key: str, fallback_days: int) -> int:
    policy = _retention_policy_for(data_class_key)
    if policy["enabled"]:
        return int(policy.get("retention_window_days") or fallback_days)
    return fallback_days


def _stale_user_memory_ids(cutoff: datetime) -> list[int]:
    with database.get_cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM user_memories
            WHERE status = 'active'
              AND datetime(updated_at) <= datetime(?)
            ORDER BY updated_at ASC, id ASC
            LIMIT 1000
            """,
            (cutoff.isoformat(),),
        )
        return [int(row["id"]) for row in cursor.fetchall()]


def preview_retention(request: RetentionRunRequest) -> dict:
    now = datetime.utcnow()
    stored_policies = _stored_retention_policies()
    session_memory_policy = _retention_policy_for("sage_session_memory")
    document_artifact_policy = _retention_policy_for("uploaded_document_artifacts")
    user_memory_policy = _retention_policy_for("user_memory")
    audit_log_policy = _retention_policy_for("audit_log")
    conversation_days = _retention_policy_days("sage_session_memory", request.stale_conversation_days)
    document_days = _retention_policy_days("uploaded_document_artifacts", request.document_artifact_days)
    user_memory_days = _retention_policy_days("user_memory", 30)
    audit_log_days = _retention_policy_days("audit_log", 30)
    conversation_cutoff = now - timedelta(days=conversation_days)
    document_cutoff = now - timedelta(days=document_days)
    user_memory_cutoff = now - timedelta(days=user_memory_days)
    audit_log_cutoff = now - timedelta(days=audit_log_days)

    stale_conversations = []
    skipped_conversations = []
    if session_memory_policy["enabled"]:
        with query._sessions_lock:
            for session_id, session in list(query._sessions.items()):
                with query._session_lock(session):
                    last_activity = _session_last_activity(session)
                if last_activity and last_activity <= conversation_cutoff:
                    if database.has_incomplete_deletion_tombstone_for_conversation(session_id):
                        skipped_conversations.append(session_id)
                    else:
                        stale_conversations.append(session_id)

    document_artifacts = []
    if document_artifact_policy["enabled"]:
        job_limit = 1000
        job_offset = 0
        while True:
            jobs = ingest_db.list_jobs(limit=job_limit, offset=job_offset)
            if not jobs:
                break
            for job in jobs:
                reason = ingest._document_artifact_cleanup_reason(job)
                if not reason:
                    continue
                updated_at = _parse_timestamp(job.get("updated_at"))
                if updated_at and updated_at <= document_cutoff:
                    document_artifacts.append({
                        "job_id": job["job_id"],
                        "filename": job.get("filename", "unknown"),
                        "reason": reason,
                    })
            if len(jobs) < job_limit:
                break
            job_offset += job_limit

    user_memories = []
    if user_memory_policy["enabled"]:
        user_memories = _stale_user_memory_ids(user_memory_cutoff)

    audit_log_entries = []
    if audit_log_policy["enabled"]:
        audit_log_entries = database.list_config_audit_log_compaction_candidates(
            audit_log_cutoff.isoformat(),
        )

    skipped_classes = []
    if "sage_session_memory" in stored_policies and not session_memory_policy["enabled"]:
        skipped_classes.append("sage_session_memory")
    if "uploaded_document_artifacts" in stored_policies and not document_artifact_policy["enabled"]:
        skipped_classes.append("uploaded_document_artifacts")
    if "user_memory" in stored_policies and not user_memory_policy["enabled"]:
        skipped_classes.append("user_memory")
    if "audit_log" in stored_policies and not audit_log_policy["enabled"]:
        skipped_classes.append("audit_log")

    return {
        "status": "preview",
        "destructive": False,
        "eligible": {
            "stale_conversations": stale_conversations,
            "document_artifacts": document_artifacts,
            "user_memories": user_memories,
            "audit_log_entries": audit_log_entries,
        },
        "counts": {
            "stale_conversations": len(stale_conversations),
            "document_artifacts": len(document_artifacts),
            "user_memories": len(user_memories),
            "audit_log_entries": len(audit_log_entries),
            "skipped_classes": len(skipped_classes),
        },
        "skipped_conversations": skipped_conversations,
        "skipped_classes": skipped_classes,
    }


async def run_retention(request: RetentionRunRequest, admin: dict) -> dict:
    now = datetime.utcnow()
    stored_policies = _stored_retention_policies()
    session_memory_policy = _retention_policy_for("sage_session_memory")
    document_artifact_policy = _retention_policy_for("uploaded_document_artifacts")
    user_memory_policy = _retention_policy_for("user_memory")
    audit_log_policy = _retention_policy_for("audit_log")
    conversation_cutoff = now - timedelta(
        days=_retention_policy_days("sage_session_memory", request.stale_conversation_days)
    )
    document_cutoff = now - timedelta(
        days=_retention_policy_days("uploaded_document_artifacts", request.document_artifact_days)
    )
    user_memory_cutoff = now - timedelta(days=_retention_policy_days("user_memory", 30))
    audit_log_cutoff = now - timedelta(days=_retention_policy_days("audit_log", 30))
    results = []
    retained = {
        "stale_conversations": [],
        "skipped_conversations": [],
        "document_artifacts": [],
        "user_memories": [],
        "audit_log_entries": 0,
    }

    stale_sessions = []
    if session_memory_policy["enabled"]:
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
    elif "sage_session_memory" in stored_policies:
        results.append(deletion_target_skipped(
            target_kind="lifecycle_data_class",
            target_id="sage_session_memory",
            action="retention_skip_disabled_policy",
            detail="Skipped Sage Session Memory retention because its Data Retention policy is disabled.",
        ))

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

    if document_artifact_policy["enabled"]:
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
    elif "uploaded_document_artifacts" in stored_policies:
        results.append(deletion_target_skipped(
            target_kind="lifecycle_data_class",
            target_id="uploaded_document_artifacts",
            action="retention_skip_disabled_policy",
            detail="Skipped Uploaded Document Artifacts retention because its Data Retention policy is disabled.",
        ))

    if user_memory_policy["enabled"]:
        for memory_id in _stale_user_memory_ids(user_memory_cutoff):
            deleted = database.soft_delete_user_memory(
                memory_id,
                deleted_by_actor=f"retention:{admin.get('pubkey', 'unknown')}",
                deletion_reason="Data Retention policy removed stale User Memory.",
            )
            if deleted:
                retained["user_memories"].append(memory_id)
                results.append(deletion_target_succeeded(
                    target_kind="user_memory",
                    target_id=str(memory_id),
                    action="retention_delete_user_memory",
                    detail="Deleted stale User Memory by Data Retention policy.",
                ))
            else:
                results.append(deletion_target_skipped(
                    target_kind="user_memory",
                    target_id=str(memory_id),
                    action="retention_skip_user_memory",
                    detail="Skipped User Memory because it was no longer active.",
                ))
    elif "user_memory" in stored_policies:
        results.append(deletion_target_skipped(
            target_kind="lifecycle_data_class",
            target_id="user_memory",
            action="retention_skip_disabled_policy",
            detail="Skipped User Memory retention because its Data Retention policy is disabled.",
        ))

    if audit_log_policy["enabled"]:
        compaction = database.compact_config_audit_log_before(
            audit_log_cutoff.isoformat(),
            changed_by=admin.get("pubkey", "unknown"),
        )
        retained["audit_log_entries"] = compaction["compacted_entries"]
        results.append(deletion_target_succeeded(
            target_kind="audit_log",
            target_id=str(compaction["compacted_entries"]),
            action="retention_compact_audit_log",
            detail="Compacted old non-lifecycle Audit Log detail while preserving lifecycle evidence.",
        ))
    elif "audit_log" in stored_policies:
        results.append(deletion_target_skipped(
            target_kind="lifecycle_data_class",
            target_id="audit_log",
            action="retention_skip_disabled_policy",
            detail="Skipped Audit Log retention because its Data Retention policy is disabled.",
        ))

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


async def run_scheduled_retention(request: ScheduledRetentionRunRequest, admin: dict) -> dict:
    scheduled_policies = {
        key: policy
        for key, policy in _stored_retention_policies().items()
        if policy.get("enabled") and policy.get("scheduled_enforcement_enabled")
    }
    enabled_classes = sorted(scheduled_policies.keys())
    if not enabled_classes:
        deletion = summarize_deletion_results([
            deletion_target_skipped(
                target_kind="retention",
                target_id="scheduled",
                action="scheduled_retention_skip_no_enabled_classes",
                detail="No Lifecycle Data Classes have scheduled Retention Execution enabled.",
            )
        ])
        _audit_retention_run(changed_by=admin.get("pubkey", "unknown"), deletion=deletion)
        return {
            "status": "skipped",
            "enabled_classes": [],
            "retry_results": [],
            "retention": {"status": deletion["status"], "deletion": deletion, "retained": {}},
        }

    retention = await run_retention(
        RetentionRunRequest(
            stale_conversation_days=_retention_policy_days("sage_session_memory", 30),
            document_artifact_days=_retention_policy_days("uploaded_document_artifacts", 0),
        ),
        admin,
    )

    retry_results = []
    attempted_retries = 0
    if request.retry_limit > 0:
        for tombstone in database.list_deletion_tombstones(status="incomplete"):
            if len(retry_results) >= request.retry_limit:
                break
            if tombstone["lifecycle_data_class"] != "sage_session_memory":
                continue
            attempted_retries += 1
            deletion = await delete_session_memory_for_conversation({
                "id": tombstone["conversation_id"],
                "agent_runtime": "sage",
                "owner_type": "tombstone",
                "owner_id": tombstone.get("former_subject_ref"),
            })
            new_status = "completed" if deletion["status"] == "succeeded" else "incomplete"
            updated = database.update_deletion_tombstone_after_retry(
                tombstone["id"],
                status=new_status,
                deletion=deletion,
            )
            if updated is not None:
                _audit_deletion_tombstone_retry(
                    changed_by=admin.get("pubkey", "unknown"),
                    tombstone=updated,
                    deletion=deletion,
                )
                retry_results.append({
                    "tombstone_id": updated["id"],
                    "status": updated["status"],
                    "deletion": deletion,
                })

    final_status = retention["status"]
    if attempted_retries > len(retry_results) or any(
        result.get("status") != "completed"
        for result in retry_results
    ):
        final_status = "incomplete"

    return {
        "status": final_status,
        "enabled_classes": enabled_classes,
        "retry_results": retry_results,
        "retention": retention,
    }


@router.get("/status", response_model=dict)
async def get_admin_lifecycle_status(_admin: dict = Depends(auth.require_admin)):
    return get_lifecycle_status()


@router.get("/audit-coverage", response_model=dict)
async def get_admin_audit_coverage(_admin: dict = Depends(auth.require_admin)):
    return get_audit_coverage_inventory()


@router.post("/unsupported-deployment-surfaces/{surface_key}/acknowledgement", response_model=dict)
async def update_admin_unsupported_deployment_surface_acknowledgement(
    surface_key: str,
    request: UnsupportedSurfaceAcknowledgementRequest,
    admin: dict = Depends(auth.require_admin),
):
    return {
        "unsupported_deployment_surfaces": _set_unsupported_surface_acknowledgement(
            surface_key,
            request.acknowledged,
            changed_by=admin.get("pubkey", "unknown"),
        )
    }


@router.put("/retention-policies/{data_class_key}", response_model=dict)
async def update_admin_retention_policy(
    data_class_key: str,
    request: RetentionPolicyUpdateRequest,
    admin: dict = Depends(auth.require_admin),
):
    return {
        "policy": _update_retention_policy(
            data_class_key,
            request,
            changed_by=admin.get("pubkey", "unknown"),
        )
    }


@router.put("/artifact-encryption-posture", response_model=dict)
async def update_admin_artifact_encryption_posture(
    request: ArtifactEncryptionPostureUpdateRequest,
    admin: dict = Depends(auth.require_admin),
):
    posture = request.posture.strip().lower()
    if posture not in {"required", "disabled"}:
        raise HTTPException(status_code=400, detail="Unsupported Artifact Encryption Posture")
    database.upsert_deployment_config(
        content_artifacts.ARTIFACT_ENCRYPTION_KEY,
        posture,
        is_secret=False,
        requires_restart=False,
        category="storage",
        description="Artifact Encryption Posture (required or disabled)",
        changed_by=admin.get("pubkey", "unknown"),
    )
    return {"artifact_encryption": _artifact_encryption_status()}


@router.get("/confidentiality-migration/preview", response_model=dict)
async def preview_admin_confidentiality_migration(_admin: dict = Depends(auth.require_admin)):
    return preview_confidentiality_migration()


@router.post("/confidentiality-migration/execute", response_model=dict)
async def execute_admin_confidentiality_migration(admin: dict = Depends(auth.require_admin)):
    return execute_confidentiality_migration(actor=admin.get("pubkey", "unknown"))


@router.post("/retention/preview", response_model=dict)
async def preview_admin_retention(
    request: RetentionRunRequest,
    _admin: dict = Depends(auth.require_admin),
):
    return preview_retention(request)


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


@router.post("/retention/scheduled/run", response_model=dict)
async def run_admin_scheduled_retention(
    request: ScheduledRetentionRunRequest,
    admin: dict = Depends(auth.require_admin),
):
    return await run_scheduled_retention(request, admin)


@router.post("/retention/scheduled/automation/run", response_model=dict)
async def run_automation_scheduled_retention(
    request: ScheduledRetentionRunRequest,
    machine_actor: dict = Depends(_require_retention_automation_actor),
):
    return await run_scheduled_retention(request, machine_actor)
