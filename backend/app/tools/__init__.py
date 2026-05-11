"""Tools module for AI chat tool calling."""

from .base import BaseTool, ToolCallInfo, ToolDefinition, ToolResult
from .admin_config import AdminConfigTool
from .orchestrator import ToolOrchestrator
from .registry import ToolRegistry, get_registry, register_tool
from .sqlite_query import SQLiteQueryTool
from .web_search import WebSearchTool

__all__ = [
    "BaseTool",
    "AdminConfigTool",
    "ToolCallInfo",
    "ToolDefinition",
    "ToolResult",
    "ToolOrchestrator",
    "ToolRegistry",
    "get_registry",
    "register_tool",
    "SQLiteQueryTool",
    "WebSearchTool",
]


def init_tools() -> ToolRegistry:
    """Initialize and register all tools."""
    registry = get_registry()

    # Register tools
    registry.register(WebSearchTool())
    registry.register(SQLiteQueryTool())
    registry.register(AdminConfigTool())

    return registry
