"""Admin configuration context tool."""

import json
from typing import Any

import database

from .base import BaseTool, ToolDefinition, ToolResult


class AdminConfigTool(BaseTool):
    """Read scoped admin configuration context for Admin Conversations."""

    DEPLOYMENT_KEYWORDS = {
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
    }

    DEPLOYMENT_CATEGORY_KEYWORDS = {
        "email": {"smtp", "email"},
        "domains": {"domain", "dns", "cors", "url"},
        "ssl": {"ssl", "https", "tls", "certificate", "cert"},
        "llm": {"provider", "model", "llm", "rag", "pdf"},
        "search": {"searxng", "search"},
    }

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="admin-config",
            description="Read scoped admin configuration context for Instance, Deployment, Agent, user type, document default, and health questions.",
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
            return ToolResult(success=False, data=None, error=str(e))

    def _select_scope(self, query: str) -> str:
        normalized = query.lower()
        if any(keyword in normalized for keyword in self.DEPLOYMENT_KEYWORDS):
            return "deployment-settings"
        return "overview"

    def _select_deployment_category(self, query: str) -> str | None:
        normalized = query.lower()
        for category, keywords in self.DEPLOYMENT_CATEGORY_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                return category
        return None

    def _read_deployment_settings(self, category: str | None) -> list[dict[str, Any]]:
        if category:
            return database.get_deployment_config_by_category(category)
        return database.get_all_deployment_config()

    def _format_data(self, data: Any) -> str:
        lines = [
            "SCOPED CONFIG CONTEXT",
            f"scope: {data.get('scope', 'overview')}",
            "",
            "INSTANCE SETTINGS",
            json.dumps(data.get("instance_settings", {}), indent=2, sort_keys=True),
        ]
        if data.get("scope") == "deployment-settings":
            category = data.get("deployment_category")
            title = f"DEPLOYMENT SETTINGS ({category})" if category else "DEPLOYMENT SETTINGS"
            lines.extend([
                "",
                title,
                json.dumps(data.get("deployment_settings", []), indent=2, sort_keys=True),
            ])
        return "\n".join(lines)
