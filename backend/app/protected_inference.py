"""Shared gate for Model Provider calls carrying protected product content."""

from __future__ import annotations

import json
from typing import Callable

from inference_verification import fingerprint_claims


PROTECTED_INFERENCE_CONTEXTS = {
    "conversation",
    "rag_query",
    "user_memory_extraction",
    "admin_db_query",
}
DEFAULT_EXPECTED_CLAIMS_FINGERPRINT = fingerprint_claims({})


class ProtectedInferenceBlocked(Exception):
    def __init__(self, *, context: str, status: str) -> None:
        self.context = context
        self.status = status
        super().__init__(
            f"Protected inference is unavailable because Verifiable Inference status is {status}."
        )


class ProtectedInferenceGate:
    def __init__(
        self,
        *,
        current_status: Callable[[], dict],
        audit_block: Callable[..., None],
    ) -> None:
        self.current_status = current_status
        self.audit_block = audit_block

    def require_current(self, *, context: str) -> dict:
        if not inference_requires_verification(context):
            return {"id": None, "bypass": False, "privacy_posture": "not_required"}

        status = self.current_status()
        record = status.get("record")
        if status.get("status") == "current" and record:
            return record

        status_value = str(status.get("status") or "missing")
        self.audit_block(context=context, status=status_value)
        raise ProtectedInferenceBlocked(context=context, status=status_value)


def inference_requires_verification(context: str) -> bool:
    return context in PROTECTED_INFERENCE_CONTEXTS


def inference_verification_reference(record: dict | None) -> dict | None:
    if not record:
        return None
    return {
        "record_id": record.get("id"),
        "provider_identity": record.get("provider_identity"),
        "provider_endpoint": record.get("provider_endpoint"),
        "model_identifier": record.get("model_identifier"),
        "checked_at": record.get("checked_at"),
        "expires_at": record.get("expires_at"),
    }


def require_current_inference_verification(
    *,
    context: str,
    expected_claims_fingerprint: str = DEFAULT_EXPECTED_CLAIMS_FINGERPRINT,
) -> dict:
    import database

    gate = ProtectedInferenceGate(
        current_status=lambda: database.get_current_inference_verification_status_for_config(
            expected_claims_fingerprint=expected_claims_fingerprint,
        ),
        audit_block=audit_blocked_protected_inference,
    )
    return gate.require_current(context=context)


def audit_blocked_protected_inference(*, context: str, status: str) -> None:
    import database

    database.log_config_audit_event(
        table_name="inference_verification",
        config_key="protected_inference_blocked",
        old_value=None,
        new_value=json.dumps({
            "context": context,
            "status": status,
        }, separators=(",", ":")),
        changed_by="system:protected-inference-gate",
    )

