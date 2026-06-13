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
    "onboarding",
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
        "Tool catalog metadata is Enclave Control Plane context, not Python public Tool orchestration.",
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


# =============================================================================
# Onboarding (guided first-run setup)
# =============================================================================

# Each item is one step the assistant walks the operator through. This list is the
# extension point: add more groups (user-types, agent-settings, etc.) as additional
# items to extend AI-guided onboarding to other config domains.
#
# `configurable`:
#   - "chat": the assistant can set it via a change set (PUT /admin/settings)
#   - "deployment": secret/restart-required; the assistant must NOT take it in chat,
#     only guide the operator to the Deployment Settings page.
ONBOARDING_BASELINE_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "key": "instance_name",
        "label": "Instance name",
        "question": (
            "What should we call this space? This name shows at the top of the app "
            "and in the browser tab — for example, \"Acme Aid\" or \"Refugee Legal Help\"."
        ),
        "importance": "required",
        "configurable": "chat",
        "default": "Enclave",
    },
    {
        "key": "description",
        "label": "Short description",
        "question": (
            "In a sentence, what is this space for? This is just a private note for "
            "your own reference (your users won't see it) — for example, \"Rapid legal "
            "support for people who've been detained.\""
        ),
        "importance": "recommended",
        "configurable": "chat",
        "default": "A privacy-first RAG knowledge base",
    },
    {
        "key": "assistant_name",
        "label": "Assistant name",
        "question": (
            "What should we name the AI helper? Your users will see this name on every "
            "message it sends — for example, \"Aria\", \"Sage\", or \"Companion\"."
        ),
        "importance": "recommended",
        "configurable": "chat",
        "default": "Enclave AI",
    },
    {
        "key": "primary_color",
        "label": "Accent color",
        "question": (
            "What accent color should the app use? This is the highlight color for things "
            "like buttons and links (the light/dark background is set separately). You can "
            "tell me a color name like blue, purple, green, orange, pink, or teal — or a "
            "specific color code like #3B82F6."
        ),
        "importance": "recommended",
        "configurable": "chat",
        "default": "#3B82F6",
    },
    {
        "key": "default_theme",
        "label": "Light or dark",
        "question": (
            "Should the app open in light mode, dark mode, or just match whatever the "
            "person's device is set to? (light, dark, or system)"
        ),
        "importance": "recommended",
        "configurable": "chat",
        "default": "system",
    },
    {
        "key": "default_language",
        "label": "Default language",
        "question": (
            "What language should the app start in for new people? For example, English "
            "or Spanish. This is optional — if you skip it, the app follows each person's "
            "browser language."
        ),
        "importance": "optional",
        "configurable": "chat",
        "default": "",
    },
    {
        "key": "header_tagline",
        "label": "Tagline",
        "question": (
            "Want a short tagline in the header, next to your space's name? For example, "
            "\"Private answers, always.\" This is optional — feel free to skip it."
        ),
        "importance": "optional",
        "configurable": "chat",
        "default": "",
    },
    {
        "key": "auto_approve_users",
        "label": "Who can join",
        "question": (
            "When someone new signs up, should they get in right away, or wait for you to "
            "approve them first? (\"right away\" or \"approve each person\")"
        ),
        "importance": "recommended",
        "configurable": "chat",
        "default": "true",
    },
)

# Deployment/secret steps the assistant guides toward but never sets in chat.
ONBOARDING_DEPLOYMENT_HANDOFFS: tuple[dict[str, str], ...] = (
    {
        "label": "Email / SMTP",
        "why": "Required for real users to receive magic-link sign-in emails (or enable MOCK_EMAIL for testing).",
    },
    {
        "label": "Model provider keys",
        "why": "The assistant cannot run without the model/embedding API keys.",
    },
    {
        "label": "Domains / CORS / SSL",
        "why": "Needed for any non-localhost deployment.",
    },
)


def _onboarding_item_status(current_value: str | None, default: str, configured: bool) -> str:
    # An explicitly-configured key counts as 'set' even if its value equals the
    # default (e.g. operator chose theme=system), so it burns down off the list.
    if configured:
        return "set"
    value = (current_value or "").strip()
    if not value:
        return "unset"
    if value == (default or "").strip():
        return "default"
    return "set"


def _onboarding_setting_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _build_onboarding_section(*, settings: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    try:
        configured_keys = database.get_onboarding_configured_keys()
    except Exception as e:
        warnings.append(f"onboarding configured keys read failed: {e}")
        configured_keys = set()
    checklist = []
    for item in ONBOARDING_BASELINE_ITEMS:
        current = settings.get(item["key"])
        current_str = _onboarding_setting_value(current)
        checklist.append({
            "key": item["key"],
            "label": item["label"],
            "question": item["question"],
            "importance": item["importance"],
            "configurable": item["configurable"],
            "current_value": current_str,
            "status": _onboarding_item_status(
                current_str, item.get("default", ""), item["key"] in configured_keys
            ),
        })

    remaining = [c for c in checklist if c["status"] in ("unset", "default")]

    lines = [
        "ONBOARDING MODE — GUIDED FIRST-RUN SETUP",
        "You are helping a brand-new operator set up their Enclave instance for the very first "
        "time. This is their first impression — be warm, concise, and encouraging.",
        "",
        "HOW TO RUN THIS SESSION (ASK EVERYTHING AT ONCE):",
        "- Present ALL chat-configurable items that still need a value (status 'unset' or 'default') as a "
        "SINGLE numbered list in ONE message, each line: number, label, and the item's friendly 'question'. "
        "Tell the operator they can answer as many as they like in one reply, number their answers, and "
        "skip anything. Do NOT ask one question per turn.",
        "- When they reply, parse their single message flexibly: they may number answers (\"1. ... 4. ...\"), "
        "write prose, answer only some, and skip others. Only use values they actually provided — never "
        "invent a value for something they skipped.",
        "- Apply EVERYTHING they provided in ONE change set (PUT /admin/settings) — a single approval for "
        "all of it. Translate plain answers to stored values per the value mapping in the write contract.",
        "- The CHECKLIST you receive each turn is the source of truth for what is saved. After the Apply, "
        "re-read it: confirm what saved, and if any value they gave still shows 'unset'/'default', it did "
        "NOT save — re-apply it in another change set.",
        "- BURN DOWN THE LIST: partial answers are fine. After applying what they gave, present a NEW, "
        "SHORTER numbered list of ONLY the items that still show 'unset'/'default', and invite them to "
        "answer any of those (or skip). Repeat this loop — each round the list gets shorter — until no "
        "chat-configurable items remain or the operator says they're done. Never re-ask for items already "
        "'set' unless the operator wants to change them.",
        "- The operator can stop at any time with items still unanswered; that's OK. Optional items "
        "(language, tagline) especially can be left as-is. Don't pressure them to finish every item.",
        "- NEVER ask for secrets or API keys in chat. For the DEPLOYMENT HANDOFFS below, explain what "
        "they are and direct the operator to the Deployment Settings page — never put them in a change set.",
        "- When no items remain (or the operator is done), summarize what was set (read values from the "
        "checklist, not memory), then tell them to use the 'Finish & go to dashboard' button and to visit "
        "Deployment Settings for the handoff items.",
        "",
        f"PROGRESS: {len(checklist) - len(remaining)}/{len(checklist)} baseline items configured.",
        "",
        "REMAINING — present THESE as the numbered list this turn (if empty, the baseline is complete; "
        "summarize and wrap up):",
        _compact_json(
            [{"key": c["key"], "label": c["label"], "question": c["question"]} for c in remaining]
        ),
        "",
        "FULL CHECKLIST (with saved status, for reference):",
        _compact_json(checklist),
        "",
        "DEPLOYMENT HANDOFFS (guide only — never set in chat):",
        _compact_json(list(ONBOARDING_DEPLOYMENT_HANDOFFS)),
        "",
        "WRITE CONTRACT:",
        "- Apply chat-configurable items with PUT /admin/settings and a JSON body containing ALL the "
        "keys you have collected for the group, e.g. {\"instance_name\": \"...\", \"description\": \"...\"}.",
        "- Batch related settings into a single change set (one Apply for the whole group), not one per field.",
        "- The questions use plain language; translate the operator's plain answer into the stored value:",
        "    * default_theme: one of \"light\", \"dark\", or \"system\".",
        "    * default_language: a 2-letter language code (English -> \"en\", Spanish -> \"es\", "
        "French -> \"fr\", Arabic -> \"ar\", etc.).",
        "    * auto_approve_users: the string \"true\" (let people in right away) or \"false\" "
        "(approve each person manually).",
        "    * primary_color: a color name (blue, purple, green, orange, pink, teal) or a hex code "
        "like \"#3B82F6\".",
        "Example batched change set (after collecting a few branding answers):",
        json.dumps(
            {
                "version": 1,
                "summary": "Set the instance name, description, and assistant name.",
                "requests": [
                    {
                        "method": "PUT",
                        "path": "/admin/settings",
                        "body": {
                            "instance_name": "Acme Aid",
                            "description": "Rapid legal support for detainees.",
                            "assistant_name": "Aria",
                        },
                    },
                ],
            },
            indent=2,
            sort_keys=True,
        ),
    ]

    return {
        "scope": "onboarding",
        "title": "Guided Onboarding",
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
        "onboarding": lambda: _build_onboarding_section(settings=settings, warnings=warnings),
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
