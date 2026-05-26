"""
Server-owned Scoped Config Context assembly for Sage internal contract calls.

The Enclave Control Plane owns scope classification and scoped reads. Sage
consumes the returned structured sections and prompt-ready context text during
config-enabled Admin Conversations.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Optional

import database
from tools.admin_config_context import (
    ADMIN_VISIBLE_TOOL_CAPABILITIES,
    build_instance_settings_change_set_example,
    instance_settings_fields,
    resolve_included_scopes,
    select_deployment_category,
)

CONTRACT_VERSION = 1
MAX_USER_TYPES_FANOUT = 10

ScopedConfigScope = Literal[
    "overview",
    "instance-settings",
    "deployment-settings",
    "agent-settings",
    "user-types",
    "document-defaults",
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
        "",
        "ADMIN-VISIBLE TOOL CAPABILITIES",
    ]
    for tool in ADMIN_VISIBLE_TOOL_CAPABILITIES:
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
        json.dumps(settings, indent=2, sort_keys=True),
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
        json.dumps(database.get_all_ai_config(), indent=2, sort_keys=True, default=str),
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
                json.dumps(effective_config, indent=2, sort_keys=True, default=str),
            ])
        except Exception as exc:
            warnings.append(f"agent-settings user_type_id={user_type['id']} failed: {exc}")

    return {
        "scope": "agent-settings",
        "title": "Agent Settings",
        "content": "\n".join(lines),
        "fields": [],
    }


def _build_user_types_section(*, warnings: list[str]) -> dict[str, Any]:
    user_types = database.list_user_types()
    lines = [
        "USER TYPES (/admin/user-types)",
        json.dumps({"types": user_types}, indent=2, sort_keys=True, default=str),
    ]
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
                json.dumps(fields, indent=2, sort_keys=True, default=str),
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
        json.dumps(global_defaults, indent=2, sort_keys=True, default=str),
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
                json.dumps(effective_defaults, indent=2, sort_keys=True, default=str),
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
        json.dumps(health_payload, indent=2, sort_keys=True, default=str),
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
        "health": lambda: _build_health_section(warnings=warnings),
    }

    for scope in included_scopes:
        builder = scope_builders.get(scope)
        if builder is None:
            warnings.append(f"Unknown scoped config scope requested: {scope}")
            continue
        section = builder()
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
