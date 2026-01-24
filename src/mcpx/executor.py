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
        except Exception as e:
            if self._is_connection_error(e):
                # Try to reconnect through registry
                logger.info(f"Connection error for '{server_name}', attempting reconnect...")
                reconnected = await self._registry.reconnect_server(server_name)
                if reconnected:
                    # Get new session and retry
                    new_session = self._registry.get_session(server_name)
                    if new_session is not None:
                        try:
                            result = await new_session.call_tool(
                                tool_name, arguments=arguments
                            )
                        except Exception as retry_error:
                            logger.error(
                                f"Error executing tool '{server_name}:{tool_name}' after reconnect: {retry_error}"
                            )
                            return ExecutionResult(
                                server_name=server_name,
                                tool_name=tool_name,
                                success=False,
                                data=None,
                                error=str(retry_error),
                            )
                    else:
                        return ExecutionResult(
                            server_name=server_name,
                            tool_name=tool_name,
                            success=False,
                            data=None,
                            error=f"Reconnected but no session for '{server_name}'",
                        )
                else:
                    return ExecutionResult(
                        server_name=server_name,
                        tool_name=tool_name,
                        success=False,
                        data=None,
                        error=f"Failed to reconnect to '{server_name}': {e}",
                    )
            else:
                logger.error(f"Error executing tool '{server_name}:{tool_name}': {e}")
                return ExecutionResult(
                    server_name=server_name,
                    tool_name=tool_name,
                    success=False,
                    data=None,
                    error=str(e),
                )

        # Extract data from result
        data = self._extract_result_data(result)

        return ExecutionResult(
            server_name=server_name,
            tool_name=tool_name,
            success=True,
            data=data,
        )

    def _extract_result_data(self, result: Any) -> Any:
        """Extract data from CallToolResult.

        Args:
            result: Result from call_tool

        Returns:
            Extracted data (JSON serializable)
        """
        logger.debug(f"Extracting data from result type: {type(result)}")

        # MCP protocol uses content attribute with list of content items
        if hasattr(result, "content"):
            content_list = result.content
            logger.debug(f"Result has content with {len(content_list) if content_list else 0} items")

            if content_list and len(content_list) > 0:
                # If multiple items, collect all text content
                if len(content_list) > 1:
                    texts = []
                    for item in content_list:
                        if hasattr(item, "text"):
                            texts.append(item.text)
                        elif hasattr(item, "model_dump"):
                            texts.append(item.model_dump())
                        else:
                            texts.append(str(item))
                    return texts if len(texts) > 1 else texts[0] if texts else None

                # Single item - extract its content
                first_item = content_list[0]
                logger.debug(f"First content item type: {type(first_item)}")

                if hasattr(first_item, "text"):
                    text = first_item.text
                    # Try to unwrap if it's a JSON-serialized string
                    return self._unwrap_json_string(text)
                # Return dict representation for other types (e.g., ImageContent)
                if hasattr(first_item, "model_dump"):
                    return first_item.model_dump()
                return str(first_item)

        # FastMCP 3.0+ may provide direct data access
        if hasattr(result, "data") and result.data is not None:
            data = result.data
            return self._ensure_serializable(data)

        # Fallback: try to serialize the entire result
        if hasattr(result, "model_dump"):
            return result.model_dump()

        return str(result)

    def _unwrap_json_string(self, text: str) -> Any:
        """Unwrap a JSON-serialized string if needed.

        Some MCP servers return JSON data as a serialized string, e.g.:
        - '"[{\\"key\\": \\"value\\"}]"' (JSON array serialized as string)
        - '{"key": "value"}' (already valid JSON object)

        This method tries to parse the text as JSON and unwrap it if it's
        a string containing JSON.

        Args:
            text: The text content from MCP response

        Returns:
            Parsed JSON data or the original text
        """
        if not text:
            return text

        import json

        # First, try to parse the text directly as JSON
        try:
            parsed = json.loads(text)
            # If parsing succeeds and result is a string, it might be double-encoded
            # Try to parse again
            if isinstance(parsed, str):
                try:
                    return json.loads(parsed)
                except (json.JSONDecodeError, TypeError):
                    return parsed
            return parsed
        except (json.JSONDecodeError, TypeError):
            # Not valid JSON, return as-is
            return text

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

    def _is_connection_error(self, error: Exception) -> bool:
        """Check if error indicates a connection problem that may be recoverable."""
        error_str = str(error)
        connection_indicators = [
            "Client is not connected",
            "nesting counter",
            "Connection closed",
            "Connection reset",
            "Connection refused",
            "Broken pipe",
        ]
        return any(indicator in error_str for indicator in connection_indicators)

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
