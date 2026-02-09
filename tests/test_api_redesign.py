"""Test new describe/call API with method parameter.

This module tests the API redesign that uses a unified `method` parameter
for both describe and call tools, replacing the previous server_name/tool_name
split approach.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from mcpx.__main__ import McpServerConfig, ProxyConfig, create_server

# Module-level constant for temp directory path
TMP_DIR = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"


def _extract_text_content(result: Any) -> str:
    """Extract text content from CallToolResult."""
    if hasattr(result, "content"):
        content_list = result.content
        if content_list and len(content_list) > 0:
            first_item = content_list[0]
            if hasattr(first_item, "text"):
                text: Any = first_item.text
                return str(text)
    if hasattr(result, "data") and result.data is not None:
        data: Any = result.data
        return str(data)
    return str(result)


def _parse_response(content: str) -> Any:
    """Parse response, trying JSON first then TOON as fallback."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    try:
        import toons

        return toons.loads(content)
    except Exception:
        pass

    return content


class TestMethodParsing:
    """Test method string parsing logic."""

    @pytest.mark.parametrize(
        "method_str,expected_server,expected_tool",
        [
            ("server", "server", None),
            ("server.tool", "server", "tool"),
            ("my-server", "my-server", None),
            ("my-server.my_tool", "my-server", "my_tool"),
            ("filesystem.read_file", "filesystem", "read_file"),
            ("a.b", "a", "b"),
        ],
    )
    def test_method_parsing_valid(
        self, method_str: str, expected_server: str, expected_tool: str | None
    ) -> None:
        """Test valid method string parsing."""
        parts = method_str.split(".", 1)
        server_name = parts[0]
        tool_name = parts[1] if len(parts) > 1 else None

        assert server_name == expected_server
        assert tool_name == expected_tool

    @pytest.mark.parametrize(
        "method_str",
        [
            "",
            ".",
            ".tool",
            "server.",
            "server.tool.extra",
        ],
    )
    def test_method_parsing_edge_cases(self, method_str: str) -> None:
        """Test edge case method string parsing."""
        parts = method_str.split(".", 1)
        server_name = parts[0] if parts else ""
        tool_name = parts[1] if len(parts) > 1 else None

        # Verify parsing completes without error
        # (validation is handled by the API, not parsing)
        assert isinstance(server_name, str)
        assert tool_name is None or isinstance(tool_name, str)


class TestCallAPI:
    """Tests for the call tool with method parameter."""

    async def test_call_with_valid_method(self) -> None:
        """Test call(method='server.tool') with valid format."""
        tmp_dir = TMP_DIR

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "invoke",
                arguments={
                    "method": "filesystem.list_allowed_directories",
                    "arguments": {},
                },
            )

        content = _extract_text_content(result)
        # Should not be an error response
        if content.startswith("{"):
            parsed = _parse_response(content)
            assert "error" not in parsed, f"Unexpected error: {parsed.get('error')}"

    async def test_call_invalid_format_no_dot(self) -> None:
        """Test call(method='server') rejects format without tool name."""
        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            }
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "invoke",
                arguments={"method": "filesystem"},
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "invalid method format" in error_info["error"].lower()

    async def test_call_server_not_found(self) -> None:
        """Test call returns error for non-existent server."""
        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            }
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "invoke",
                arguments={
                    "method": "nonexistent.tool",
                    "arguments": {},
                },
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()

    async def test_call_tool_not_found(self) -> None:
        """Test call returns error for non-existent tool."""
        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            }
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "invoke",
                arguments={
                    "method": "filesystem.nonexistent",
                    "arguments": {},
                },
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()


class TestErrorHandling:
    """Tests for error handling with method parameter."""

    async def test_empty_method_parameter_call(self) -> None:
        """Test call handles empty method parameter."""
        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            }
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool("invoke", arguments={"method": ""})

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "invalid method format" in error_info["error"].lower()

    async def test_multiple_dots_in_method(self) -> None:
        """Test method parameter with multiple dots."""
        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            }
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            # "server.tool.extra" splits to ("server", "tool.extra")
            result = await client.call_tool(
                "invoke", arguments={"method": "filesystem.tool.extra", "arguments": {}}
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        # Should return error for tool not found
        assert "error" in error_info
        assert "not found" in error_info["error"].lower()
