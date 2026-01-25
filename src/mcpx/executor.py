"""MCP Executor - Executes tools through long-lived connections."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from mcpx.compression import ToonCompressor
from mcpx.registry import Registry

logger = logging.getLogger(__name__)

__all__ = ["ExecutionResult", "Executor"]


class ExecutionResult(BaseModel):
    """Result of tool execution.

    Attributes:
        server_name: Server name
        tool_name: Tool name
        success: Whether execution succeeded
        data: Compressed data (TOON format if compression enabled)
        raw_data: Original uncompressed data (for structuredContent)
        error: Error message if failed
        compressed: Whether data was compressed
        format: Data format ("json" or "toon")
    """

    server_name: str
    tool_name: str
    success: bool
    data: Any  # 压缩后的数据（用于 content）
    raw_data: Any = None  # 原始未压缩数据（用于 structuredContent）
    error: str | None = None
    compressed: bool = False
    format: str = "json"  # "json" or "toon"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "server_name": self.server_name,
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "raw_data": self.raw_data,
            "error": self.error,
            "compressed": self.compressed,
            "format": self.format,
        }


class Executor:
    """Executor for MCP tools using long-lived connections.

    Maintains connections to all MCP servers and routes tool execution.
    Connections stay active after execution.
    Optionally compresses results using TOON format.
    """

    def __init__(
        self,
        registry: Registry,
        toon_compression_enabled: bool = False,
        toon_compression_min_size: int = 3,
    ) -> None:
        """Initialize executor with registry.

        Args:
            registry: Registry with active connections
            toon_compression_enabled: Whether TOON compression is enabled
            toon_compression_min_size: Minimum size for compression
        """
        self._registry = registry
        self._compressor = ToonCompressor(
            enabled=toon_compression_enabled,
            min_size=toon_compression_min_size,
        )

    async def execute(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> ExecutionResult:
        """Execute a tool using a fresh session for each request.

        Args:
            server_name: Name of the server
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            ExecutionResult with success status and data or error
        """
        # Get client factory
        factory = self._registry.get_client_factory(server_name)
        if factory is None:
            return ExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"No client factory for server '{server_name}'",
            )

        # Create fresh client for this request
        client = factory()
        try:
            async with client:
                result = await client.call_tool(tool_name, arguments=arguments)

            # Extract data from result
            data = self._extract_result_data(result)

            # Apply TOON compression if enabled and beneficial
            compressed_data, was_compressed = self._compressor.compress(data)

            return ExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                success=True,
                data=compressed_data,
                raw_data=data,
                compressed=was_compressed,
                format="toon" if was_compressed else "json",
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

        透传策略:
        - 单项 TextContent: 尝试解析 JSON，否则返回 text
        - 单项 ImageContent/EmbeddedResource: 直接返回原始对象
        - 多项内容: 返回 list[Content]
        - 纯 JSON: 返回 dict/list 用于压缩

        Args:
            result: Result from call_tool

        Returns:
            原始 MCP 内容对象或 JSON 数据
        """
        from mcpx.content import is_multimodal_content

        logger.debug(f"Extracting data from result type: {type(result)}")

        # MCP protocol uses content attribute with list of content items
        if hasattr(result, "content"):
            content_list = result.content
            logger.debug(f"Result has content with {len(content_list) if content_list else 0} items")

            if not content_list:
                return None

            # 单项内容处理
            if len(content_list) == 1:
                first_item = content_list[0]
                logger.debug(f"First content item type: {type(first_item).__name__}")

                # TextContent: 尝试解析 JSON
                if hasattr(first_item, "text"):
                    text = first_item.text
                    return self._unwrap_json_string(text)

                # 多模态内容（ImageContent/EmbeddedResource）: 直接返回原始对象
                if is_multimodal_content(first_item):
                    logger.debug(f"Returning multimodal content: {type(first_item).__name__}")
                    return first_item

                # 其他类型: 返回字典表示
                if hasattr(first_item, "model_dump"):
                    return first_item.model_dump()
                return str(first_item)

            # 多项内容处理
            # 检查是否包含多模态内容
            has_multimodal = any(is_multimodal_content(item) for item in content_list)

            if has_multimodal:
                # 返回原始内容列表（保持多模态对象）
                logger.debug(f"Returning {len(content_list)} content items with multimodal content")
                return list(content_list)

            # 纯文本内容: 收集所有 text
            texts = []
            for item in content_list:
                if hasattr(item, "text"):
                    texts.append(item.text)
                elif hasattr(item, "model_dump"):
                    texts.append(item.model_dump())
                else:
                    texts.append(str(item))
            return texts if len(texts) > 1 else (texts[0] if texts else None)

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
