"""Runtime posture for Verifiable Inference admin-repair mode."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


_DEFAULT_STATUS = {
    "mode": "unknown",
    "protected_inference_available": False,
    "status": "unknown",
    "reason": "startup_verification_not_run",
    "record_id": None,
    "checked_at": None,
}

_status: dict[str, Any] = deepcopy(_DEFAULT_STATUS)


def reset_inference_repair_status() -> None:
    global _status
    _status = deepcopy(_DEFAULT_STATUS)


def mark_startup_verification_unavailable(*, status: str, reason: str) -> dict:
    global _status
    _status = {
        "mode": "degraded_admin_repair",
        "protected_inference_available": False,
        "status": status,
        "reason": reason,
        "record_id": None,
        "checked_at": _now(),
    }
    return current_inference_repair_status()


def mark_verification_record(record: dict, *, reason: str | None = None) -> dict:
    global _status
    success = record.get("status") == "success"
    _status = {
        "mode": "normal" if success else "degraded_admin_repair",
        "protected_inference_available": success,
        "status": "current" if success else str(record.get("status") or "failed"),
        "reason": reason or ("verification_current" if success else "verification_failed"),
        "record_id": record.get("id"),
        "checked_at": record.get("checked_at") or _now(),
    }
    return current_inference_repair_status()


def current_inference_repair_status() -> dict:
    return deepcopy(_status)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
