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
