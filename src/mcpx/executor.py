"""MCP Executor - Executes tools through long-lived connections."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from mcpx.registry import Registry

logger = logging.getLogger(__name__)

__all__ = ["ExecutionResult", "Executor"]


class ExecutionResult(BaseModel):
    """Result of tool execution."""

    server_name: str
    tool_name: str
    success: bool
    data: Any
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "server_name": self.server_name,
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }


class Executor:
    """Executor for MCP tools using long-lived connections.

    Maintains connections to all MCP servers and routes tool execution.
    Connections stay active after execution.
    """

    def __init__(self, registry: Registry) -> None:
        """Initialize executor with registry.

        Args:
            registry: Registry with active connections
        """
        self._registry = registry

    async def execute(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> ExecutionResult:
        """Execute a tool through the appropriate server connection.

        Args:
            server_name: Name of the server
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            ExecutionResult with success status and data or error
        """
        # Get session
        session = self._registry.get_session(server_name)
        if session is None:
            return ExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"No active connection to server '{server_name}'",
            )

        # Execute tool
        try:
            result = await session.call_tool(tool_name, arguments=arguments)

            # Extract data from result
            data = self._extract_result_data(result)

            return ExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                success=True,
                data=data,
            )

        except Exception as e:
            logger.error(f"Error executing tool '{server_name}:{tool_name}': {e}")
            return ExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                success=False,
                data=None,
                error=str(e),
            )

    def _extract_result_data(self, result: Any) -> Any:
        """Extract data from CallToolResult.

        Args:
            result: Result from call_tool

        Returns:
            Extracted data (JSON serializable)
        """
        # FastMCP 3.0+ provides direct data access
        if hasattr(result, "data"):
            data = result.data
            # Ensure data is JSON serializable
            return self._ensure_serializable(data)

        # Older versions use content attribute
        if hasattr(result, "content"):
            content_list = result.content
            if content_list and len(content_list) > 0:
                # Extract text from first item
                first_item = content_list[0]
                if hasattr(first_item, "text"):
                    return first_item.text
                # Return dict representation
                if hasattr(first_item, "model_dump"):
                    return first_item.model_dump()
                return str(first_item)

        return str(result)

    def _ensure_serializable(self, data: Any) -> Any:
        """Ensure data is JSON serializable.

        Args:
            data: Data to check/convert

        Returns:
            JSON serializable data
        """
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool)):
            return data
        if isinstance(data, (list, tuple)):
            return [self._ensure_serializable(item) for item in data]
        if isinstance(data, dict):
            return {k: self._ensure_serializable(v) for k, v in data.items()}
        # Handle pydantic models
        if hasattr(data, "model_dump"):
            return data.model_dump()
        # Fallback to string representation
        return str(data)

    async def execute_many(
        self, calls: list[tuple[str, str, dict[str, Any]]]
    ) -> list[ExecutionResult]:
        """Execute multiple tools.

        Args:
            calls: List of (server_name, tool_name, arguments) tuples

        Returns:
            List of ExecutionResult objects
        """
        results = []
        for server_name, tool_name, arguments in calls:
            result = await self.execute(server_name, tool_name, arguments)
            results.append(result)
        return results
