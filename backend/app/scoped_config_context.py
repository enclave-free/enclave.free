"""
Server-owned Scoped Config Context assembly for Sage internal contract calls.

The Enclave Control Plane owns scope classification and scoped reads. Sage
consumes the returned structured sections and prompt-ready context text during
config-enabled Admin Conversations.
"""

from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Optional

import database
from region_data import SUBREGION_NAMES
from tools.admin_config_context import (
    ADMIN_VISIBLE_TOOLS,
    build_instance_settings_change_set_example,
    instance_settings_fields,
    resolve_included_scopes,
    select_deployment_category,
)

CONTRACT_VERSION = 1
MAX_USER_TYPES_FANOUT = 10
SCOPED_CONFIG_CACHE_TTL_SECONDS = 30

_scoped_config_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_scoped_config_cache_lock = threading.Lock()

ScopedConfigScope = Literal[
    "overview",
    "instance-settings",
    "deployment-settings",
    "agent-settings",
    "user-types",
    "document-defaults",
    "resources",
    "health",
]

ScopedConfigMode = Literal["auto", "overview", "full"]

OVERVIEW_SETTING_KEYS: tuple[str, ...] = (
    "instance_name",
    "description",
    "assistant_name",
    "header_tagline",
)


class ScopedConfigAuthorizationError(Exception):
    """Raised when the actor is not authorized for admin scoped config context."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def invalidate_scoped_config_context_cache() -> None:
    """Clear short-lived scoped config context reads after admin writes."""
    with _scoped_config_cache_lock:
        _scoped_config_cache.clear()


def _compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def _cache_get(key: tuple[str, str]) -> dict[str, Any] | None:
    now = time.time()
    with _scoped_config_cache_lock:
        cached = _scoped_config_cache.get(key)
        if cached is None:
            return None
        cached_at, section = cached
        if now - cached_at >= SCOPED_CONFIG_CACHE_TTL_SECONDS:
            _scoped_config_cache.pop(key, None)
            return None
        return deepcopy(section)


def _cache_put(key: tuple[str, str], section: dict[str, Any]) -> None:
    with _scoped_config_cache_lock:
        _scoped_config_cache[key] = (time.time(), deepcopy(section))


def _cache_key_for_scope(scope: str, query: str) -> tuple[str, str]:
    if scope == "deployment-settings":
        return (scope, select_deployment_category(query) or "__all__")
    return (scope, "")


def _format_overview_settings(settings: dict[str, Any]) -> str:
    lines: list[str] = []
    for key in OVERVIEW_SETTING_KEYS:
        if key not in settings:
            continue
        value = settings[key]
        rendered = value if isinstance(value, str) else json.dumps(value)
        lines.append(f"- {key}: {rendered}")
    return "\n".join(lines)


def _build_control_contract_lines(
    *,
    generated_at: str,
    primary_scope: ScopedConfigScope,
) -> list[str]:
    lines = [
        "SCOPED CONFIG CONTEXT",
        f"Generated: {generated_at}",
        f"scope: {primary_scope}",
    ]
    if primary_scope != "overview":
        lines.extend([
            "",
            "Tool capability contract: see overview scope.",
            "State-changing writes still require exactly one valid JSON change set and Admin Change Confirmation.",
        ])
        return lines

    lines.extend([
        "",
        "ADMIN-VISIBLE TOOL CAPABILITIES",
    ])
    for tool in ADMIN_VISIBLE_TOOLS:
        lines.append(
            f"- {tool['id']} ({tool['name']}): {tool['description']} Access: {tool['access']}."
        )
    lines.extend([
        "",
        "RULES",
        "- You are assisting the instance admin in configuring Enclave.",
        "- Never ask for or assume access to the admin Nostr private key (nsec). It is held in NIP-07 and is not available here.",
        "- Treat all secret environment variables as highly sensitive.",
        "- Do not echo secrets back into chat. If you must reference them, say \"[REDACTED]\".",
        "- Prefer actionable, specific guidance: which setting to change, what to set it to, and whether restart is required.",
        "- When the admin delegates a configuration task, inspect first-party context, choose reasonable defaults for unspecified details, and state important assumptions briefly.",
        "- For a coherent delegated admin configuration task, group related settings into one executable change set instead of splitting every setting into separate proposals.",
        "- Never call prose-only bullets or recommendations a Change Confirmation. A Change Confirmation requires exactly one valid JSON change set that the UI can validate and preview.",
        "",
        "HOW TO USE THESE TOOLS",
        "",
        "admin-config: Call to inspect or understand any configuration area.",
        "Each call returns the relevant configuration scope and context for that area.",
        "You may call it multiple times to understand different configuration areas.",
        "",
        "db-query: Call for analytics, user counts, or data inspection.",
        "Use this for questions about existing data, patterns, or inventory.",
        "",
        "web-search: Call for current information or best practices (when enabled).",
        "",
        "CHANGESET FORMAT (optional)",
        "If you want the admin to apply changes from this chat, include exactly one JSON code block with this shape:",
        "```json",
        json.dumps(
            {
                "version": 1,
                "summary": "Short summary of the proposed changes.",
                "requests": [
                    {
                        "method": "PUT",
                        "path": "/admin/settings",
                        "body": {"default_theme": "dark"},
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "- State-changing Admin Conversation writes require Admin Change Confirmation before apply.",
        "- Use exactly one JSON change set. Instance Settings are updated with a partial PUT /admin/settings body.",
        "- Do not include secret Deployment Settings unless the Admin explicitly requested setting them.",
    ])
    return lines


def _build_overview_section(settings: dict[str, Any]) -> dict[str, Any]:
    overview_lines = _format_overview_settings(settings)
    content = "INSTANCE OVERVIEW (/admin/settings)"
    if overview_lines:
        content = f"{content}\n{overview_lines}"
    return {
        "scope": "overview",
        "title": "Instance overview",
        "content": content,
        "fields": [],
    }


def _format_instance_settings_lines(settings: dict[str, Any]) -> list[str]:
    lines = [
        "INSTANCE SETTINGS (/admin/settings)",
        _compact_json(settings),
        "",
        "INSTANCE BRANDING, THEME, AND COPY SETTINGS",
    ]
    for field in instance_settings_fields(settings):
        lines.append(
            f"- {field['key']} ({field['label']}): current value: {field['current_value']}; "
            f"valid values: {field['valid_values']}; mutation: {field['mutation']}"
        )
    example_change_set = build_instance_settings_change_set_example()
    lines.extend([
        "",
        "CHANGESET FORMAT",
        "State-changing Admin Conversation writes require Admin Change Confirmation before apply.",
        "Use exactly one JSON change set. Instance Settings are updated with a partial PUT /admin/settings body.",
        "Never call prose-only bullets or recommendations a Change Confirmation. A Change Confirmation requires exactly one valid JSON change set that the UI can validate and preview.",
        "If you already described changes in prose but did not emit JSON, the admin cannot apply them yet. On apply/confirm follow-up language, generate the missing JSON change set or ask one focused follow-up.",
        "Do not include secret Deployment Settings unless the Admin explicitly requested setting them.",
        json.dumps(example_change_set, indent=2, sort_keys=True),
    ])
    return lines


def _build_instance_settings_section(settings: dict[str, Any]) -> dict[str, Any]:
    fields = instance_settings_fields(settings)
    content = "\n".join(_format_instance_settings_lines(settings))
    return {
        "scope": "instance-settings",
        "title": "Instance Settings",
        "content": content,
        "fields": fields,
    }


def _format_deployment_items(items: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in items:
        secret = " secret=true" if item.get("is_secret") else ""
        restart = " requires_restart=true" if item.get("requires_restart") else ""
        value = item.get("value") or ""
        lines.append(f"- {item['key']} = {value}{restart}{secret}")
        description = item.get("description")
        if description:
            lines.append(f"  description: {description}")
    return lines


def _summarize_ai_config_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summarized: list[dict[str, Any]] = []
    for row in rows:
        value = row.get("value")
        value_text = "" if value is None else str(value)
        summarized.append({
            "key": row.get("key"),
            "category": row.get("category"),
            "value_type": row.get("value_type"),
            "description": row.get("description"),
            "value_length": len(value_text),
            "is_override": bool(row.get("is_override", False)),
        })
    return summarized


def _build_deployment_settings_section(
    query: str,
    *,
    warnings: list[str],
) -> dict[str, Any]:
    category = select_deployment_category(query)
    if category:
        items = database.get_deployment_config_by_category(category)
        title = f"DEPLOYMENT SETTINGS ({category})"
    else:
        items = database.get_all_deployment_config()
        title = "DEPLOYMENT SETTINGS (/admin/deployment/config)"

    lines = [title, *_format_deployment_items(items), "", "SECRETS"]
    secret_keys = [item["key"] for item in items if item.get("is_secret")]
    if secret_keys:
        lines.append(
            "Secret env vars are masked in this context. Metadata is shown with secret=true; "
            "raw values are never included unless a future secret-aware Admin Conversation extends the contract."
        )
        for key in sorted(secret_keys):
            lines.append(f"- {key} = [REDACTED]")
    else:
        lines.append("No secret deployment settings are present in this scoped read.")

    return {
        "scope": "deployment-settings",
        "title": "Deployment Settings",
        "content": "\n".join(lines),
        "fields": [],
    }


def _build_agent_settings_section(
    *,
    warnings: list[str],
) -> dict[str, Any]:
    lines = [
        "AGENT SETTINGS (/admin/ai-config)",
        "AI CONFIG SUMMARY",
        _compact_json(_summarize_ai_config_rows(database.get_all_ai_config())),
    ]
    user_types = database.list_user_types()
    included_types = user_types[:MAX_USER_TYPES_FANOUT]
    if len(user_types) > MAX_USER_TYPES_FANOUT:
        warnings.append(
            f"agent-settings reduced to first {MAX_USER_TYPES_FANOUT} user types "
            f"of {len(user_types)} total."
        )

    for user_type in included_types:
        try:
            effective_config = database.get_effective_ai_config(user_type["id"])
            lines.extend([
                "",
                f"AGENT SETTINGS (user_type_id={user_type['id']} {user_type['name']})",
                _compact_json(_summarize_ai_config_rows(effective_config)),
            ])
        except Exception as exc:
            warnings.append(f"agent-settings user_type_id={user_type['id']} failed: {exc}")

    return {
        "scope": "agent-settings",
        "title": "Agent Settings",
        "content": "\n".join(lines),
        "fields": [],
    }


def _build_user_type_write_contract_lines() -> list[str]:
    private_field_example = {
        "version": 1,
        "summary": "Create an Activist user type with private onboarding fields.",
        "requests": [
            {
                "method": "POST",
                "path": "/admin/user-types",
                "body": {
                    "name": "Activist",
                    "description": "Users participating as activists",
                    "display_order": 0,
                },
            },
            {
                "method": "POST",
                "path": "/admin/user-fields",
                "body": {
                    "field_name": "Name",
                    "field_type": "text",
                    "required": True,
                    "display_order": 0,
                    "user_type_id": "@type:activist",
                    "placeholder": "Your name",
                    "encryption_enabled": True,
                    "include_in_chat": False,
                },
            },
            {
                "method": "POST",
                "path": "/admin/user-fields",
                "body": {
                    "field_name": "Email",
                    "field_type": "email",
                    "required": True,
                    "display_order": 1,
                    "user_type_id": "@type:activist",
                    "placeholder": "you@example.org",
                    "encryption_enabled": True,
                    "include_in_chat": False,
                },
            },
            {
                "method": "POST",
                "path": "/admin/user-fields",
                "body": {
                    "field_name": "Phone Number",
                    "field_type": "text",
                    "required": True,
                    "display_order": 2,
                    "user_type_id": "@type:activist",
                    "placeholder": "Your phone number",
                    "encryption_enabled": True,
                    "include_in_chat": False,
                },
            },
        ],
    }
    return [
        "",
        "USER TYPE AND FIELD WRITE CONTRACT",
        "- Create user types with POST /admin/user-types and body keys: "
        "name, description, icon, display_order.",
        "- Create onboarding fields with POST /admin/user-fields and body keys: "
        "field_name, field_type, required, display_order, user_type_id, "
        "placeholder, options, encryption_enabled, include_in_chat.",
        "- Supported field_type values: text, textarea, number, boolean, email, "
        "url, select, multi_select, date.",
        "- For phone/contact numbers, prefer field_type text so formatting and "
        "leading +/0 characters are preserved.",
        "- Private onboarding fields use encryption_enabled=true and "
        "include_in_chat=false. Encrypted fields cannot be included in chat context.",
        "- Use @type:<slug> placeholders when one change set creates a user type "
        "and then creates fields for it.",
        "Example private onboarding change set:",
        json.dumps(private_field_example, indent=2, sort_keys=True),
    ]


def _build_user_types_section(*, warnings: list[str]) -> dict[str, Any]:
    user_types = database.list_user_types()
    lines = [
        "USER TYPES (/admin/user-types)",
        _compact_json({"types": user_types}),
    ]
    lines.extend(_build_user_type_write_contract_lines())
    included_types = user_types[:MAX_USER_TYPES_FANOUT]
    if len(user_types) > MAX_USER_TYPES_FANOUT:
        warnings.append(
            f"user-types reduced to first {MAX_USER_TYPES_FANOUT} user types "
            f"of {len(user_types)} total."
        )

    for user_type in included_types:
        try:
            fields = database.get_field_definitions(user_type["id"])
            lines.extend([
                "",
                f"USER FIELDS (user_type_id={user_type['id']} {user_type['name']})",
                _compact_json(fields),
            ])
        except Exception as exc:
            warnings.append(f"user-fields user_type_id={user_type['id']} failed: {exc}")

    return {
        "scope": "user-types",
        "title": "User Types",
        "content": "\n".join(lines),
        "fields": [],
    }


def _build_document_defaults_section(*, warnings: list[str]) -> dict[str, Any]:
    global_defaults = database.list_document_defaults()
    lines = [
        "DOCUMENT DEFAULTS (/ingest/admin/documents/defaults)",
        _compact_json(global_defaults),
    ]
    user_types = database.list_user_types()
    included_types = user_types[:MAX_USER_TYPES_FANOUT]
    if len(user_types) > MAX_USER_TYPES_FANOUT:
        warnings.append(
            f"document-defaults reduced to first {MAX_USER_TYPES_FANOUT} user types "
            f"of {len(user_types)} total."
        )

    for user_type in included_types:
        try:
            effective_defaults = database.get_effective_document_defaults(user_type["id"])
            lines.extend([
                "",
                f"DOCUMENT DEFAULTS (user_type_id={user_type['id']} {user_type['name']})",
                _compact_json(effective_defaults),
            ])
        except Exception as exc:
            warnings.append(
                f"document-defaults user_type_id={user_type['id']} failed: {exc}"
            )

    return {
        "scope": "document-defaults",
        "title": "Document Defaults",
        "content": "\n".join(lines),
        "fields": [],
    }


def _build_resources_write_contract_lines() -> list[str]:
    create_example = {
        "version": 1,
        "summary": "Add a Spanish-speaking detention lawyer covering Central America.",
        "requests": [
            {
                "method": "POST",
                "path": "/admin/resources",
                "body": {
                    "name": "Central America Human Rights Counsel",
                    "resource_type": "ngo",
                    "description": "Spanish-speaking human-rights legal network.",
                    "scope_level": "subregion",
                    "scope_code": "013",
                    "help_types": ["legal", "humanitarian"],
                    "languages": ["es", "en"],
                    "contact": {"email": "info@example.org", "url": "https://example.org"},
                    "vetted_by": "Admin",
                },
            },
        ],
    }
    return [
        "",
        "RESOURCE DIRECTORY WRITE CONTRACT",
        "- Create a resource with POST /admin/resources; update with PUT /admin/resources/{resource_id}; "
        "remove with DELETE /admin/resources/{resource_id}.",
        "- Body keys: name, resource_type (lawyer|ngo|un_body|clinic|shelter|financial|hotline|other), "
        "description, scope_level, scope_code, help_types (array), languages (array of ISO codes), "
        "contact (object: phone, email, url, secure_channel, address, notes), verified (bool), "
        "vetted_by, source_note, display_order, archived (bool).",
        "- COVERAGE: scope_level is one of country|subregion|region|global. For 'country' use an ISO 3166-1 "
        "alpha-2 code as scope_code (e.g. NI). For 'subregion'/'region' use the UN M49 code (e.g. 013 = "
        "Central America, 002 = Africa). For 'global' omit scope_code. See the country/region reference below.",
        "- help_types must reference existing help-type vocabulary keys. Add new vocabulary via "
        "PUT /admin/help-types/{key} before using it.",
        "- LIFECYCLE: a resource is created as 'pending' and auto-promotes to 'ready' only when ALL required "
        "fields are present: name, resource_type, scope_level (+scope_code unless global), at least one "
        "help_type, and at least one contact method. The response includes status and missing_fields — "
        "keep asking the admin for missing_fields until status is 'ready'. Only 'ready' resources are shown "
        "to end users.",
        "Example create change set:",
        json.dumps(create_example, indent=2, sort_keys=True),
    ]


def _build_resources_section(*, warnings: list[str]) -> dict[str, Any]:
    try:
        resources = database.list_resources()
    except Exception as exc:
        warnings.append(f"resources list failed: {exc}")
        resources = []
    try:
        help_types = database.list_help_types()
    except Exception as exc:
        warnings.append(f"help-types list failed: {exc}")
        help_types = []

    # Compact view: enough for the agent to reason about coverage + completeness.
    compact_resources = [
        {
            "resource_id": r["resource_id"],
            "name": r["name"],
            "resource_type": r["resource_type"],
            "scope_level": r["scope_level"],
            "scope_code": r["scope_code"],
            "help_types": r["help_types"],
            "languages": r["languages"],
            "status": r["status"],
            "missing_fields": r["missing_fields"],
            "verified": bool(r["verified_at"]),
        }
        for r in resources
    ]

    lines = [
        "RESOURCE DIRECTORY (/admin/resources)",
        _compact_json({"resources": compact_resources}),
        "",
        "HELP TYPE VOCABULARY (/admin/help-types)",
        _compact_json({"help_types": [{"key": h["key"], "label": h["label"]} for h in help_types]}),
        "",
        "COUNTRY / REGION REFERENCE (UN M49 subregion codes for scope_code)",
        _compact_json(SUBREGION_NAMES),
    ]
    lines.extend(_build_resources_write_contract_lines())
    return {
        "scope": "resources",
        "title": "Resource Directory",
        "content": "\n".join(lines),
        "fields": [],
    }


def _build_health_section(*, warnings: list[str]) -> dict[str, Any]:
    restart_keys = database.get_restart_required_keys()
    deployment_items = database.get_all_deployment_config()
    service_keys = (
        "QDRANT_HOST",
        "QDRANT_PORT",
        "LLM_PROVIDER",
        "LLM_API_URL",
        "SEARXNG_URL",
        "SAGE_WEB_URL",
    )
    configured_services = {
        item["key"]: item["value"]
        for item in deployment_items
        if item["key"] in service_keys
    }
    health_payload = {
        "configured_services": configured_services,
        "restart_required_keys": restart_keys,
        "live_service_probes": (
            "Live service probe results are available from GET /admin/deployment/health."
        ),
    }
    lines = [
        "SERVICE HEALTH (/admin/deployment/health)",
        _compact_json(health_payload),
        "",
        "RESTART-REQUIRED DEPLOYMENT KEYS",
    ]
    if restart_keys:
        lines.extend(f"- {key}" for key in restart_keys)
    else:
        lines.append("- none configured")

    return {
        "scope": "health",
        "title": "Service Health",
        "content": "\n".join(lines),
        "fields": [],
    }


def _append_warnings_section(
    *,
    warnings: list[str],
    sections: list[dict[str, Any]],
    context_lines: list[str],
) -> None:
    if not warnings:
        return
    warning_block = "\n".join(["WARNINGS", *[f"- {item}" for item in warnings]])
    context_lines.extend(["", warning_block])
    sections.append({
        "scope": "warnings",
        "title": "Warnings",
        "content": warning_block,
    })


def build_scoped_config_context(
    *,
    query: str,
    actor: dict[str, Any],
    mode: ScopedConfigMode = "auto",
    requested_scopes: Optional[list[ScopedConfigScope]] = None,
) -> dict[str, Any]:
    """
    Build the authoritative Scoped Config Context response for Sage.

    Parameters:
        query: The Admin's configuration question.
        actor: Internal actor context; only approved admins are authorized.
        mode: `auto` classifies the query; `overview` forces overview scope.
        requested_scopes: Optional explicit scope hints for multi-scope reads.
    """
    if actor.get("type") != "admin" or not actor.get("approved"):
        raise ScopedConfigAuthorizationError(
            "Approved admin actor required for scoped config context"
        )

    generated_at = _utc_now_iso()
    primary_scope, included_scopes = resolve_included_scopes(
        query,
        mode=mode,
        requested_scopes=requested_scopes,
    )

    warnings: list[str] = []
    sections: list[dict[str, Any]] = []
    context_lines = _build_control_contract_lines(
        generated_at=generated_at,
        primary_scope=primary_scope,  # type: ignore[arg-type]
    )

    settings = database.get_all_settings()
    scope_builders: dict[str, Callable[[], dict[str, Any]]] = {
        "overview": lambda: _build_overview_section(settings),
        "instance-settings": lambda: _build_instance_settings_section(settings),
        "deployment-settings": lambda: _build_deployment_settings_section(
            query,
            warnings=warnings,
        ),
        "agent-settings": lambda: _build_agent_settings_section(warnings=warnings),
        "user-types": lambda: _build_user_types_section(warnings=warnings),
        "document-defaults": lambda: _build_document_defaults_section(warnings=warnings),
        "resources": lambda: _build_resources_section(warnings=warnings),
        "health": lambda: _build_health_section(warnings=warnings),
    }

    for scope in included_scopes:
        builder = scope_builders.get(scope)
        if builder is None:
            warnings.append(f"Unknown scoped config scope requested: {scope}")
            continue
        cache_key = _cache_key_for_scope(scope, query)
        section = _cache_get(cache_key)
        if section is None:
            warning_count_before = len(warnings)
            section = builder()
            if len(warnings) == warning_count_before:
                _cache_put(cache_key, section)
        sections.append(section)
        context_lines.extend(["", section["content"]])

    _append_warnings_section(
        warnings=warnings,
        sections=sections,
        context_lines=context_lines,
    )

    return {
        "version": CONTRACT_VERSION,
        "primary_scope": primary_scope,
        "included_scopes": included_scopes,
        "context_text": "\n".join(context_lines),
        "sections": sections,
        "warnings": warnings,
        "generated_at": generated_at,
        "secret_policy": {"mode": "masked"},
    }
