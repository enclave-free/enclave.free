from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SEED_STATUS_PATH = "/data/seed_status.json"
PRODUCTION_ENV_VALUES = {"production", "prod"}
EMBEDDING_TRANSIENT_ERROR_MARKERS = (
    "insufficient_quota",
    "quota",
    "rate limit",
    "429",
    "token limit exceeded",
    "context length",
)


def seed_status_path() -> Path:
    return Path(os.getenv("SEED_STATUS_PATH", DEFAULT_SEED_STATUS_PATH))


def is_production_mode() -> bool:
    for key in ("ENCLAVE_ENV", "APP_ENV", "ENVIRONMENT"):
        value = os.getenv(key, "").strip().lower()
        if value in PRODUCTION_ENV_VALUES:
            return True
    return False


def is_embedding_transient_seed_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in EMBEDDING_TRANSIENT_ERROR_MARKERS)


def should_continue_after_qdrant_seed_failure(exc: BaseException) -> bool:
    return (not is_production_mode()) and is_embedding_transient_seed_error(exc)


def write_seed_status(status: dict[str, Any]) -> dict[str, Any]:
    path = seed_status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, sort_keys=True), encoding="utf-8")
    return status


def write_ready_seed_status() -> dict[str, Any]:
    return write_seed_status({
        "status": "ready",
        "reason": None,
        "message": "Qdrant smoke-test seed is ready.",
    })


def write_degraded_seed_status(exc: BaseException) -> dict[str, Any]:
    return write_seed_status({
        "status": "degraded",
        "reason": "embedding_provider_unavailable",
        "message": (
            "Qdrant seed skipped because the embedding provider is temporarily "
            "unavailable. Startup continues in degraded local-development mode; "
            "retrieval smoke tests will fail until seed succeeds."
        ),
        "error_type": type(exc).__name__,
    })


def read_seed_status() -> dict[str, Any] | None:
    path = seed_status_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None
