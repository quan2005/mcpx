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
    def test_method_parsing_valid(self, method_str: str, expected_server: str, expected_tool: str | None) -> None:
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


class TestDescribeAPI:
    """Tests for the describe tool with method parameter."""

    async def test_describe_with_server_only(self) -> None:
        """Test describe(method='server') returns all tools from server."""
        tmp_dir = TMP_DIR

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "describe", arguments={"method": "filesystem"}
            )

        content = _extract_text_content(result)
        tools = _parse_response(content)

        assert isinstance(tools, list)
        assert len(tools) > 0
        for tool in tools:
            assert "method" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["method"].startswith("filesystem.")

    async def test_describe_with_server_tool(self) -> None:
        """Test describe(method='server.tool') returns specific tool schema."""
        tmp_dir = TMP_DIR

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            # First get a tool name
            list_result = await client.call_tool(
                "describe", arguments={"method": "filesystem"}
            )
            tools = _parse_response(_extract_text_content(list_result))
            assert len(tools) > 0

            tool_name = tools[0]["method"].split(".", 1)[1]

            # Get specific tool
            result = await client.call_tool(
                "describe",
                arguments={"method": f"filesystem.{tool_name}"},
            )

        content = _extract_text_content(result)
        tool_info = _parse_response(content)

        assert "method" in tool_info
        assert tool_info["method"] == f"filesystem.{tool_name}"
        assert "description" in tool_info
        assert "input_schema" in tool_info

    async def test_describe_server_not_found(self) -> None:
        """Test describe returns error for non-existent server."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "describe", arguments={"method": "nonexistent"}
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()
        assert "available_servers" in error_info

    async def test_describe_tool_not_found(self) -> None:
        """Test describe returns error for non-existent tool."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "describe",
                arguments={"method": "filesystem.nonexistent"},
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()
        assert "available_tools" in error_info


class TestCallAPI:
    """Tests for the call tool with method parameter."""

    async def test_call_with_valid_method(self) -> None:
        """Test call(method='server.tool') with valid format."""
        tmp_dir = TMP_DIR

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "call",
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
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "call",
                arguments={"method": "filesystem"},
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "invalid method format" in error_info["error"].lower()

    async def test_call_server_not_found(self) -> None:
        """Test call returns error for non-existent server."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "call",
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
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "call",
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

    async def test_empty_method_parameter_describe(self) -> None:
        """Test describe handles empty method parameter."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "describe", arguments={"method": ""}
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()

    async def test_empty_method_parameter_call(self) -> None:
        """Test call handles empty method parameter."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "call", arguments={"method": ""}
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "invalid method format" in error_info["error"].lower()

    async def test_method_with_trailing_dot(self) -> None:
        """Test method parameter with trailing dot."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            # describe with trailing dot - should treat as server only
            result = await client.call_tool(
                "describe", arguments={"method": "filesystem."}
            )

        content = _extract_text_content(result)
        # "filesystem." splits to ("filesystem", "")
        # This should return tools for filesystem server
        data = _parse_response(content)
        if "error" not in data:
            # If not an error, should be a list of tools
            assert isinstance(data, list)

    async def test_multiple_dots_in_method(self) -> None:
        """Test method parameter with multiple dots."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            # "server.tool.extra" splits to ("server", "tool.extra")
            result = await client.call_tool(
                "describe", arguments={"method": "filesystem.tool.extra"}
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        # Should return error for tool not found
        assert "error" in error_info
        assert "not found" in error_info["error"].lower()


class TestSchemaCompressionInDescribe:
    """Tests for schema compression in describe API."""

    async def test_describe_returns_compressed_schema(self) -> None:
        """Test describe returns TypeScript compressed schema when enabled."""
        tmp_dir = TMP_DIR

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            ],
            schema_compression_enabled=True,
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "describe", arguments={"method": "filesystem"}
            )

        content = _extract_text_content(result)
        tools = _parse_response(content)

        assert isinstance(tools, list)
        assert len(tools) > 0
        # Check that input_schema is compressed (string format)
        for tool in tools:
            assert "input_schema" in tool
            # Compressed schema is a string (TypeScript type)
            assert isinstance(tool["input_schema"], str)

    async def test_describe_returns_uncompressed_schema(self) -> None:
        """Test describe returns JSON schema when compression disabled."""
        tmp_dir = TMP_DIR

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            ],
            schema_compression_enabled=False,
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "describe", arguments={"method": "filesystem"}
            )

        content = _extract_text_content(result)
        tools = _parse_response(content)

        assert isinstance(tools, list)
        assert len(tools) > 0
        # Check that input_schema is not compressed (dict format)
        for tool in tools:
            assert "input_schema" in tool
            # Uncompressed schema is a dict (JSON Schema)
            assert isinstance(tool["input_schema"], dict)


class TestToonCompressionInDescribe:
    """Tests for TOON compression in describe API."""

    async def test_describe_with_toon_compression(self) -> None:
        """Test describe returns TOON compressed content when enabled."""
        tmp_dir = TMP_DIR

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            ],
            toon_compression_enabled=True,
            toon_compression_min_size=2,
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "describe", arguments={"method": "filesystem"}
            )

        content = _extract_text_content(result)
        # TOON compressed content should be parseable by toons library
        parsed = _parse_response(content)
        assert isinstance(parsed, list)
        assert len(parsed) > 0

    async def test_describe_without_toon_compression(self) -> None:
        """Test describe returns plain JSON when TOON disabled."""
        tmp_dir = TMP_DIR

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            ],
            toon_compression_enabled=False,
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "describe", arguments={"method": "filesystem"}
            )

        content = _extract_text_content(result)
        # Should be plain JSON
        parsed = json.loads(content)
        assert isinstance(parsed, list)
        assert len(parsed) > 0
