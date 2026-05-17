"""
Enclave Deployment Configuration Router
Handles environment settings, service health checks, and .env management.
"""

import os
import time
import json
import logging
from datetime import datetime, timezone
from typing import Final, Mapping, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request
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

PRODUCTION_UNSAFE_FLAGS: Final[tuple[str, ...]] = (
    "MOCK_EMAIL",
)


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
    if key == "LLM_API_KEY":
        return None
    return os.getenv(key)


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
        value = None if key == "LLM_API_KEY" else os.getenv(key)

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
    _: None = Depends(config_export_limiter),
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
        # Quote values with spaces or special chars, escape backslashes, newlines, tabs, and dollar signs
        if " " in value or "=" in value or "#" in value or '"' in value or "\\" in value or "\n" in value or "\r" in value or "\t" in value or "$" in value:
            # Escape backslashes first, then quotes, then dollar signs, then control characters
            value = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
            value = f'"{value}"'

        lines.append(f"{config['key']}={value}")

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


@router.post("/config/validate", response_model=DeploymentValidationResponse)
async def validate_config(admin: dict = Depends(auth.require_admin)):
    """
    Validate current configuration.
    Checks for required values and valid formats.
    Requires admin authentication.
    """
    errors = []
    warnings = []

    all_config = database.get_all_deployment_config()
    config_dict = {c["key"]: c["value"] for c in all_config}

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

    if auth.is_production_mode():
        for key in PRODUCTION_UNSAFE_FLAGS:
            if _truthy_config_value(_deployment_config_value(config_dict, key)):
                errors.append(f"{key} must be disabled in production")
        rate_limit_backend = (
            _deployment_config_value(config_dict, "RATE_LIMIT_BACKEND")
            or os.getenv("RATE_LIMIT_BACKEND", "memory")
        ).strip().lower()
        if rate_limit_backend != "valkey":
            errors.append("RATE_LIMIT_BACKEND must be valkey in production")
        if not (_deployment_config_value(config_dict, "RATE_LIMIT_VALKEY_URL") or os.getenv("RATE_LIMIT_VALKEY_URL", "")).strip():
            errors.append("RATE_LIMIT_VALKEY_URL must be configured in production")

    if not config_dict.get("SMTP_HOST") and not mock_email_enabled:
        warnings.append("SMTP not configured - email features will not work")

    if not config_dict.get("SEARXNG_URL"):
        warnings.append("SEARXNG_URL not configured - web search will not work")

    # Check for SSL configuration consistency
    ssl_cert = config_dict.get("SSL_CERT_PATH", "")
    ssl_key = config_dict.get("SSL_KEY_PATH", "")
    force_https = config_dict.get("FORCE_HTTPS", "").lower() in ("true", "1", "yes", "on")

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

    try:
        start = time.time()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(llm_health_url)
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

    # Check if restart is required
    restart_keys = database.get_restart_required_keys()
    audit_log = database.get_config_audit_log(limit=50, table_name="deployment_config")

    # Find keys that were changed since service started
    changed_requiring_restart = []
    for entry in audit_log:
        if entry["config_key"] in restart_keys:
            try:
                # Parse the changed_at timestamp and compare to service start time
                changed_at_str = entry["changed_at"]
                # Handle both Z suffix and +00:00 suffix for UTC
                changed_at = datetime.fromisoformat(changed_at_str.replace("Z", "+00:00"))
                if changed_at > SERVICE_START_TIME:
                    changed_requiring_restart.append(entry["config_key"])
            except (ValueError, TypeError, AttributeError):
                # Skip entries with invalid timestamps
                pass

    return ServiceHealthResponse(
        services=services,
        restart_required=len(changed_requiring_restart) > 0,
        changed_keys_requiring_restart=list(set(changed_requiring_restart)),
    )


@router.get("/restart-required", response_model=dict)
async def check_restart_required(admin: dict = Depends(auth.require_admin)):
    """
    Check if service restart is needed after config changes.
    Requires admin authentication.
    """
    restart_keys = database.get_restart_required_keys()
    audit_log = database.get_config_audit_log(limit=100, table_name="deployment_config")

    changed_requiring_restart = []
    for entry in audit_log:
        if entry["config_key"] in restart_keys:
            try:
                # Parse the changed_at timestamp and compare to service start time
                changed_at_str = entry["changed_at"]
                changed_at = datetime.fromisoformat(changed_at_str.replace("Z", "+00:00"))
                if changed_at > SERVICE_START_TIME:
                    changed_requiring_restart.append({
                        "key": entry["config_key"],
                        "changed_at": entry["changed_at"],
                    })
            except (ValueError, TypeError, AttributeError):
                # Skip entries with invalid timestamps
                pass

    return {
        "restart_required": len(changed_requiring_restart) > 0,
        "changed_keys": changed_requiring_restart[:10],  # Limit to recent
    }


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
