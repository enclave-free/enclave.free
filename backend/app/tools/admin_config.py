from __future__ import annotations

"""Admin configuration context tool."""

import json
import logging
import re
from typing import Any, ClassVar

import database

from .base import BaseTool, ToolDefinition, ToolResult

logger = logging.getLogger("enclave.tools.admin_config")


class AdminConfigTool(BaseTool):
    """Read scoped admin configuration context for Admin Conversations."""

    ADMIN_VISIBLE_TOOL_CAPABILITIES: ClassVar[tuple[dict[str, str], ...]] = (
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

    DEPLOYMENT_KEYWORDS: ClassVar[frozenset[str]] = frozenset({
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

    INSTANCE_VISUAL_IDENTITY_KEYWORDS: ClassVar[frozenset[str]] = frozenset({
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

    AGENT_SETTINGS_KEYWORDS: ClassVar[frozenset[str]] = frozenset({
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

    INSTANCE_VISUAL_IDENTITY_SETTINGS: ClassVar[tuple[dict[str, str], ...]] = (
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

    DEPLOYMENT_CATEGORY_KEYWORDS: ClassVar[dict[str, frozenset[str]]] = {
        "email": frozenset({"smtp", "email"}),
        "domains": frozenset({"domain", "dns", "cors", "url"}),
        "ssl": frozenset({"ssl", "https", "tls", "certificate", "cert"}),
        "llm": frozenset({"provider", "model", "llm", "rag", "pdf"}),
        "search": frozenset({"searxng", "search"}),
    }

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="admin-config",
            description="Read scoped admin configuration context for Instance and Deployment settings.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The admin's configuration question",
                    }
                },
                "required": ["query"],
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            query = str(kwargs.get("query") or "")
            scope = self._select_scope(query)
            settings = database.get_all_settings()
            data: dict[str, Any] = {
                "scope": scope,
                "instance_settings": settings,
                "tool_capabilities": self.ADMIN_VISIBLE_TOOL_CAPABILITIES,
                "visual_identity_settings": self._visual_identity_settings(settings),
                "warnings": [],
            }
            if scope == "deployment-settings":
                category = self._select_deployment_category(query)
                data["deployment_settings"] = self._read_deployment_settings(category)
                data["deployment_category"] = category
            return ToolResult(
                success=True,
                data=data,
            )
        except Exception as e:
            logger.exception("Admin config tool execution failed")
            return ToolResult(success=False, data=None, error=str(e))

    @staticmethod
    def _contains_keyword(query: str, keywords: frozenset[str]) -> bool:
        tokens = set(re.split(r"[^a-z0-9]+", query.lower()))
        return bool(tokens.intersection(keywords))

    def _select_scope(self, query: str) -> str:
        if self._contains_keyword(query, self.INSTANCE_VISUAL_IDENTITY_KEYWORDS):
            return "instance-settings"
        if self._contains_keyword(query, self.AGENT_SETTINGS_KEYWORDS):
            return "agent-settings"
        if self._contains_keyword(query, self.DEPLOYMENT_KEYWORDS):
            return "deployment-settings"
        return "overview"

    def _select_deployment_category(self, query: str) -> str | None:
        for category, keywords in self.DEPLOYMENT_CATEGORY_KEYWORDS.items():
            if self._contains_keyword(query, keywords):
                return category
        return None

    def _read_deployment_settings(self, category: str | None) -> list[dict[str, Any]]:
        if category:
            return database.get_deployment_config_by_category(category)
        return database.get_all_deployment_config()

    def _visual_identity_settings(self, settings: dict[str, Any]) -> list[dict[str, str]]:
        values = []
        for item in self.INSTANCE_VISUAL_IDENTITY_SETTINGS:
            values.append({
                **item,
                "current_value": str(settings.get(item["key"], "")),
                "mutation": "PUT /admin/settings",
            })
        return values

    def _format_data(self, data: Any) -> str:
        lines = [
            "SCOPED CONFIG CONTEXT",
            f"scope: {data.get('scope', 'overview')}",
            "",
            "ADMIN-VISIBLE TOOL CAPABILITIES",
        ]
        for tool in data.get("tool_capabilities", []):
            lines.append(
                f"- {tool['id']} ({tool['name']}): {tool['description']} Access: {tool['access']}."
            )
        lines.extend([
            "",
            "INSTANCE SETTINGS",
            json.dumps(data.get("instance_settings", {}), indent=2, sort_keys=True),
        ])
        if data.get("scope") == "instance-settings":
            example_change_set = {
                "version": 1,
                "summary": "Update Instance visual identity settings.",
                "requests": [
                    {
                        "method": "PUT",
                        "path": "/admin/settings",
                        "body": {
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
            lines.extend([
                "",
                "INSTANCE VISUAL IDENTITY SETTINGS",
            ])
            for item in data.get("visual_identity_settings", []):
                lines.append(
                    f"- {item['key']} ({item['label']}): current value: {item['current_value']}; "
                    f"valid values: {item['valid_values']}; mutation: {item['mutation']}"
                )
            lines.extend([
                "",
                "CHANGESET FORMAT",
                "State-changing Admin Conversation writes require Admin Change Confirmation before apply.",
                "Use exactly one JSON change set. Instance Settings are updated with a partial PUT /admin/settings body.",
                "Do not include secret Deployment Settings unless the Admin explicitly requested setting them.",
                json.dumps(example_change_set, indent=2, sort_keys=True),
            ])
        if data.get("scope") == "agent-settings":
            lines.extend([
                "",
                "AGENT SETTINGS",
                "- prompt sections: use Agent Settings for Sage prompt behavior.",
                "- max tokens: use Agent Settings for response length controls.",
                "- temperature: use Agent Settings for model sampling behavior.",
                "- trace visibility: use Agent Settings for Conversation Trace policy.",
                "- personalization: use Agent Settings for user-type Sage behavior.",
            ])
        if data.get("scope") == "deployment-settings":
            category = data.get("deployment_category")
            title = f"DEPLOYMENT SETTINGS ({category})" if category else "DEPLOYMENT SETTINGS"
            lines.extend([
                "",
                title,
                json.dumps(data.get("deployment_settings", []), indent=2, sort_keys=True),
            ])
        return "\n".join(lines)
