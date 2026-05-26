from __future__ import annotations

import re
from typing import Any


ADMIN_VISIBLE_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "id": "web-search",
        "name": "Web Search",
        "access": "all users when enabled",
        "description": (
            "Looks up current or external information through the configured SearXNG service. "
            "Use this to find best practices, current documentation, or external reference material "
            "that may inform configuration decisions."
        ),
        "examples": [
            "Search for current best practices on data retention policies",
            "Look up the latest documentation for Enclave deployment settings",
            "Find guidance on GDPR compliance for user onboarding",
        ],
    },
    {
        "id": "admin-config",
        "name": "Admin Config",
        "access": "admins only",
        "description": (
            "Read instance configuration including settings, deployment configuration, user types, "
            "onboarding structure, document access policies, and agent behavior. Ask about what you "
            "need to inspect or change, and the tool returns the relevant context with actionable "
            "schema for configuration changes."
        ),
        "examples": [
            "What user types are configured?",
            "Show me the SMTP email settings",
            "How do I create a user type with encrypted private fields?",
            "What instance settings control data retention?",
        ],
    },
    {
        "id": "db-query",
        "name": "Database",
        "access": "admins only",
        "description": (
            "Runs safe read-only admin database queries using natural language for analytics, "
            "user inspection, troubleshooting, or data analysis. Use this for questions about "
            "existing data, patterns, or inventory."
        ),
        "examples": [
            "How many users are currently registered?",
            "Show me recent user onboarding activity",
            "List all user types and their field counts",
        ],
    },
)

DEPLOYMENT_KEYWORDS: frozenset[str] = frozenset({
    "deployment",
    "env",
    "environment",
    "smtp",
    "email",
    "domain",
    "ssl",
    "https",
    "provider",
    "model",
    "searxng",
    "restart",
})

DEPLOYMENT_CATEGORY_KEYWORDS: dict[str, frozenset[str]] = {
    "email": frozenset({"smtp", "email"}),
    "domains": frozenset({"domain", "dns", "cors", "url"}),
    "ssl": frozenset({"ssl", "https", "tls", "certificate", "cert"}),
    "llm": frozenset({"provider", "model", "llm", "rag", "pdf"}),
    "search": frozenset({"searxng", "search"}),
}

INSTANCE_VISUAL_IDENTITY_KEYWORDS: frozenset[str] = frozenset({
    "appearance",
    "branding",
    "bubble",
    "chat",
    "color",
    "colors",
    "identity",
    "palette",
    "status",
    "surface",
    "theme",
    "themes",
    "typography",
    "visual",
})

INSTANCE_COPY_KEYWORDS: frozenset[str] = frozenset({
    "copy",
    "description",
    "label",
    "logo",
    "name",
    "tagline",
    "title",
})

INSTANCE_COPY_SETTINGS: tuple[dict[str, str], ...] = (
    {
        "key": "instance_name",
        "label": "Instance name",
        "valid_values": "string",
    },
    {
        "key": "description",
        "label": "Instance description",
        "valid_values": "string",
    },
    {
        "key": "logo_url",
        "label": "Logo URL",
        "valid_values": "URL or empty string",
    },
    {
        "key": "icon",
        "label": "Instance icon",
        "valid_values": "icon name",
    },
    {
        "key": "assistant_icon",
        "label": "Assistant icon",
        "valid_values": "icon name",
    },
    {
        "key": "assistant_name",
        "label": "Assistant display name",
        "valid_values": "string",
    },
    {
        "key": "user_label",
        "label": "User label",
        "valid_values": "string",
    },
    {
        "key": "header_tagline",
        "label": "Header tagline",
        "valid_values": "string",
    },
)

AGENT_SETTINGS_KEYWORDS: frozenset[str] = frozenset({
    "agent",
    "behavior",
    "behaviour",
    "conversation",
    "max",
    "personalization",
    "prompt",
    "prompts",
    "temperature",
    "tokens",
    "trace",
})

USER_TYPES_KEYWORDS: frozenset[str] = frozenset({
    "field",
    "fields",
    "onboard",
    "onboarding",
    "question",
    "questions",
    "type",
    "types",
    "user",
    "users",
})

DOCUMENT_DEFAULTS_KEYWORDS: frozenset[str] = frozenset({
    "access",
    "default",
    "defaults",
    "document",
    "documents",
    "ingestion",
    "library",
})

HEALTH_KEYWORDS: frozenset[str] = frozenset({
    "broken",
    "health",
    "readiness",
    "service",
    "status",
    "validate",
    "validation",
})

SCOPE_PRIORITY: tuple[str, ...] = (
    "overview",
    "health",
    "instance-settings",
    "user-types",
    "agent-settings",
    "document-defaults",
    "deployment-settings",
)

ALL_DOCUMENTED_SCOPES: tuple[str, ...] = (
    "overview",
    "instance-settings",
    "deployment-settings",
    "agent-settings",
    "user-types",
    "document-defaults",
    "health",
)

INSTANCE_VISUAL_IDENTITY_SETTINGS: tuple[dict[str, str], ...] = (
    {
        "key": "default_theme",
        "label": "Default theme",
        "valid_values": "system, light, dark",
    },
    {
        "key": "primary_color",
        "label": "Primary color",
        "valid_values": "preset name or hex color",
    },
    {
        "key": "chat_bubble_style",
        "label": "Chat bubble style",
        "valid_values": "soft or other supported Instance setting value",
    },
    {
        "key": "chat_bubble_shadow",
        "label": "Chat bubble shadow",
        "valid_values": "true, false",
    },
    {
        "key": "surface_style",
        "label": "Surface style",
        "valid_values": "plain or other supported Instance setting value",
    },
    {
        "key": "status_icon_set",
        "label": "Status icon set",
        "valid_values": "classic, minimal, playful",
    },
    {
        "key": "typography_preset",
        "label": "Typography preset",
        "valid_values": "modern, grotesk, humanist",
    },
)


def contains_keyword(query: str, keywords: frozenset[str]) -> bool:
    tokens = set(re.split(r"[^a-z0-9]+", query.lower()))
    return bool(tokens.intersection(keywords))


def is_user_type_configuration_query(query: str) -> bool:
    normalized = query.lower()
    return bool(
        re.search(r"\buser\s+types?\b", normalized)
        or re.search(r"\bonboarding\b|\bonboard\b", normalized)
        or re.search(r"\buser\s+fields?\b", normalized)
    )


def _matches_scope(query: str, scope: str) -> bool:
    normalized = query.lower()
    if scope == "overview":
        return contains_keyword(query, OVERVIEW_KEYWORDS)
    if scope == "instance-settings":
        if is_user_type_configuration_query(query):
            return False
        if re.search(r"status[_\s-]?icon", normalized):
            return True
        return (
            contains_keyword(query, INSTANCE_VISUAL_IDENTITY_KEYWORDS)
            or contains_keyword(query, INSTANCE_COPY_KEYWORDS)
        )
    if scope == "health":
        if re.search(r"status[_\s-]?icon", normalized):
            return False
        return contains_keyword(query, HEALTH_KEYWORDS)
    if scope == "user-types":
        return (
            (
                is_user_type_configuration_query(query)
                or contains_keyword(query, USER_TYPES_KEYWORDS)
            )
            and not contains_keyword(query, AGENT_SETTINGS_KEYWORDS)
        )
    if scope == "agent-settings":
        return contains_keyword(query, AGENT_SETTINGS_KEYWORDS)
    if scope == "document-defaults":
        return contains_keyword(query, DOCUMENT_DEFAULTS_KEYWORDS)
    if scope == "deployment-settings":
        return contains_keyword(query, DEPLOYMENT_KEYWORDS)
    return False


def select_matching_scopes(query: str) -> list[str]:
    """Return all scopes matched by the query, ordered by classification priority."""
    matched = [scope for scope in SCOPE_PRIORITY if _matches_scope(query, scope)]
    return matched or ["overview"]


def select_scope(query: str) -> str:
    return select_matching_scopes(query)[0]


def resolve_included_scopes(
    query: str,
    *,
    mode: str,
    requested_scopes: list[str] | None = None,
) -> tuple[str, list[str]]:
    """
    Resolve primary and included scopes for a scoped config context request.

    Parameters:
        query: Admin configuration question used for auto classification.
        mode: `auto` classifies the query; `overview` forces overview scope.
        requested_scopes: Optional explicit scope hints for multi-scope reads.
    """
    if mode == "overview":
        return "overview", ["overview"]
    if mode == "full":
        return "overview", list(ALL_DOCUMENTED_SCOPES)

    primary_scope = select_scope(query)
    if requested_scopes:
        included_scopes = list(dict.fromkeys(requested_scopes))
        if primary_scope not in included_scopes:
            included_scopes.insert(0, primary_scope)
        return primary_scope, included_scopes

    matched_scopes = select_matching_scopes(query)
    if len(matched_scopes) > 1:
        return matched_scopes[0], matched_scopes
    return primary_scope, [primary_scope]


OVERVIEW_KEYWORDS: frozenset[str] = frozenset({
    "capabilities",
    "capability",
    "tool",
    "tools",
})

SCOPE_DESCRIPTIONS: dict[str, str] = {
    "overview": "High-level instance summary with instance name, description, and assistant identity.",
    "instance-settings": "Instance branding, theme, visual identity, and copy settings.",
    "deployment-settings": "Deployment environment settings including SMTP, SSL, model provider, and SearXNG configuration.",
    "agent-settings": "Sage agent behavior settings including prompts, max tokens, temperature, and personalization.",
    "user-types": "User type definitions and onboarding field configuration.",
    "document-defaults": "Document access defaults and ingestion policies per user type.",
    "health": "Service health, readiness, and restart-required deployment keys.",
}

CONFIDENCE_THRESHOLD = 0.7


def compute_scope_confidence(query: str, matched_scopes: list[str]) -> float:
    if not matched_scopes:
        return 0.0
    if matched_scopes == ["overview"]:
        return 0.9 if contains_keyword(query, OVERVIEW_KEYWORDS) else 0.3
    match_count = len(matched_scopes)
    if match_count == 1:
        return 0.9
    if match_count == 2:
        return 0.85
    if match_count == 3:
        return 0.8
    return 0.7


def build_available_scopes_response() -> list[dict[str, str]]:
    return [
        {"id": scope, "description": SCOPE_DESCRIPTIONS.get(scope, "")}
        for scope in ALL_DOCUMENTED_SCOPES
    ]


def select_deployment_category(query: str) -> str | None:
    for category, keywords in DEPLOYMENT_CATEGORY_KEYWORDS.items():
        if contains_keyword(query, keywords):
            return category
    return None


def visual_identity_settings(settings: dict[str, Any]) -> list[dict[str, str]]:
    values = []
    for item in INSTANCE_VISUAL_IDENTITY_SETTINGS:
        values.append({
            **item,
            "current_value": str(settings.get(item["key"], "")),
            "mutation": "PUT /admin/settings",
        })
    return values


def instance_settings_fields(settings: dict[str, Any]) -> list[dict[str, str]]:
    """Return branding, theme, and copy Instance Settings with mutation guidance."""
    fields: list[dict[str, str]] = []
    for item in (*INSTANCE_COPY_SETTINGS, *INSTANCE_VISUAL_IDENTITY_SETTINGS):
        fields.append({
            **item,
            "current_value": str(settings.get(item["key"], "")),
            "mutation": "PUT /admin/settings",
        })
    return fields


def build_instance_settings_change_set_example() -> dict[str, Any]:
    """Example Executable Change Set for Instance Settings updates."""
    return {
        "version": 1,
        "summary": "Update Instance branding, theme, and copy settings.",
        "requests": [
            {
                "method": "PUT",
                "path": "/admin/settings",
                "body": {
                    "instance_name": "Free Them",
                    "description": "PPST support instance",
                    "assistant_name": "Sage",
                    "default_theme": "dark",
                    "primary_color": "#3B82F6",
                    "chat_bubble_style": "soft",
                    "chat_bubble_shadow": True,
                    "surface_style": "plain",
                    "status_icon_set": "minimal",
                    "typography_preset": "modern",
                },
            },
        ],
    }
