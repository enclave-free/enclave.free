from __future__ import annotations

import re
from typing import Any


ADMIN_VISIBLE_TOOL_CAPABILITIES: tuple[dict[str, str], ...] = (
    {
        "id": "web-search",
        "name": "Web Search",
        "access": "all users when enabled",
        "description": "Looks up current or external information through the configured SearXNG service.",
    },
    {
        "id": "admin-config",
        "name": "Admin Config",
        "access": "admins only",
        "description": "Reads scoped admin configuration context and can support confirmed configuration changes.",
    },
    {
        "id": "db-query",
        "name": "Database",
        "access": "admins only",
        "description": "Runs safe read-only admin database queries for troubleshooting and inspection.",
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


def select_scope(query: str) -> str:
    if contains_keyword(query, INSTANCE_VISUAL_IDENTITY_KEYWORDS):
        return "instance-settings"
    if contains_keyword(query, AGENT_SETTINGS_KEYWORDS):
        return "agent-settings"
    if contains_keyword(query, DEPLOYMENT_KEYWORDS):
        return "deployment-settings"
    return "overview"


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
