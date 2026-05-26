from __future__ import annotations

"""Admin configuration context tool."""

import json
import logging
from typing import Any

import database

from .base import BaseTool, ToolDefinition, ToolResult
from .admin_config_context import (
    ADMIN_VISIBLE_TOOLS,
    build_available_scopes_response,
    compute_scope_confidence,
    CONFIDENCE_THRESHOLD,
    select_deployment_category,
    select_matching_scopes,
    select_scope,
    visual_identity_settings,
)

logger = logging.getLogger("enclave.tools.admin_config")


class AdminConfigTool(BaseTool):
    """Read scoped admin configuration context for Admin Conversations."""

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
            matched_scopes = select_matching_scopes(query)
            confidence = compute_scope_confidence(query, matched_scopes)
            if confidence < CONFIDENCE_THRESHOLD:
                return ToolResult(
                    success=False,
                    data={
                        "available_scopes": build_available_scopes_response(),
                        "confidence": confidence,
                    },
                    error=(
                        "Unable to confidently classify query. "
                        "Please clarify which configuration area you are asking about."
                    ),
                )
            scope = select_scope(query)
            settings = database.get_all_settings()
            data: dict[str, Any] = {
                "scope": scope,
                "instance_settings": settings,
                "tool_capabilities": ADMIN_VISIBLE_TOOLS,
                "visual_identity_settings": visual_identity_settings(settings),
                "warnings": [],
            }
            if scope == "deployment-settings":
                category = select_deployment_category(query)
                data["deployment_settings"] = self._read_deployment_settings(category)
                data["deployment_category"] = category
            return ToolResult(
                success=True,
                data=data,
            )
        except Exception as e:
            logger.exception("Admin config tool execution failed")
            return ToolResult(success=False, data=None, error=str(e))

    def _read_deployment_settings(self, category: str | None) -> list[dict[str, Any]]:
        if category:
            return database.get_deployment_config_by_category(category)
        return database.get_all_deployment_config()

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
                "Never call prose-only bullets or recommendations a Change Confirmation. A Change Confirmation requires exactly one valid JSON change set that the UI can validate and preview.",
                "If you already described changes in prose but did not emit JSON, the admin cannot apply them yet. On apply/confirm follow-up language, generate the missing JSON change set or ask one focused follow-up.",
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
