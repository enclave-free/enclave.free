"""
Enclave Deployment Configuration Router
Handles environment settings, service health checks, and .env management.
"""

import os
import time
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Final, Mapping, Optional
from urllib.parse import ParseResult, urlparse
from fastapi import APIRouter, Header, HTTPException, Depends, Query, Request
from fastapi.responses import PlainTextResponse

import httpx

import auth
import database
from inference_verification import TinfoilVerifier, fingerprint_claims, verify_and_store
from inference_repair import current_inference_repair_status, mark_startup_verification_unavailable, mark_verification_record
from rate_limit import RateLimiter, rate_limit_backend_status
from models import (
    DeploymentConfigItem,
    DeploymentConfigResponse,
    DeploymentConfigUpdate,
    ServiceHealthItem,
    ServiceHealthResponse,
    DeploymentValidationResponse,
    ConfigAuditLogEntry,
    ConfigAuditLogResponse,
    SuccessResponse,
)

logger = logging.getLogger("enclave.deployment_config")

# Track when this module was loaded (service start time)
# Used to determine which config changes require restart
SERVICE_START_TIME = datetime.now(timezone.utc)

router = APIRouter(prefix="/admin/deployment", tags=["deployment"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

# High-risk export endpoint limiter (best-effort in-memory)
def _parse_rate_limit() -> int:
    try:
        return int(os.getenv("RATE_LIMIT_CONFIG_EXPORT_PER_HOUR", "5"))
    except ValueError:
        return 5

config_export_limiter = RateLimiter(
    limit=_parse_rate_limit(),
    window_seconds=60 * 60,
)


async def check_config_export_rate_limit(request: Request) -> None:
    await config_export_limiter(request)


def current_expected_claims() -> dict:
    """Return the configured expected Verifiable Inference claims for v1."""
    return {}


def current_expected_claims_fingerprint() -> str:
    return fingerprint_claims(current_expected_claims())


def _audit_inference_verification_status_change(event: dict, *, changed_by: str) -> None:
    database.log_config_audit_event(
        table_name="inference_verification",
        config_key="verification_status_changed",
        old_value=None,
        new_value=json.dumps(event, separators=(",", ":")),
        changed_by=changed_by,
    )


def run_startup_inference_verification() -> dict:
    """
    Attempt Verifiable Inference during startup without crash-looping the app.
    Admin repair surfaces remain available if startup verification cannot pass.
    """
    configured = _configured_model_provider()
    api_key = database.get_deployment_config_value("LLM_API_KEY")
    if not api_key:
        logger.warning("Startup Verifiable Inference skipped: LLM_API_KEY not configured")
        return mark_startup_verification_unavailable(
            status="missing",
            reason="LLM_API_KEY not configured",
        )

    try:
        record = verify_and_store(
            verifier=TinfoilVerifier(),
            storage=database,
            expected_claims=current_expected_claims(),
            trigger="startup",
            api_key=api_key,
            audit_status_change=lambda event: _audit_inference_verification_status_change(
                event,
                changed_by="system:startup",
            ),
            **configured,
        )
    except Exception as exc:
        logger.exception("Startup Verifiable Inference failed without a stored record")
        return mark_startup_verification_unavailable(
            status="failed",
            reason=str(exc),
        )

    return mark_verification_record(
        record,
        reason="startup_verification_current" if record.get("status") == "success" else "startup_verification_failed",
    )


def _configured_model_provider() -> dict:
    return {
        "provider_identity": database.get_deployment_config_value("LLM_PROVIDER") or os.getenv("LLM_PROVIDER", "sage"),
        "provider_endpoint": database.get_deployment_config_value("LLM_API_URL") or os.getenv("LLM_API_URL", ""),
        "model_identifier": database.get_deployment_config_value("LLM_MODEL") or os.getenv("LLM_MODEL", ""),
    }


def _dotenv_quote(value: str) -> str:
    """Quote values that would be ambiguous in a dotenv file."""
    if any(char in value for char in (' ', '=', '#', '"', "\\", "\n", "\r", "\t", "$")):
        escaped = (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("$", "\\$")
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'
    return value


def _deployment_config_values_for_export(keys: tuple[str, ...]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in keys:
        meta = ENV_CONFIG_MAP.get(key, {})
        if meta.get("is_secret"):
            values[key] = database.get_deployment_config_value(key) or ""
        else:
            config = database.get_deployment_config(key)
            values[key] = (config or {}).get("value") or meta.get("default") or os.getenv(key, "")
    return values


def _sage_runtime_env_text() -> str:
    values = _deployment_config_values_for_export(SAGE_RUNTIME_ENV_KEYS)
    lines = [
        "# Enclave Sage Runtime Env",
        "# Generated from Deployment Settings.",
        f"# Generated: {datetime.now(timezone.utc).isoformat()}",
        "# Apply by saving as runtime/generated/sage.env and restarting the sage service.",
        "",
    ]
    for source_key, runtime_key in SAGE_RUNTIME_ENV_MAP:
        lines.append(f"{runtime_key}={_dotenv_quote(values.get(source_key, ''))}")
    return "\n".join(lines)


def _core_backend_runtime_env_text() -> str:
    values = _deployment_config_values_for_export(CORE_BACKEND_RUNTIME_ENV_KEYS)
    lines = [
        "# Enclave Core Backend Runtime Env",
        "# Generated from Deployment Settings.",
        f"# Generated: {datetime.now(timezone.utc).isoformat()}",
        "# Apply by saving as runtime/generated/core-backend.env and restarting the core-backend service.",
        "",
    ]
    for source_key, runtime_key in CORE_BACKEND_RUNTIME_ENV_MAP:
        lines.append(f"{runtime_key}={_dotenv_quote(values.get(source_key, ''))}")
    return "\n".join(lines)


def _parse_audit_changed_at(value: Any) -> Optional[datetime]:
    try:
        changed_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=timezone.utc)
        return changed_at
    except (TypeError, ValueError):
        return None


def _latest_audit_marker_from_entries(
    entries: list[Mapping[str, Any]],
    *,
    config_keys: set[str],
) -> Optional[tuple[datetime, int]]:
    latest: Optional[tuple[datetime, int]] = None
    for entry in entries:
        if entry.get("config_key") not in config_keys:
            continue
        changed_at = _parse_audit_changed_at(entry.get("changed_at"))
        if changed_at is None:
            continue
        marker = (changed_at, int(entry.get("id") or 0))
        if latest is None or marker > latest:
            latest = marker
    return latest


def _deployment_config_audit_log() -> list[Mapping[str, Any]]:
    return database.get_config_audit_log(limit=2000, table_name="deployment_config")


def _latest_audit_marker(*, table_name: str, config_keys: set[str]) -> Optional[tuple[datetime, int]]:
    if not config_keys:
        return None
    placeholders = ", ".join("?" for _ in config_keys)
    with database.get_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, changed_at
            FROM config_audit_log
            WHERE table_name = ? AND config_key IN ({placeholders})
            ORDER BY changed_at DESC, id DESC
            LIMIT 1
            """,
            (table_name, *sorted(config_keys)),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    entry = dict(row)
    changed_at = _parse_audit_changed_at(entry.get("changed_at"))
    if changed_at is None:
        return None
    return changed_at, int(entry.get("id") or 0)


def _sage_runtime_env_status(audit_log: Optional[list[Mapping[str, Any]]] = None) -> dict[str, Any]:
    return _generated_runtime_env_status(
        export_key=SAGE_RUNTIME_ENV_EXPORT_KEY,
        source_keys=SAGE_RUNTIME_ENV_KEYS,
        audit_log=audit_log,
    )


def _core_backend_runtime_env_status(audit_log: Optional[list[Mapping[str, Any]]] = None) -> dict[str, Any]:
    return _generated_runtime_env_status(
        export_key=CORE_BACKEND_RUNTIME_ENV_EXPORT_KEY,
        source_keys=CORE_BACKEND_RUNTIME_ENV_KEYS,
        audit_log=audit_log,
    )


def _generated_runtime_env_status(
    *,
    export_key: str,
    source_keys: tuple[str, ...],
    audit_log: Optional[list[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    if audit_log is None:
        latest_export = _latest_audit_marker(
            table_name="deployment_config",
            config_keys={export_key},
        )
        latest_source_change = _latest_audit_marker(
            table_name="deployment_config",
            config_keys=set(source_keys),
        )
    else:
        latest_export = _latest_audit_marker_from_entries(
            audit_log,
            config_keys={export_key},
        )
        latest_source_change = _latest_audit_marker_from_entries(
            audit_log,
            config_keys=set(source_keys),
        )
    if latest_export is None:
        return {
            "status": "not_generated",
            "latest_export_at": None,
            "latest_source_change_at": latest_source_change[0].isoformat() if latest_source_change else None,
        }
    stale = latest_source_change is not None and latest_source_change > latest_export
    return {
        "status": "stale" if stale else "current",
        "latest_export_at": latest_export[0].isoformat(),
        "latest_source_change_at": latest_source_change[0].isoformat() if latest_source_change else None,
    }


def _runtime_env_comparison_status(
    running_sage_config: Optional[Mapping[str, Any]] = None,
    running_core_backend_config: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    audit_log = _deployment_config_audit_log()
    generated = _sage_runtime_env_status(audit_log)
    restart = _restart_required_status(audit_log)
    desired = _deployment_config_values_for_export(SAGE_RUNTIME_ENV_KEYS)
    configured_desired = sum(1 for value in desired.values() if str(value or "").strip())
    desired_fingerprint = _desired_sage_runtime_fingerprint()
    running_status = "restart_required" if restart["restart_required"] else "not_directly_introspected"
    running_fingerprint = None
    if running_sage_config is not None:
        running_fingerprint = _running_sage_runtime_fingerprint(running_sage_config)
        running_status = "matches_desired" if running_fingerprint == desired_fingerprint else "drifted"
    core_backend_desired = _deployment_config_values_for_export(CORE_BACKEND_RUNTIME_ENV_KEYS)
    configured_core_backend_desired = sum(1 for value in core_backend_desired.values() if str(value or "").strip())
    core_backend_desired_fingerprint = _desired_core_backend_runtime_fingerprint()
    core_backend_running_status = "not_directly_introspected"
    core_backend_running_fingerprint = None
    if running_core_backend_config is not None:
        core_backend_running_fingerprint = _running_core_backend_runtime_fingerprint(running_core_backend_config)
        core_backend_running_status = (
            "matches_desired"
            if core_backend_running_fingerprint == core_backend_desired_fingerprint
            else "drifted"
        )
    return {
        "sage": {
            "desired": {
                "status": "configured" if configured_desired else "not_configured",
                "configured_keys": configured_desired,
                "total_keys": len(SAGE_RUNTIME_ENV_KEYS),
                "fingerprint": desired_fingerprint,
            },
            "generated": generated,
            "running": {
                "status": running_status,
                "summary": (
                    "Sage running runtime config matches desired Deployment Settings."
                    if running_status == "matches_desired"
                    else "Sage running runtime config differs from desired Deployment Settings."
                    if running_status == "drifted"
                    else
                    "Restart-required Deployment Settings changed since service start."
                    if restart["restart_required"]
                    else "Sage live runtime env is not directly introspected in this slice; use service health plus generated env freshness."
                ),
                "fingerprint": running_fingerprint,
                "changed_keys_requiring_restart": [item["key"] for item in restart["changed_keys"]],
            },
        },
        "core_backend": {
            "desired": {
                "status": "configured" if configured_core_backend_desired else "not_configured",
                "configured_keys": configured_core_backend_desired,
                "total_keys": len(CORE_BACKEND_RUNTIME_ENV_KEYS),
                "fingerprint": core_backend_desired_fingerprint,
            },
            "generated": _core_backend_runtime_env_status(audit_log),
            "running": {
                "status": core_backend_running_status,
                "summary": (
                    "Core backend running runtime config matches desired Deployment Settings."
                    if core_backend_running_status == "matches_desired"
                    else "Core backend running runtime config differs from desired Deployment Settings."
                    if core_backend_running_status == "drifted"
                    else "Core backend live runtime env is not directly introspected yet; use generated env freshness."
                ),
                "fingerprint": core_backend_running_fingerprint,
            },
        },
    }


def _runtime_config_fingerprint(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_origin_for_sage(value: str) -> str:
    parsed = urlparse(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return value.strip().rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _desired_sage_runtime_fingerprint() -> str:
    values = _deployment_config_values_for_export(SAGE_RUNTIME_ENV_KEYS)
    origins = [
        _normalize_origin_for_sage(origin)
        for origin in (values.get("CORS_ORIGINS") or "").split(",")
        if origin.strip()
    ]
    frontend_url = values.get("FRONTEND_URL") or ""
    frontend_origin = _normalize_origin_for_sage(frontend_url) if frontend_url else ""
    if frontend_origin and frontend_origin not in origins:
        origins.append(frontend_origin)
    payload = {
        "TINFOIL_API_URL": values.get("LLM_API_URL") or "",
        "TINFOIL_API_KEY": {
            "configured": bool(values.get("LLM_API_KEY")),
            "fingerprint": hashlib.sha256((values.get("LLM_API_KEY") or "").encode("utf-8")).hexdigest()
            if values.get("LLM_API_KEY")
            else None,
        },
        "TINFOIL_MODEL": values.get("LLM_MODEL") or "",
        "TINFOIL_EMBEDDING_MODEL": values.get("EMBEDDING_MODEL") or "",
        "FRONTEND_URL": frontend_url or None,
        "CORS_ORIGINS": origins,
        "SEARXNG_URL": values.get("SEARXNG_URL") or "",
    }
    return _runtime_config_fingerprint(payload)


def _desired_core_backend_runtime_fingerprint() -> str:
    values = _deployment_config_values_for_export(CORE_BACKEND_RUNTIME_ENV_KEYS)
    origins = [
        _normalize_origin_for_sage(origin)
        for origin in (values.get("CORS_ORIGINS") or "").split(",")
        if origin.strip()
    ]
    frontend_url = values.get("FRONTEND_URL") or ""
    frontend_origin = _normalize_origin_for_sage(frontend_url) if frontend_url else ""
    if frontend_origin and frontend_origin not in origins:
        origins.append(frontend_origin)
    payload = {
        "LLM_API_URL": values.get("LLM_API_URL") or "",
        "LLM_API_KEY": {
            "configured": bool(values.get("LLM_API_KEY")),
            "fingerprint": hashlib.sha256((values.get("LLM_API_KEY") or "").encode("utf-8")).hexdigest()
            if values.get("LLM_API_KEY")
            else None,
        },
        "LLM_MODEL": values.get("LLM_MODEL") or "",
        "EMBEDDING_MODEL": values.get("EMBEDDING_MODEL") or "",
        "FRONTEND_URL": frontend_url or None,
        "CORS_ORIGINS": origins,
        "SEARXNG_URL": values.get("SEARXNG_URL") or "",
    }
    return _runtime_config_fingerprint(payload)


def _running_sage_runtime_fingerprint(runtime_config: Mapping[str, Any]) -> str:
    raw_origins = runtime_config.get("CORS_ORIGINS")
    origins = [
        _normalize_origin_for_sage(origin)
        for origin in raw_origins
        if isinstance(origin, str) and origin.strip()
    ] if isinstance(raw_origins, list) else []
    payload = {
        "TINFOIL_API_URL": runtime_config.get("TINFOIL_API_URL") or "",
        "TINFOIL_API_KEY": runtime_config.get("TINFOIL_API_KEY") or {"configured": False, "fingerprint": None},
        "TINFOIL_MODEL": runtime_config.get("TINFOIL_MODEL") or "",
        "TINFOIL_EMBEDDING_MODEL": runtime_config.get("TINFOIL_EMBEDDING_MODEL") or "",
        "FRONTEND_URL": runtime_config.get("FRONTEND_URL"),
        "CORS_ORIGINS": origins,
        "SEARXNG_URL": runtime_config.get("SEARXNG_URL") or "",
    }
    return _runtime_config_fingerprint(payload)


def _running_core_backend_runtime_fingerprint(runtime_config: Mapping[str, Any]) -> str:
    raw_origins = runtime_config.get("CORS_ORIGINS")
    origins = [
        _normalize_origin_for_sage(origin)
        for origin in raw_origins
        if isinstance(origin, str) and origin.strip()
    ] if isinstance(raw_origins, list) else []
    payload = {
        "LLM_API_URL": runtime_config.get("LLM_API_URL") or "",
        "LLM_API_KEY": runtime_config.get("LLM_API_KEY") or {"configured": False, "fingerprint": None},
        "LLM_MODEL": runtime_config.get("LLM_MODEL") or "",
        "EMBEDDING_MODEL": runtime_config.get("EMBEDDING_MODEL") or "",
        "FRONTEND_URL": runtime_config.get("FRONTEND_URL"),
        "CORS_ORIGINS": origins,
        "SEARXNG_URL": runtime_config.get("SEARXNG_URL") or "",
    }
    return _runtime_config_fingerprint(payload)


def _core_backend_runtime_config_payload() -> dict[str, Any]:
    values = _deployment_config_values_for_export(CORE_BACKEND_RUNTIME_ENV_KEYS)
    origins = [
        _normalize_origin_for_sage(origin)
        for origin in (values.get("CORS_ORIGINS") or "").split(",")
        if origin.strip()
    ]
    frontend_url = values.get("FRONTEND_URL") or ""
    frontend_origin = _normalize_origin_for_sage(frontend_url) if frontend_url else ""
    if frontend_origin and frontend_origin not in origins:
        origins.append(frontend_origin)
    return {
        "LLM_API_URL": values.get("LLM_API_URL") or "",
        "LLM_API_KEY": {
            "configured": bool(values.get("LLM_API_KEY")),
            "fingerprint": hashlib.sha256((values.get("LLM_API_KEY") or "").encode("utf-8")).hexdigest()
            if values.get("LLM_API_KEY")
            else None,
        },
        "LLM_MODEL": values.get("LLM_MODEL") or "",
        "EMBEDDING_MODEL": values.get("EMBEDDING_MODEL") or "",
        "FRONTEND_URL": frontend_url or None,
        "CORS_ORIGINS": origins,
        "SEARXNG_URL": values.get("SEARXNG_URL") or "",
    }


def fetch_running_core_backend_config() -> dict[str, Any]:
    raw_origins = os.getenv("CORS_ORIGINS", "")
    origins = [
        _normalize_origin_for_sage(origin)
        for origin in raw_origins.split(",")
        if origin.strip()
    ]
    frontend_url = os.getenv("FRONTEND_URL", "")
    frontend_origin = _normalize_origin_for_sage(frontend_url) if frontend_url else ""
    if frontend_origin and frontend_origin not in origins:
        origins.append(frontend_origin)
    api_key = os.getenv("LLM_API_KEY", "")
    return {
        "LLM_API_URL": os.getenv("LLM_API_URL", ""),
        "LLM_API_KEY": {
            "configured": bool(api_key),
            "fingerprint": hashlib.sha256(api_key.encode("utf-8")).hexdigest() if api_key else None,
        },
        "LLM_MODEL": os.getenv("LLM_MODEL", ""),
        "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", ""),
        "FRONTEND_URL": frontend_url or None,
        "CORS_ORIGINS": origins,
        "SEARXNG_URL": os.getenv("SEARXNG_URL", ""),
    }


def _require_internal_agent_token(x_internal_agent_token: Optional[str]) -> None:
    expected = os.getenv("INTERNAL_AGENT_TOKEN", "")
    if not expected or x_internal_agent_token != expected:
        raise HTTPException(status_code=403, detail="Invalid internal agent token")


async def _fetch_sage_running_runtime_config() -> Optional[Mapping[str, Any]]:
    runtime_url = (os.getenv("SAGE_WEB_URL", "http://sage:3000")).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            fingerprint_resp = await client.get(
                runtime_url + "/internal/runtime-config/fingerprint",
                headers={"X-Internal-Agent-Token": os.getenv("INTERNAL_AGENT_TOKEN", "")},
            )
        if fingerprint_resp.status_code == 200:
            return (fingerprint_resp.json() or {}).get("runtime_config") or {}
        logger.warning("Agent Runtime fingerprint check returned %s", fingerprint_resp.status_code)
    except (httpx.RequestError, ValueError) as e:
        logger.warning(f"Agent Runtime fingerprint check failed: {e}")
    return None


# Environment variable to config key mapping
# These are the keys we allow managing through the UI
ENV_CONFIG_MAP = {
    # Python-side Model Provider deployment metadata.
    # LLM_* names are not live Sage Agent Settings.
    "LLM_PROVIDER": {"category": "llm", "description": "Model Provider label for Python diagnostics and verification metadata", "requires_restart": True, "default": "sage"},
    "LLM_MODEL": {"category": "llm", "description": "Model identifier for Python diagnostics and verification metadata", "requires_restart": False},
    "LLM_API_URL": {"category": "llm", "description": "Model Provider API base URL for Python diagnostics and verification metadata", "requires_restart": True},
    "LLM_API_KEY": {"category": "llm", "description": "Model Provider API key for Python diagnostics and verification metadata", "requires_restart": False, "is_secret": True},
    # Embedding Settings
    "EMBEDDING_PROVIDER": {"category": "embedding", "description": "Embedding provider: tinfoil or local", "requires_restart": True, "default": "tinfoil"},
    "EMBEDDING_MODEL": {"category": "embedding", "description": "Embedding model identifier", "requires_restart": True, "default": "nomic-embed-text"},
    "EMBEDDING_API_URL": {"category": "embedding", "description": "OpenAI-compatible embedding API base URL", "requires_restart": True, "default": "http://tinfoil-proxy:8089/v1"},
    "EMBEDDING_API_KEY": {"category": "embedding", "description": "Embedding API key", "requires_restart": True, "is_secret": True},
    # Email Settings (no defaults - optional, user must configure)
    "SMTP_HOST": {"category": "email", "description": "SMTP server hostname", "requires_restart": False},
    "SMTP_PORT": {"category": "email", "description": "SMTP server port", "requires_restart": False},
    "SMTP_USER": {"category": "email", "description": "SMTP username", "requires_restart": False, "is_secret": True},
    "SMTP_PASS": {"category": "email", "description": "SMTP password", "requires_restart": False, "is_secret": True},
    "SMTP_FROM": {"category": "email", "description": "From email address", "requires_restart": False},
    "MOCK_EMAIL": {"category": "email", "description": "Enable mock email mode", "requires_restart": False},
    # SMTP test status keys (internal, set by test-email endpoint)
    "SMTP_LAST_TEST_SUCCESS": {"category": "email", "description": "Whether last SMTP test was successful", "requires_restart": False},
    "SMTP_LAST_TEST_AT": {"category": "email", "description": "Timestamp of last SMTP test", "requires_restart": False},
    # Storage Settings
    "SQLITE_PATH": {"category": "storage", "description": "SQLite database path", "requires_restart": True, "default": "/data/enclave.db"},
    "UPLOADS_DIR": {"category": "storage", "description": "Uploads directory path", "requires_restart": True, "default": "/uploads"},
    "CONTENT_ENCRYPTION_KEY": {"category": "storage", "description": "Deployment-held key for backend-readable active content encryption", "requires_restart": False, "is_secret": True},
    "DOCUMENT_ARTIFACT_ENCRYPTION": {"category": "storage", "description": "Artifact Encryption Posture (auto, required, or disabled)", "requires_restart": False, "default": "auto"},
    # Qdrant Settings
    "QDRANT_HOST": {"category": "storage", "description": "Qdrant server hostname", "requires_restart": True, "default": "qdrant"},
    "QDRANT_PORT": {"category": "storage", "description": "Qdrant server port", "requires_restart": True, "default": "6333"},
    # Search Settings
    "SEARXNG_URL": {"category": "search", "description": "SearXNG instance URL", "requires_restart": False, "default": "http://searxng:8080"},
    # Security Settings
    "FRONTEND_URL": {"category": "security", "description": "Frontend application URL", "requires_restart": False, "default": "http://localhost:5173"},
    "RATE_LIMIT_CHAT_PER_MINUTE": {"category": "security", "description": "Chat requests per minute", "requires_restart": True, "default": "120"},
    "RATE_LIMIT_QUERY_PER_MINUTE": {"category": "security", "description": "Retrieval query requests per minute", "requires_restart": True, "default": "90"},
    "RATE_LIMIT_UPLOAD_PER_MINUTE": {"category": "security", "description": "Document upload requests per minute", "requires_restart": True, "default": "20"},
    "RATE_LIMIT_VECTOR_SEARCH_PER_MINUTE": {"category": "security", "description": "Vector search requests per minute", "requires_restart": True, "default": "30"},
    "RATE_LIMIT_CONFIG_EXPORT_PER_HOUR": {"category": "security", "description": "Deployment config exports per hour", "requires_restart": True, "default": "5"},
    "RATE_LIMIT_BACKEND": {"category": "security", "description": "Shared rate limit backend: memory or valkey", "requires_restart": True, "default": "memory"},
    "RATE_LIMIT_VALKEY_URL": {"category": "security", "description": "Self-hosted Valkey URL for shared rate limits", "requires_restart": True, "default": "redis://valkey:6379/0", "is_secret": True},
    # Retrieval compatibility settings. RAG_* names remain stable public config keys.
    "RAG_TOP_K": {"category": "llm", "description": "Default Retrieval count", "requires_restart": False, "default": "8"},
    "PDF_EXTRACT_MODE": {"category": "llm", "description": "PDF extraction mode (fast/quality)", "requires_restart": False, "default": "fast"},
    # Domain & URLs Settings
    "BASE_DOMAIN": {"category": "domains", "description": "Root domain name", "requires_restart": False, "default": "localhost"},
    "INSTANCE_URL": {"category": "domains", "description": "Full application URL with protocol", "requires_restart": True, "default": "http://localhost:5173"},
    "API_BASE_URL": {"category": "domains", "description": "API subdomain URL (optional)", "requires_restart": True, "default": "http://localhost:8000"},
    "ADMIN_BASE_URL": {"category": "domains", "description": "Admin panel subdomain URL (optional)", "requires_restart": True, "default": "http://localhost:5173/admin"},
    "EMAIL_DOMAIN": {"category": "domains", "description": "Domain for email addresses", "requires_restart": False, "default": "localhost"},
    "DKIM_SELECTOR": {"category": "domains", "description": "DKIM DNS record selector", "requires_restart": False, "default": "enclave"},
    "SPF_INCLUDE": {"category": "domains", "description": "SPF DNS include directive (e.g., include:_spf.google.com)", "requires_restart": False, "default": ""},
    "DMARC_POLICY": {"category": "domains", "description": "DMARC DNS policy record", "requires_restart": False, "default": "v=DMARC1; p=none"},
    "CORS_ORIGINS": {"category": "domains", "description": "Comma-separated allowed CORS origins", "requires_restart": True, "default": "http://localhost:5173"},
    "CDN_DOMAINS": {"category": "domains", "description": "Content delivery domains", "requires_restart": False},
    "CUSTOM_SEARXNG_URL": {"category": "domains", "description": "Private SearXNG instance URL", "requires_restart": True},
    "WEBHOOK_BASE_URL": {"category": "domains", "description": "Webhook callback base URL", "requires_restart": False, "default": "http://localhost:8000"},
    # SSL & Security Settings
    "TRUSTED_PROXIES": {"category": "ssl", "description": "Trusted reverse proxies (cloudflare, aws, custom)", "requires_restart": True},
    "SSL_CERT_PATH": {"category": "ssl", "description": "SSL certificate file path", "requires_restart": True},
    "SSL_KEY_PATH": {"category": "ssl", "description": "SSL private key file path", "requires_restart": True, "is_secret": True},
    "FORCE_HTTPS": {"category": "ssl", "description": "Redirect HTTP to HTTPS", "requires_restart": True, "default": "false"},
    "HSTS_MAX_AGE": {"category": "ssl", "description": "HSTS max-age in seconds", "requires_restart": False, "default": "31536000"},
    "MONITORING_URL": {"category": "general", "description": "Health monitoring endpoint URL", "requires_restart": False, "default": "http://localhost:8000/health"},
}

# Keys that should never be exposed or editable
FORBIDDEN_KEYS = {"SECRET_KEY", "DATABASE_URL", "ADMIN_PRIVATE_KEY"}

# Allowed table names for audit log queries (prevents SQL injection)
ALLOWED_AUDIT_TABLES = {
    "deployment_config",
    "ai_config",
    "ai_config_user_type_overrides",
    "document_defaults",
    "document_defaults_user_type_overrides",
    "document_actions",
    "data_deletion",
    "inference_verification",
    "instance_settings",
    "conversation_trace",
    "user_approval",
    "user_memories",
    "user_types",
}

RATE_LIMIT_KEYS: Final[set[str]] = {
    "RATE_LIMIT_CHAT_PER_MINUTE",
    "RATE_LIMIT_QUERY_PER_MINUTE",
    "RATE_LIMIT_UPLOAD_PER_MINUTE",
    "RATE_LIMIT_VECTOR_SEARCH_PER_MINUTE",
    "RATE_LIMIT_CONFIG_EXPORT_PER_HOUR",
}

SAGE_RUNTIME_ENV_EXPORT_KEY: Final[str] = "sage_runtime_env_export"
SAGE_RUNTIME_ENV_KEYS: Final[tuple[str, ...]] = (
    "LLM_API_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMBEDDING_MODEL",
    "FRONTEND_URL",
    "CORS_ORIGINS",
    "SEARXNG_URL",
)
SAGE_RUNTIME_ENV_MAP: Final[tuple[tuple[str, str], ...]] = (
    ("LLM_API_URL", "TINFOIL_API_URL"),
    ("LLM_API_KEY", "TINFOIL_API_KEY"),
    ("LLM_MODEL", "TINFOIL_MODEL"),
    ("EMBEDDING_MODEL", "TINFOIL_EMBEDDING_MODEL"),
    ("FRONTEND_URL", "FRONTEND_URL"),
    ("CORS_ORIGINS", "CORS_ORIGINS"),
    ("SEARXNG_URL", "SEARXNG_URL"),
)

CORE_BACKEND_RUNTIME_ENV_EXPORT_KEY: Final[str] = "core_backend_runtime_env_export"
CORE_BACKEND_RUNTIME_ENV_KEYS: Final[tuple[str, ...]] = (
    "LLM_API_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMBEDDING_MODEL",
    "FRONTEND_URL",
    "CORS_ORIGINS",
    "SEARXNG_URL",
)
CORE_BACKEND_RUNTIME_ENV_MAP: Final[tuple[tuple[str, str], ...]] = (
    ("LLM_API_URL", "LLM_API_URL"),
    ("LLM_API_KEY", "LLM_API_KEY"),
    ("LLM_MODEL", "LLM_MODEL"),
    ("EMBEDDING_MODEL", "EMBEDDING_MODEL"),
    ("FRONTEND_URL", "FRONTEND_URL"),
    ("CORS_ORIGINS", "CORS_ORIGINS"),
    ("SEARXNG_URL", "SEARXNG_URL"),
)

PRODUCTION_UNSAFE_FLAGS: Final[tuple[str, ...]] = (
    "MOCK_EMAIL",
)

PRODUCTION_UNSAFE_ENV_FLAGS: Final[tuple[str, ...]] = (
    "SIMULATE_USER_AUTH",
    "SIMULATE_ADMIN_AUTH",
    "PROTECTED_INFERENCE_DEVELOPMENT_BYPASS",
)

WEAK_SECRET_KEY_VALUES: Final[set[str]] = {
    "",
    "change-me",
    "changeme",
    "secret",
    "test-secret",
    "replace-this-with-a-long-random-secret",
    "your-secret-key-here",
}

OPERATIONAL_READINESS = {
    "runtime_alerting": [
        {
            "category": "repeated_auth_failures",
            "owner": "operator",
            "evidence_source": "Audit Log, gateway access logs, and auth failure logs",
            "verification": "Configure alert rules for repeated magic-link, session, or admin authentication failures and record an alert drill.",
        },
        {
            "category": "unusual_admin_actions",
            "owner": "operator",
            "evidence_source": "Audit Log records for admin configuration, lifecycle, export, and database-inspection actions",
            "verification": "Configure alert rules for unusual admin action volume, off-hours changes, or high-risk settings changes and record an alert drill.",
        },
        {
            "category": "destructive_endpoint_usage",
            "owner": "operator",
            "evidence_source": "Audit Log records, gateway logs, and application logs for deletion, compaction, migration, and purge endpoints",
            "verification": "Configure alert rules for destructive endpoint calls and record an alert drill before production use.",
        },
    ],
    "backup_restore_verification": {
        "cadence": "quarterly and before production upgrades or storage migrations",
        "targets": [
            {
                "target": "sqlite_database",
                "verification": "Restore the SQLite database into an isolated environment and verify schema migrations and admin login.",
            },
            {
                "target": "deployment_config",
                "verification": "Restore deployment configuration and secret references without exposing secret values in drill evidence.",
            },
            {
                "target": "uploads_directory",
                "verification": "Restore uploaded artifacts and verify document listing, download, and lifecycle deletion behavior.",
            },
            {
                "target": "retrieval_index",
                "verification": "Restore or rebuild the retrieval index and confirm query hydration resolves chunk text from product storage.",
            },
        ],
        "evidence": "Record restore drill date, operator, environment, targets covered, result, and follow-up actions in the security checklist or operations log.",
    },
    "incident_response": {
        "runbooks": {
            "incident_response": "docs/operational-monitoring-and-recovery.md",
            "key_recovery": "docs/admin-key-recovery-runbook.md",
        },
        "verification": "Run tabletop drills for auth abuse, destructive action review, backup restore, and admin key recovery.",
    },
    "drill_evidence": "Update docs/security-data-protection-checklist.md with the latest alert and restore drill evidence.",
}


def _config_to_item(config: dict) -> DeploymentConfigItem:
    """Convert database row to DeploymentConfigItem"""
    return DeploymentConfigItem(
        key=config["key"],
        value=config["value"],
        is_secret=bool(config.get("is_secret")),
        requires_restart=bool(config.get("requires_restart")),
        category=config["category"],
        description=config.get("description"),
        updated_at=config.get("updated_at"),
    )


def _truthy_config_value(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "on"}


def _deployment_config_value(config_dict: Mapping[str, str], key: str) -> Optional[str]:
    value = config_dict.get(key)
    if value not in (None, ""):
        return value
    return os.getenv(key)


def _parsed_url(value: Optional[str]) -> Optional[ParseResult]:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return None
    return parsed


def _is_local_or_internal_url(value: Optional[str]) -> bool:
    parsed = _parsed_url(value)
    if parsed is None:
        return False
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    if "." not in host:
        return True
    return host.endswith(".local") or host.endswith(".internal")


def _url_scheme(value: Optional[str]) -> str:
    parsed = _parsed_url(value)
    return parsed.scheme.lower() if parsed else ""


def _secret_key_is_strong(secret_key: Optional[str]) -> bool:
    value = str(secret_key or "").strip()
    if value.lower() in WEAK_SECRET_KEY_VALUES:
        return False
    return len(value) >= 32


def _sync_env_to_db() -> None:
    """
    Sync current environment variables to the database.
    Only syncs keys that are in ENV_CONFIG_MAP and don't already exist in DB.
    """
    for key, meta in ENV_CONFIG_MAP.items():
        if key in FORBIDDEN_KEYS:
            continue

        existing = database.get_deployment_config(key)
        # Try to get value from env.
        value = os.getenv(key)

        if key == "LLM_PROVIDER":
            value = (value or meta.get("default", "sage") or "sage").strip().lower()
            if value not in {"sage"}:
                value = "sage"

        # 4. Fall back to default from config map
        if value is None:
            value = meta.get("default", "")

        if existing:
            # Backfill empty values with defaults/env values
            existing_value = existing.get("value")
            should_backfill_value = (
                (existing_value is None or existing_value == "")
                and value not in (None, "")
            )
            # Keep metadata in sync for known one-off category corrections.
            should_sync_metadata = (
                key == "MONITORING_URL" and existing.get("category") != meta["category"]
            )
            should_force_supported_provider = (
                key == "LLM_PROVIDER"
                and str(existing_value or "").strip().lower() not in {"sage"}
            )

            if should_backfill_value or should_sync_metadata or should_force_supported_provider:
                value_to_store = "sage" if should_force_supported_provider else (existing_value if existing_value not in (None, "") else value)
                database.upsert_deployment_config(
                    key=key,
                    value=value_to_store,
                    is_secret=meta.get("is_secret", False),
                    requires_restart=meta.get("requires_restart", False),
                    category=meta["category"],
                    description=meta.get("description", ""),
                )
                if should_backfill_value:
                    logger.debug(f"Backfilled empty config: {key} (value: {'***' if meta.get('is_secret') else value_to_store})")
                elif should_sync_metadata:
                    logger.debug(f"Synchronized config metadata: {key} (category -> {meta['category']})")
                elif should_force_supported_provider:
                    logger.info("Normalized LLM_PROVIDER to sage during startup sync")
            continue

        database.upsert_deployment_config(
            key=key,
            value=value,
            is_secret=meta.get("is_secret", False),
            requires_restart=meta.get("requires_restart", False),
            category=meta["category"],
            description=meta.get("description", ""),
        )
        logger.debug(f"Synced env var to DB: {key} (value: {'***' if meta.get('is_secret') else value})")


@router.on_event("startup")
async def startup_sync() -> None:
    """Sync environment variables to database on startup"""
    _sync_env_to_db()


@router.get("/config", response_model=DeploymentConfigResponse)
async def get_deployment_config(admin: dict = Depends(auth.require_admin)):
    """
    Get all deployment configuration grouped by category.
    Secret values are masked.
    Requires admin authentication.
    """
    # Note: env sync happens at startup via lifespan hook - no need to sync on every read

    all_config = database.get_all_deployment_config()

    response = DeploymentConfigResponse()
    for config in all_config:
        if config["key"] not in ENV_CONFIG_MAP:
            continue
        item = _config_to_item(config)
        category = config["category"]

        if category == "llm":
            response.llm.append(item)
        elif category == "embedding":
            response.embedding.append(item)
        elif category == "email":
            response.email.append(item)
        elif category == "storage":
            response.storage.append(item)
        elif category == "security":
            response.security.append(item)
        elif category == "search":
            response.search.append(item)
        elif category == "domains":
            response.domains.append(item)
        elif category == "ssl":
            response.ssl.append(item)
        else:
            response.general.append(item)

    return response


@router.get("/inference-verification/status", response_model=dict)
async def get_inference_verification_status(admin: dict = Depends(auth.require_admin)):
    """
    Get current Verifiable Inference status for the configured Model Provider.
    Requires admin authentication.
    """
    configured = _configured_model_provider()
    status = database.get_current_inference_verification_status(
        **configured,
        expected_claims_fingerprint=current_expected_claims_fingerprint(),
    )
    return {
        **status,
        "configured_provider": configured,
        "expected_claims_fingerprint": current_expected_claims_fingerprint(),
        "repair": current_inference_repair_status(),
    }


@router.get("/inference-verification/records", response_model=dict)
async def list_inference_verification_records(
    limit: int = Query(default=100, ge=1, le=500),
    admin: dict = Depends(auth.require_admin),
):
    """
    List Inference Verification Record metadata without full attestation material.
    Requires admin authentication.
    """
    return {"records": database.list_inference_verification_records(limit=limit)}


@router.get("/inference-verification/records/{record_id}", response_model=dict)
async def get_inference_verification_record(record_id: int, admin: dict = Depends(auth.require_admin)):
    """
    Fetch a single Inference Verification Record including full attestation material.
    Requires admin authentication.
    """
    record = database.get_inference_verification_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Inference Verification Record not found")
    return record


@router.post("/inference-verification/verify", response_model=dict)
async def verify_inference_now(admin: dict = Depends(auth.require_admin)):
    """
    Run manual Verifiable Inference for the configured Model Provider.
    Requires admin authentication.
    """
    configured = _configured_model_provider()
    api_key = database.get_deployment_config_value("LLM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="LLM_API_KEY not configured")
    changed_by = admin.get("pubkey", "admin")
    record = verify_and_store(
        verifier=TinfoilVerifier(),
        storage=database,
        expected_claims=current_expected_claims(),
        trigger="manual",
        api_key=api_key,
        audit_status_change=lambda event: _audit_inference_verification_status_change(event, changed_by=changed_by),
        **configured,
    )
    mark_verification_record(
        record,
        reason="manual_verification_current" if record.get("status") == "success" else "manual_verification_failed",
    )
    database.log_config_audit_event(
        table_name="inference_verification",
        config_key="manual_verification",
        old_value=None,
        new_value=json.dumps({
            "record_id": record.get("id"),
            "status": record.get("status"),
            "trigger": record.get("trigger"),
        }, separators=(",", ":")),
        changed_by=changed_by,
    )
    return record


@router.get("/config/export", response_class=PlainTextResponse)
async def export_env_file(
    request: Request,
    admin: dict = Depends(auth.require_admin),
    _: None = Depends(check_config_export_rate_limit),
):
    """
    Export current configuration as .env file format.
    Secret values are included (not masked).
    Requires admin authentication.
    """
    logger.warning(
        "High-risk config export requested by admin=%s from ip=%s",
        admin.get("pubkey", "unknown"),
        request.client.host if request.client else "unknown",
    )
    lines = ["# Enclave Configuration Export", f"# Generated: {datetime.now(timezone.utc).isoformat()}", ""]

    # Get raw values from database (not masked)
    with database.get_cursor() as cursor:
        cursor.execute("SELECT * FROM deployment_config ORDER BY category, key")
        configs = [dict(row) for row in cursor.fetchall()]

    current_category = None
    for config in configs:
        if config["key"] in FORBIDDEN_KEYS:
            continue

        # Add category header
        if config["category"] != current_category:
            if current_category is not None:
                lines.append("")
            lines.append(f"# {config['category'].upper()}")
            current_category = config["category"]

        if config.get("is_secret"):
            value = database.get_deployment_config_value(config["key"]) or ""
        else:
            value = config["value"] or ""
        lines.append(f"{config['key']}={_dotenv_quote(value)}")

    # Explicitly audit high-risk export action.
    # old/new values are intentionally omitted to avoid logging secret material.
    database.log_config_audit_event(
        table_name="deployment_config",
        config_key=".env_export",
        old_value=None,
        new_value=(
            f"exported_keys={len([c for c in configs if c.get('key') not in FORBIDDEN_KEYS])};"
            f"ip={request.client.host if request.client else 'unknown'}"
        ),
        changed_by=admin.get("pubkey", "unknown"),
    )

    return "\n".join(lines)


@router.get("/runtime-env/sage", response_class=PlainTextResponse)
@router.get("/config/runtime-env/sage", response_class=PlainTextResponse)
async def export_sage_runtime_env(
    request: Request,
    admin: dict = Depends(auth.require_admin),
    _: None = Depends(check_config_export_rate_limit),
):
    """
    Export the Sage runtime env generated from Deployment Settings.
    Secret values are included so the artifact must be handled as sensitive deployment material.
    """
    logger.warning(
        "Sage runtime env export requested by admin=%s from ip=%s",
        admin.get("pubkey", "unknown"),
        request.client.host if request.client else "unknown",
    )
    content = _sage_runtime_env_text()
    database.log_config_audit_event(
        table_name="deployment_config",
        config_key=SAGE_RUNTIME_ENV_EXPORT_KEY,
        old_value=None,
        new_value=(
            f"exported_keys={len(SAGE_RUNTIME_ENV_MAP)};"
            f"ip={request.client.host if request.client else 'unknown'}"
        ),
        changed_by=admin.get("pubkey", "unknown"),
    )
    return content


@router.get("/runtime-env/core-backend", response_class=PlainTextResponse)
@router.get("/config/runtime-env/core-backend", response_class=PlainTextResponse)
async def export_core_backend_runtime_env(
    request: Request,
    admin: dict = Depends(auth.require_admin),
    _: None = Depends(check_config_export_rate_limit),
):
    """
    Export the core-backend runtime env generated from Deployment Settings.
    Secret values are included so the artifact must be handled as sensitive deployment material.
    """
    logger.warning(
        "Core backend runtime env export requested by admin=%s from ip=%s",
        admin.get("pubkey", "unknown"),
        request.client.host if request.client else "unknown",
    )
    content = _core_backend_runtime_env_text()
    database.log_config_audit_event(
        table_name="deployment_config",
        config_key=CORE_BACKEND_RUNTIME_ENV_EXPORT_KEY,
        old_value=None,
        new_value=(
            f"exported_keys={len(CORE_BACKEND_RUNTIME_ENV_MAP)};"
            f"ip={request.client.host if request.client else 'unknown'}"
        ),
        changed_by=admin.get("pubkey", "unknown"),
    )
    return content


@internal_router.get("/runtime-config/fingerprint", response_model=dict)
async def get_core_backend_runtime_config_fingerprint(
    x_internal_agent_token: Optional[str] = Header(default=None),
) -> dict:
    """
    Return safe core-backend runtime config for internal alignment checks.
    Secret-bearing values are represented by configured/fingerprint metadata only.
    """
    _require_internal_agent_token(x_internal_agent_token)
    return {
        "service": "core-backend",
        "runtime_config": fetch_running_core_backend_config(),
    }


@router.get("/config/{key}", response_model=DeploymentConfigItem)
async def get_deployment_config_by_key(key: str, admin: dict = Depends(auth.require_admin)):
    """
    Get a single deployment config value.
    Secret values are masked.
    Requires admin authentication.
    """
    if key in FORBIDDEN_KEYS:
        raise HTTPException(status_code=403, detail="Access to this key is forbidden")
    if key not in ENV_CONFIG_MAP:
        raise HTTPException(status_code=404, detail=f"Config key not found: {key}")

    config = database.get_deployment_config(key)
    if not config:
        raise HTTPException(status_code=404, detail=f"Config key not found: {key}")

    return _config_to_item(config)


@router.get("/config/{key}/reveal")
async def reveal_deployment_config_secret(key: str, admin: dict = Depends(auth.require_admin)):
    """
    Get the unmasked value of a secret config key.
    Only works for keys marked as secrets.
    Requires admin authentication.
    """
    if key in FORBIDDEN_KEYS:
        raise HTTPException(status_code=403, detail="Access to this key is forbidden")

    # Check database first for consistency with get_deployment_config_by_key
    config = database.get_deployment_config(key)
    if not config:
        raise HTTPException(status_code=404, detail=f"Config key not found: {key}")

    # Validate it's a secret using ENV_CONFIG_MAP metadata
    meta = ENV_CONFIG_MAP.get(key)
    if not meta or not meta.get("is_secret"):
        raise HTTPException(status_code=400, detail="This key is not a secret")

    # Get unmasked value using internal function
    value = database.get_deployment_config_value(key)

    return {"key": key, "value": value or ""}


@router.put("/config/{key}", response_model=DeploymentConfigItem)
async def update_deployment_config_value(
    key: str,
    update: DeploymentConfigUpdate,
    admin: dict = Depends(auth.require_admin)
):
    """
    Update a deployment config value.
    Note: Changes may require service restart to take effect.
    Requires admin authentication.
    """
    if key in FORBIDDEN_KEYS:
        raise HTTPException(status_code=403, detail="This key cannot be modified")

    if key not in ENV_CONFIG_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown config key: {key}")

    meta = ENV_CONFIG_MAP[key]
    value_to_save = update.value

    # For secret keys, preserve existing value if new value is empty/whitespace.
    if meta.get("is_secret") and (not value_to_save or not value_to_save.strip()):
        existing_value = database.get_deployment_config_value(key)
        if existing_value:
            value_to_save = existing_value
            logger.debug(f"Preserving existing secret value for {key} (empty value submitted)")

    # Validate specific keys (only if we have a real value to validate)
    if key in ("SMTP_PORT", "QDRANT_PORT") and value_to_save:
        try:
            port = int(value_to_save)
            if port < 1 or port > 65535:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=400, detail="Port must be between 1 and 65535")

    # Normalize and validate SMTP hostname-ish fields.
    # Users often paste `"smtp.example.com"` (quotes become literal in some env loaders)
    # or `smtp.example.com:587` (port belongs in SMTP_PORT).
    if key in ("SMTP_HOST", "SMTP_USER", "SMTP_FROM") and isinstance(value_to_save, str):
        value_to_save = value_to_save.strip()
        if len(value_to_save) >= 2 and value_to_save[0] == value_to_save[-1] and value_to_save[0] in ("'", '"'):
            value_to_save = value_to_save[1:-1].strip()

    if key == "SMTP_HOST" and value_to_save:
        if "://" in value_to_save or "/" in value_to_save:
            raise HTTPException(
                status_code=400,
                detail="SMTP_HOST must be a hostname only (e.g., smtp.example.com) without protocol or path",
            )
        # Detect common host:port paste (allow IPv6 which contains multiple colons).
        if isinstance(value_to_save, str) and value_to_save.count(":") == 1:
            host_part, port_part = value_to_save.rsplit(":", 1)
            if host_part and port_part.isdigit():
                raise HTTPException(
                    status_code=400,
                    detail="SMTP_HOST should not include a port. Put the port in SMTP_PORT instead.",
                )

    if key == "RAG_TOP_K" and value_to_save:
        try:
            top_k = int(value_to_save)
            if top_k < 1 or top_k > 100:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=400, detail="RAG_TOP_K must be between 1 and 100")

    if key in RATE_LIMIT_KEYS:
        if not value_to_save or value_to_save.strip() == "":
            raise HTTPException(status_code=400, detail=f"{key} must be a positive integer")
        try:
            rate_limit = int(value_to_save)
            if rate_limit < 1:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{key} must be a positive integer") from None

    if key == "RATE_LIMIT_BACKEND":
        normalized_backend = str(value_to_save or "").strip().lower()
        if normalized_backend not in {"memory", "valkey"}:
            raise HTTPException(status_code=400, detail="RATE_LIMIT_BACKEND must be memory or valkey")
        value_to_save = normalized_backend

    # URL validation for URL-type fields
    URL_KEYS = {"INSTANCE_URL", "API_BASE_URL", "ADMIN_BASE_URL", "CUSTOM_SEARXNG_URL",
                "WEBHOOK_BASE_URL", "MONITORING_URL"}
    if key in URL_KEYS and value_to_save:
        from urllib.parse import urlparse
        parsed = urlparse(value_to_save)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail=f"{key} must be a valid URL with protocol (e.g., https://example.com)")

    # Domain validation
    DOMAIN_KEYS = {"BASE_DOMAIN", "EMAIL_DOMAIN"}
    if key in DOMAIN_KEYS and value_to_save:
        import re
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(domain_pattern, value_to_save):
            raise HTTPException(status_code=400, detail=f"{key} must be a valid domain name")

    # HSTS max-age validation
    if key == "HSTS_MAX_AGE" and value_to_save:
        try:
            hsts = int(value_to_save)
            if hsts < 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=400, detail="HSTS_MAX_AGE must be a non-negative integer")

    # Boolean validation for FORCE_HTTPS
    if key == "FORCE_HTTPS" and value_to_save:
        if value_to_save.lower() not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
            raise HTTPException(status_code=400, detail="FORCE_HTTPS must be a boolean value (true/false, 1/0, yes/no, on/off)")

    if key == "LLM_PROVIDER":
        normalized = str(value_to_save or "").strip().lower()
        if normalized not in ("", "sage"):
            raise HTTPException(status_code=400, detail='LLM_PROVIDER only supports "sage"')
        value_to_save = normalized or "sage"

    # Get admin pubkey for audit log
    admin_pubkey = admin.get("pubkey")
    if not admin_pubkey:
        logger.warning("Admin pubkey not found in auth context for config update")
        admin_pubkey = "unknown"

    # Upsert the config (atomic create-or-update)
    database.upsert_deployment_config(
        key=key,
        value=value_to_save,
        is_secret=meta.get("is_secret", False),
        requires_restart=meta.get("requires_restart", False),
        category=meta["category"],
        description=meta.get("description", ""),
        changed_by=admin_pubkey,
    )

    # If SMTP config changed, reset test status so user re-verifies
    smtp_keys = {"SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"}
    if key in smtp_keys:
        try:
            database.upsert_deployment_config(
                key="SMTP_LAST_TEST_SUCCESS",
                value="false",
                is_secret=False,
                requires_restart=False,
                category="email",
                description="Whether last SMTP test was successful",
                changed_by=admin_pubkey,
            )
            logger.info(f"SMTP test status reset due to {key} change")
        except Exception as e:
            logger.warning(f"Failed to reset SMTP test status after {key} change: {e}")

    # Invalidate config cache so changes take effect immediately
    try:
        from config_loader import invalidate_cache
        invalidate_cache()
        logger.info(f"Config cache invalidated after updating {key}")
    except ImportError as e:
        logger.debug(f"config_loader not available, skipping cache invalidation: {e}")

    # Return updated config
    updated = database.get_deployment_config(key)
    if not updated:
        raise HTTPException(status_code=500, detail="Config updated but could not be retrieved")
    return _config_to_item(updated)


def _validate_config_values(config_dict: Mapping[str, str]) -> DeploymentValidationResponse:
    errors = []
    warnings = []

    # Check required settings
    required = ["LLM_PROVIDER", "QDRANT_HOST", "QDRANT_PORT"]
    for key in required:
        if not config_dict.get(key):
            errors.append(f"Missing required setting: {key}")

    # Check port values
    for port_key in ["SMTP_PORT", "QDRANT_PORT"]:
        if config_dict.get(port_key):
            try:
                port = int(config_dict[port_key])
                if port < 1 or port > 65535:
                    errors.append(f"{port_key} must be between 1 and 65535")
            except ValueError:
                errors.append(f"{port_key} must be a number")

    # Warnings for common issues
    mock_email_enabled = _truthy_config_value(_deployment_config_value(config_dict, "MOCK_EMAIL"))
    if mock_email_enabled:
        warnings.append("MOCK_EMAIL is enabled - emails will not be sent")

    # Check for SSL configuration consistency
    ssl_cert = config_dict.get("SSL_CERT_PATH", "")
    ssl_key = config_dict.get("SSL_KEY_PATH", "")
    force_https = _truthy_config_value(_deployment_config_value(config_dict, "FORCE_HTTPS"))

    if auth.is_production_mode():
        for key in PRODUCTION_UNSAFE_FLAGS:
            if _truthy_config_value(_deployment_config_value(config_dict, key)):
                errors.append(f"{key} must be disabled in production")
        for key in PRODUCTION_UNSAFE_ENV_FLAGS:
            if _truthy_config_value(os.getenv(key)):
                errors.append(f"{key} must be disabled in production")
        if not _secret_key_is_strong(os.getenv("SECRET_KEY")):
            errors.append("SECRET_KEY must be strong, stable, and managed outside the image in production")
        if os.getenv("SESSION_COOKIE_SECURE", "").strip().lower() in {"false", "0", "no", "off"}:
            errors.append("SESSION_COOKIE_SECURE must not be disabled in production")
        if _truthy_config_value(os.getenv("BACKEND_RELOAD")):
            errors.append("BACKEND_RELOAD must be disabled in production")
        published_service_host = os.getenv("PUBLISHED_SERVICE_HOST", "").strip()
        if published_service_host in {"0.0.0.0", "::"}:
            warnings.append(
                f"Published service host {published_service_host} requires an explicit production exposure review"
            )
        rate_limit_backend = (
            _deployment_config_value(config_dict, "RATE_LIMIT_BACKEND")
            or os.getenv("RATE_LIMIT_BACKEND", "memory")
        ).strip().lower()
        if rate_limit_backend != "valkey":
            errors.append("RATE_LIMIT_BACKEND must be valkey in production")
        if not (_deployment_config_value(config_dict, "RATE_LIMIT_VALKEY_URL") or os.getenv("RATE_LIMIT_VALKEY_URL", "")).strip():
            errors.append("RATE_LIMIT_VALKEY_URL must be configured in production")
        for key in ("INSTANCE_URL", "API_BASE_URL", "ADMIN_BASE_URL", "FRONTEND_URL"):
            url = _deployment_config_value(config_dict, key)
            if url and not _is_local_or_internal_url(url) and _url_scheme(url) != "https":
                errors.append(f"{key} must use HTTPS in production")
        if not force_https:
            errors.append("FORCE_HTTPS must be enabled in production")
        try:
            if int(_deployment_config_value(config_dict, "HSTS_MAX_AGE") or "0") < 31536000:
                errors.append("HSTS_MAX_AGE must be at least 31536000 in production")
        except ValueError:
            errors.append("HSTS_MAX_AGE must be a non-negative integer")
        if not (_deployment_config_value(config_dict, "TRUSTED_PROXIES") or "").strip():
            warnings.append("TRUSTED_PROXIES should name the TLS-terminating reverse proxy in production")
        for key in ("LLM_API_URL", "EMBEDDING_API_URL"):
            url = _deployment_config_value(config_dict, key)
            if url and not _is_local_or_internal_url(url) and _url_scheme(url) != "https":
                errors.append(f"{key} must use HTTPS for external provider endpoints in production")

    if not config_dict.get("SMTP_HOST") and not mock_email_enabled:
        warnings.append("SMTP not configured - email features will not work")

    if not config_dict.get("SEARXNG_URL"):
        warnings.append("SEARXNG_URL not configured - web search will not work")

    if force_https and (not ssl_cert or not ssl_key):
        warnings.append("FORCE_HTTPS is enabled but SSL certificate paths are not configured")

    if ssl_cert and not ssl_key:
        warnings.append("SSL_CERT_PATH is set but SSL_KEY_PATH is missing")

    if ssl_key and not ssl_cert:
        warnings.append("SSL_KEY_PATH is set but SSL_CERT_PATH is missing")

    # Check CORS origins match configured domains
    cors_origins_raw = config_dict.get("CORS_ORIGINS", "")
    instance_url = config_dict.get("INSTANCE_URL", "").rstrip("/")
    if instance_url and cors_origins_raw:
        # Parse comma-separated origins and normalize (strip whitespace and trailing slashes)
        cors_origins_list = [origin.strip().rstrip("/") for origin in cors_origins_raw.split(",") if origin.strip()]
        if instance_url not in cors_origins_list:
            warnings.append("INSTANCE_URL is not included in CORS_ORIGINS - this may cause CORS errors")

    return DeploymentValidationResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


@router.post("/config/validate", response_model=DeploymentValidationResponse)
async def validate_config(admin: dict = Depends(auth.require_admin)) -> DeploymentValidationResponse:
    """
    Validate current configuration.
    Checks for required values and valid formats.
    Requires admin authentication.
    """
    all_config = database.get_all_deployment_config()
    config_dict = {c["key"]: c["value"] for c in all_config}
    return _validate_config_values(config_dict)


@router.get("/operational-readiness")
async def get_operational_readiness(admin: dict = Depends(auth.require_admin)) -> Dict[str, Any]:
    """
    Expose operator-owned monitoring, restore, and incident drill expectations.
    Requires admin authentication.
    """
    return OPERATIONAL_READINESS


def _readiness_item(
    *,
    key: str,
    label: str,
    source: str,
    severity: str,
    status: str,
    summary: str,
    next_action: str,
    conversation_blocking: bool = False,
) -> dict:
    return {
        "key": key,
        "label": label,
        "source": source,
        "severity": severity,
        "status": status,
        "summary": summary,
        "next_action": next_action,
        "conversation_blocking": conversation_blocking,
    }


def _deployment_validation_readiness_items() -> list[dict]:
    all_config = database.get_all_deployment_config()
    config_dict = {c["key"]: c["value"] for c in all_config}
    validation = _validate_config_values(config_dict)
    items: list[dict] = []
    if validation.errors:
        items.append(_readiness_item(
            key="deployment_settings_validation",
            label="Deployment Settings Validation",
            source="deployment_validation",
            severity="blocker",
            status="invalid",
            summary="Deployment Settings validation has errors that must be repaired.",
            next_action="Review Deployment Settings validation errors.",
        ))
    elif validation.warnings:
        items.append(_readiness_item(
            key="deployment_settings_validation",
            label="Deployment Settings Validation",
            source="deployment_validation",
            severity="warning",
            status="warnings",
            summary="Deployment Settings validation has advisory warnings.",
            next_action="Review Deployment Settings validation warnings.",
        ))
    else:
        items.append(_readiness_item(
            key="deployment_settings_validation",
            label="Deployment Settings Validation",
            source="deployment_validation",
            severity="ready",
            status="valid",
            summary="Deployment Settings validation has no errors or warnings.",
            next_action="No action required.",
        ))
    return items


def _inference_readiness_item() -> dict:
    configured = _configured_model_provider()
    status = database.get_current_inference_verification_status(
        **configured,
        expected_claims_fingerprint=current_expected_claims_fingerprint(),
    )
    status_key = status.get("status", "missing")
    if status_key == "current":
        return _readiness_item(
            key="verifiable_inference",
            label="Verifiable Inference",
            source="inference_verification",
            severity="ready",
            status=status_key,
            summary="Current Verifiable Inference evidence is available for normal Conversations.",
            next_action="No action required.",
        )
    return _readiness_item(
        key="verifiable_inference",
        label="Verifiable Inference",
        source="inference_verification",
        severity="warning",
        status=f"deferred_{status_key}",
        summary="Verifiable Inference is deferred for this prototype and is not required for normal Conversations.",
        next_action="Track Verifiable Inference as post-prototype hardening; verification can still be reviewed or run manually.",
    )


def _unacknowledged_deployment_surface_labels(lifecycle_status: dict) -> list[str]:
    categories = lifecycle_status.get("unsupported_deployment_surface_categories") or []
    unacknowledged_categories = [
        category.get("label") or category.get("category") or "Unsupported Deployment Surface category"
        for category in categories
        if not category.get("acknowledged")
    ]
    surfaces = lifecycle_status.get("unsupported_deployment_surfaces") or []
    unacknowledged_surfaces = [
        surface.get("label") or surface.get("key") or "Unsupported Deployment Surface"
        for surface in surfaces
        if not surface.get("acknowledged")
    ]
    return [*unacknowledged_categories, *unacknowledged_surfaces]


def _lifecycle_readiness_item(lifecycle_status: dict) -> dict:
    readiness = lifecycle_status.get("lifecycle_readiness") or {}
    status = readiness.get("status", "needs_review")
    unacknowledged_surfaces = _unacknowledged_deployment_surface_labels(lifecycle_status)
    if status == "reviewed" and not unacknowledged_surfaces:
        return _readiness_item(
            key="lifecycle_readiness",
            label="Data Lifecycle Review",
            source="lifecycle_readiness",
            severity="ready",
            status=status,
            summary=readiness.get("summary") or "Data Lifecycle Review has been completed.",
            next_action="No action required.",
        )
    if unacknowledged_surfaces:
        summary = (
            f"Data Lifecycle Review needs Admin review and "
            f"{len(unacknowledged_surfaces)} unsupported Deployment Surface acknowledgements."
        )
        next_action = "Review Data Lifecycle Status and acknowledge unsupported Deployment Surfaces."
    else:
        summary = readiness.get("summary") or "Data Lifecycle Review needs Admin review."
        next_action = "Review Data Lifecycle Status."
    return _readiness_item(
        key="lifecycle_readiness",
        label="Data Lifecycle Review",
        source="lifecycle_readiness",
        severity="warning",
        status=status,
        summary=summary,
        next_action=next_action,
    )


def _unsupported_surface_readiness_item(lifecycle_status: dict) -> dict:
    unacknowledged = _unacknowledged_deployment_surface_labels(lifecycle_status)
    if not unacknowledged:
        return _readiness_item(
            key="deployment_surface_acknowledgements",
            label="Deployment Surface Acknowledgements",
            source="deployment_surfaces",
            severity="ready",
            status="acknowledged",
            summary="Unsupported Deployment Surface categories have been acknowledged.",
            next_action="No action required.",
        )
    return _readiness_item(
        key="deployment_surface_acknowledgements",
        label="Deployment Surface Acknowledgements",
        source="deployment_surfaces",
        severity="warning",
        status="needs_acknowledgement",
        summary=f"{len(unacknowledged)} unsupported Deployment Surface entries need acknowledgement.",
        next_action="Acknowledge unsupported Deployment Surface categories after review.",
    )


def _backup_restore_readiness_item() -> dict:
    return _readiness_item(
        key="backup_restore_drill",
        label="Backup And Restore Drill",
        source="operational_readiness",
        severity="warning",
        status="operator_evidence_required",
        summary=OPERATIONAL_READINESS["backup_restore_verification"]["evidence"],
        next_action="Record a restore drill for the Single-Instance Deployment.",
    )


def _restart_readiness_item() -> dict:
    restart = _restart_required_status()
    if restart["restart_required"]:
        changed = ", ".join(item["key"] for item in restart["changed_keys"])
        return _readiness_item(
            key="restart_required",
            label="Restart Required",
            source="restart_required",
            severity="warning",
            status="restart_required",
            summary=f"Runtime restart is required for changed Deployment Settings: {changed}.",
            next_action="Restart the affected service after reviewing changes.",
        )
    return _readiness_item(
        key="restart_required",
        label="Restart Required",
        source="restart_required",
        severity="ready",
        status="current",
        summary="No restart-required Deployment Settings have changed since service start.",
        next_action="No action required.",
    )


def _runtime_env_readiness_item(running_sage_config: Optional[Mapping[str, Any]] = None) -> dict:
    comparison = _runtime_env_comparison_status(running_sage_config)
    sage = comparison["sage"]
    generated_status = sage["generated"]["status"]
    running_status = sage["running"]["status"]
    if generated_status == "current" and running_status == "matches_desired":
        return _readiness_item(
            key="sage_runtime_env",
            label="Sage Runtime Config",
            source="runtime_env",
            severity="ready",
            status="matches_desired",
            summary="Running Sage runtime config matches desired Deployment Settings.",
            next_action="No action required.",
        )
    if generated_status == "current" and running_status == "drifted":
        return _readiness_item(
            key="sage_runtime_env",
            label="Sage Runtime Config",
            source="runtime_env",
            severity="warning",
            status="drifted",
            summary="Running Sage runtime config differs from desired Deployment Settings.",
            next_action="Investigate Sage runtime config drift, apply the generated Sage env, and restart Sage.",
        )
    if generated_status == "current":
        return _readiness_item(
            key="sage_runtime_env",
            label="Sage Runtime Config",
            source="runtime_env",
            severity="ready",
            status="current",
            summary="Sage runtime env has been generated from current Deployment Settings.",
            next_action="No action required unless the generated artifact has not been applied to the Deployment.",
        )
    if generated_status == "stale":
        return _readiness_item(
            key="sage_runtime_env",
            label="Sage Runtime Config",
            source="runtime_env",
            severity="warning",
            status="stale",
            summary="Deployment Settings changed after the Sage runtime env was generated.",
            next_action="Export a fresh Sage runtime env and apply it through the Deployment restart path.",
        )
    return _readiness_item(
        key="sage_runtime_env",
        label="Sage Runtime Config",
        source="runtime_env",
        severity="warning",
        status="not_generated",
        summary="Sage runtime env has not been generated from Deployment Settings yet.",
        next_action="Export the Sage runtime env before treating Deployment Settings as applied to Sage.",
    )


def _core_backend_runtime_env_readiness_item(
    running_core_backend_config: Optional[Mapping[str, Any]] = None,
) -> dict:
    comparison = _runtime_env_comparison_status(
        running_core_backend_config=running_core_backend_config
    )
    core_backend = comparison["core_backend"]
    generated_status = core_backend["generated"]["status"]
    running_status = core_backend["running"]["status"]
    if generated_status == "current" and running_status == "matches_desired":
        return _readiness_item(
            key="core_backend_runtime_env",
            label="Core Backend Runtime Config",
            source="runtime_env",
            severity="ready",
            status="matches_desired",
            summary="Running core-backend runtime config matches desired Deployment Settings.",
            next_action="No action required.",
        )
    if generated_status == "current" and running_status == "drifted":
        return _readiness_item(
            key="core_backend_runtime_env",
            label="Core Backend Runtime Config",
            source="runtime_env",
            severity="warning",
            status="drifted",
            summary="Running core-backend runtime config differs from desired Deployment Settings.",
            next_action="Investigate core-backend runtime config drift, apply the generated core-backend env, and restart core-backend.",
        )
    if generated_status == "current":
        return _readiness_item(
            key="core_backend_runtime_env",
            label="Core Backend Runtime Config",
            source="runtime_env",
            severity="ready",
            status="current",
            summary="Core-backend runtime env has been generated from current Deployment Settings.",
            next_action="No action required unless the generated artifact has not been applied to the Deployment.",
        )
    if generated_status == "stale":
        return _readiness_item(
            key="core_backend_runtime_env",
            label="Core Backend Runtime Config",
            source="runtime_env",
            severity="warning",
            status="stale",
            summary="Deployment Settings changed after the core-backend runtime env was generated.",
            next_action="Export a fresh core-backend runtime env and apply it through the Deployment restart path.",
        )
    return _readiness_item(
        key="core_backend_runtime_env",
        label="Core Backend Runtime Config",
        source="runtime_env",
        severity="warning",
        status="not_generated",
        summary="Core-backend runtime env has not been generated from Deployment Settings yet.",
        next_action="Export the core-backend runtime env before treating Deployment Settings as applied to core-backend.",
    )


def _restart_required_status(audit_log: Optional[list[Mapping[str, Any]]] = None) -> dict[str, Any]:
    restart_keys = database.get_restart_required_keys()
    if audit_log is None:
        audit_log = _deployment_config_audit_log()

    changed_requiring_restart = []
    for entry in audit_log:
        if entry["config_key"] in restart_keys:
            changed_at = _parse_audit_changed_at(entry.get("changed_at"))
            if changed_at is not None and changed_at > SERVICE_START_TIME:
                changed_requiring_restart.append({
                    "key": entry["config_key"],
                    "changed_at": entry["changed_at"],
                })

    return {
        "restart_required": len(changed_requiring_restart) > 0,
        "changed_keys": changed_requiring_restart[:10],
    }


def deployment_readiness_summary() -> dict:
    from lifecycle import get_lifecycle_status

    lifecycle_status = get_lifecycle_status()
    items = [
        *_deployment_validation_readiness_items(),
        _inference_readiness_item(),
        _lifecycle_readiness_item(lifecycle_status),
        _backup_restore_readiness_item(),
        _restart_readiness_item(),
    ]
    blockers = sum(1 for item in items if item["severity"] == "blocker")
    warnings = sum(1 for item in items if item["severity"] == "warning")
    ready = sum(1 for item in items if item["severity"] == "ready")
    return {
        "status": "blocked" if blockers else ("warnings" if warnings else "ready"),
        "summary": {
            "blockers": blockers,
            "warnings": warnings,
            "ready": ready,
            "total": len(items),
        },
        "items": items,
    }


@router.get("/readiness", response_model=dict)
async def get_deployment_readiness(admin: dict = Depends(auth.require_admin)) -> dict:
    """
    Summarize Deployment Readiness for a Single-Instance Deployment.
    Requires admin authentication.
    """
    return deployment_readiness_summary()


@router.get("/health", response_model=ServiceHealthResponse)
async def get_service_health(admin: dict = Depends(auth.require_admin)):
    """
    Get health status of all connected services.
    Requires admin authentication.
    """
    services = []
    all_config = database.get_all_deployment_config()
    config_dict = {c["key"]: c["value"] for c in all_config}

    # Check Qdrant
    qdrant_host = config_dict.get("QDRANT_HOST") or os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = config_dict.get("QDRANT_PORT") or os.getenv("QDRANT_PORT", "6333")
    try:
        start = time.time()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"http://{qdrant_host}:{qdrant_port}/collections")
        response_time = int((time.time() - start) * 1000)
        services.append(ServiceHealthItem(
            name="Qdrant",
            status="healthy" if resp.status_code == 200 else "unhealthy",
            response_time_ms=response_time,
            last_checked=datetime.now(timezone.utc).isoformat(),
        ))
    except Exception as e:
        logger.warning(f"Qdrant health check failed: {e}")
        services.append(ServiceHealthItem(
            name="Qdrant",
            status="unhealthy",
            last_checked=datetime.now(timezone.utc).isoformat(),
            error="Connection failed",
        ))

    # Check Sage Agent Runtime / router.
    provider = (config_dict.get("LLM_PROVIDER") or os.getenv("LLM_PROVIDER", "sage")).strip().lower() or "sage"
    runtime_url = (os.getenv("SAGE_WEB_URL", "http://sage:3000")).rstrip("/")
    llm_health_url = runtime_url + "/health"
    sage_runtime_config: Optional[Mapping[str, Any]] = None

    try:
        start = time.time()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(llm_health_url)
            if resp.status_code == 200:
                sage_runtime_config = await _fetch_sage_running_runtime_config()
        response_time = int((time.time() - start) * 1000)
        services.append(ServiceHealthItem(
            name=f"AI Runtime ({provider})",
            status="healthy" if resp.status_code == 200 else "unhealthy",
            response_time_ms=response_time,
            last_checked=datetime.now(timezone.utc).isoformat(),
        ))
    except httpx.RequestError as e:
        logger.warning(f"Agent Runtime ({provider}) health check failed: {e}")
        services.append(ServiceHealthItem(
            name=f"AI Runtime ({provider})",
            status="unhealthy",
            last_checked=datetime.now(timezone.utc).isoformat(),
            error="Connection failed",
        ))

    # Check Tinfoil proxy when configured
    tinfoil_url = config_dict.get("LLM_API_URL") or os.getenv("LLM_API_URL", "")
    if tinfoil_url:
        try:
            start = time.time()
            tinfoil_models_url = f"{tinfoil_url.rstrip('/')}/models"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(tinfoil_models_url)
            response_time = int((time.time() - start) * 1000)
            services.append(ServiceHealthItem(
                name="Tinfoil Proxy",
                status="healthy" if resp.status_code == 200 else "unhealthy",
                response_time_ms=response_time,
                last_checked=datetime.now(timezone.utc).isoformat(),
            ))
        except Exception as e:
            logger.warning(f"Tinfoil proxy health check failed: {e}")
            services.append(ServiceHealthItem(
                name="Tinfoil Proxy",
                status="unhealthy",
                last_checked=datetime.now(timezone.utc).isoformat(),
                error="Connection failed",
            ))

    # Check SearXNG
    searxng_url = config_dict.get("SEARXNG_URL") or os.getenv("SEARXNG_URL", "")
    if searxng_url:
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{searxng_url.rstrip('/')}/healthz")
            response_time = int((time.time() - start) * 1000)
            services.append(ServiceHealthItem(
                name="SearXNG",
                status="healthy" if resp.status_code == 200 else "unhealthy",
                response_time_ms=response_time,
                last_checked=datetime.now(timezone.utc).isoformat(),
            ))
        except Exception as e:
            logger.warning(f"SearXNG health check failed: {e}")
            services.append(ServiceHealthItem(
                name="SearXNG",
                status="unhealthy",
                last_checked=datetime.now(timezone.utc).isoformat(),
                error="Connection failed",
            ))
    else:
        services.append(ServiceHealthItem(
            name="SearXNG",
            status="unknown",
            last_checked=datetime.now(timezone.utc).isoformat(),
            error="Not configured",
        ))

    rate_limit_status = await rate_limit_backend_status()
    if rate_limit_status["status"] in {"healthy", "local_only"}:
        rate_limit_health = "healthy" if rate_limit_status["status"] == "healthy" else "unknown"
    else:
        rate_limit_health = "unhealthy"
    services.append(ServiceHealthItem(
        name="Shared Rate Limit Store",
        status=rate_limit_health,
        last_checked=datetime.now(timezone.utc).isoformat(),
        error=None if rate_limit_status["status"] == "healthy" else rate_limit_status["summary"],
    ))

    # Check SMTP (if configured)
    smtp_host = config_dict.get("SMTP_HOST") or os.getenv("SMTP_HOST", "")
    mock_smtp = (config_dict.get("MOCK_EMAIL") or os.getenv("MOCK_EMAIL", "")).lower() == "true"

    if mock_smtp:
        services.append(ServiceHealthItem(
            name="SMTP",
            status="unknown",
            last_checked=datetime.now(timezone.utc).isoformat(),
            error="Mock mode enabled",
        ))
    elif smtp_host:
        # Check for recent successful test
        last_test_at = config_dict.get("SMTP_LAST_TEST_AT")
        last_test_success = config_dict.get("SMTP_LAST_TEST_SUCCESS") == "true"

        if last_test_success and last_test_at:
            # Show as healthy with last test time
            services.append(ServiceHealthItem(
                name="SMTP",
                status="healthy",
                last_checked=last_test_at,
                error=None,
            ))
        else:
            # Not tested yet
            services.append(ServiceHealthItem(
                name="SMTP",
                status="unknown",
                last_checked=datetime.now(timezone.utc).isoformat(),
                error="Configured - click 'Send Test Email' to verify",
            ))
    else:
        services.append(ServiceHealthItem(
            name="SMTP",
            status="unknown",
            last_checked=datetime.now(timezone.utc).isoformat(),
            error="Not configured",
        ))

    restart = _restart_required_status()

    return ServiceHealthResponse(
        services=services,
        restart_required=restart["restart_required"],
        changed_keys_requiring_restart=[item["key"] for item in restart["changed_keys"]],
        runtime_env=_runtime_env_comparison_status(
            sage_runtime_config,
            running_core_backend_config=fetch_running_core_backend_config(),
        ),
    )


@router.get("/restart-required", response_model=dict)
async def check_restart_required(admin: dict = Depends(auth.require_admin)):
    """
    Check if service restart is needed after config changes.
    Requires admin authentication.
    """
    return _restart_required_status()


@router.get("/audit-log", response_model=ConfigAuditLogResponse)
async def get_audit_log(
    limit: int = Query(default=50, ge=1, le=1000),
    table_name: Optional[str] = None,
    admin: dict = Depends(auth.require_admin)
):
    """
    Get configuration audit log.
    Requires admin authentication.
    """
    # Validate table_name against allowlist to prevent SQL injection
    if table_name is not None and table_name not in ALLOWED_AUDIT_TABLES:
        raise HTTPException(status_code=400, detail=f"Invalid table_name: {table_name}")

    entries = database.get_config_audit_log(limit=limit, table_name=table_name)

    return ConfigAuditLogResponse(
        entries=[
            ConfigAuditLogEntry(
                id=e["id"],
                table_name=e["table_name"],
                config_key=e["config_key"],
                old_value=e.get("old_value"),
                new_value=e.get("new_value"),
                changed_by=e["changed_by"],
                changed_at=e["changed_at"],
            )
            for e in entries
        ]
    )


@router.get("/audit-log/verify", response_model=dict)
async def verify_audit_log_chain(
    table_name: Optional[str] = Query(default=None),
    admin: dict = Depends(auth.require_admin),
):
    """
    Verify tamper-evident hash chain integrity for configuration audit log.
    The chain is global across all config tables; optional `table_name` limits
    reporting scope while integrity is validated end-to-end.
    Requires admin authentication.
    """
    if table_name is not None and table_name not in ALLOWED_AUDIT_TABLES:
        raise HTTPException(status_code=400, detail=f"Invalid table_name: {table_name}")

    return database.verify_config_audit_log_chain(table_name=table_name)
