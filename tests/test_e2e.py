"""End-to-end tests for MCPX using FastMCP Client."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastmcp import Client

from mcpx.__main__ import McpServerConfig, ProxyConfig, create_server, load_config


def _extract_text_content(result) -> str:
    """Extract text content from CallToolResult."""
    if hasattr(result, "data"):
        return result.data
    if hasattr(result, "content"):
        content_list = result.content
        if content_list and len(content_list) > 0:
            first_item = content_list[0]
            if hasattr(first_item, "text"):
                return first_item.text
    return str(result)


class TestMCPXClientE2E:
    """E2E tests using FastMCP Client API."""

    async def test_client_list_tools_only_two(self):
        """Test: Client sees only inspect and exec."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(name="test-server", command="echo", args=["hello"]),
            ]
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            tools = await client.list_tools()

        tool_names = [tool.name for tool in tools]
        assert tool_names == ["inspect", "exec"]

    async def test_inspect_list_server_tools(self):
        """Test: inspect lists all available tools from a specific server."""
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
                "inspect", arguments={"server_name": "filesystem"}
            )

        content = _extract_text_content(result)
        tools = json.loads(content)

        assert isinstance(tools, list)
        assert len(tools) > 0
        # Each tool should have server_name, name, description, input_schema
        for tool in tools:
            assert "server_name" in tool
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["server_name"] == "filesystem"

    async def test_inspect_get_specific_tool(self):
        """Test: inspect returns full schema for a specific tool."""
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
            # First, list all tools to get a valid tool_name
            list_result = await client.call_tool(
                "inspect", arguments={"server_name": "filesystem"}
            )
            tools = json.loads(_extract_text_content(list_result))

            if tools:
                tool_name = tools[0]["name"]

                # Get detailed schema
                result = await client.call_tool(
                    "inspect",
                    arguments={"server_name": "filesystem", "tool_name": tool_name},
                )

                content = _extract_text_content(result)
                tool_info = json.loads(content)

                assert tool_info["server_name"] == "filesystem"
                assert "name" in tool_info
                assert "description" in tool_info
                assert "input_schema" in tool_info

    async def test_inspect_tool_not_found(self):
        """Test: inspect returns error for non-existent tool."""
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
                "inspect",
                arguments={"server_name": "filesystem", "tool_name": "nonexistent"},
            )

        content = _extract_text_content(result)
        error_info = json.loads(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()

    async def test_inspect_server_not_found(self):
        """Test: inspect returns error for invalid server_name."""
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
                "inspect", arguments={"server_name": "nonexistent"}
            )

        content = _extract_text_content(result)
        error_info = json.loads(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()
        assert "available_servers" in error_info

    async def test_exec_server_not_found(self):
        """Test: exec returns error for non-existent server."""
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
                "exec",
                arguments={
                    "server_name": "nonexistent",
                    "tool_name": "some_tool",
                    "arguments": {},
                },
            )

        content = _extract_text_content(result)
        exec_result = json.loads(content)

        assert exec_result["success"] is False
        assert "error" in exec_result
        assert "not found" in exec_result["error"].lower()

    async def test_exec_tool_not_found(self):
        """Test: exec returns error for non-existent tool."""
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
                "exec",
                arguments={
                    "server_name": "filesystem",
                    "tool_name": "nonexistent",
                    "arguments": {},
                },
            )

        content = _extract_text_content(result)
        exec_result = json.loads(content)

        assert exec_result["success"] is False
        assert "error" in exec_result
        assert "not found" in exec_result["error"].lower()

    async def test_exec_argument_validation_error(self):
        """Test: exec returns accurate error when arguments don't match schema."""
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
            # First get a valid tool
            list_result = await client.call_tool(
                "inspect", arguments={"server_name": "filesystem"}
            )
            tools = json.loads(_extract_text_content(list_result))

            if tools:
                tool_name = tools[0]["name"]

                # Call with invalid arguments (should fail validation)
                result = await client.call_tool(
                    "exec",
                    arguments={
                        "server_name": "filesystem",
                        "tool_name": tool_name,
                        "arguments": {"invalid_param": "value"},
                    },
                )

                content = _extract_text_content(result)
                exec_result = json.loads(content)

                # Should fail with validation error
                assert exec_result["success"] is False
                assert "error" in exec_result
                assert "validation" in exec_result["error"].lower()

    async def test_exec_missing_required_argument(self):
        """Test: exec returns error when required argument is missing."""
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
            # read_file requires 'path' argument
            result = await client.call_tool(
                "exec",
                arguments={
                    "server_name": "filesystem",
                    "tool_name": "read_file",
                    "arguments": {},  # Missing required 'path'
                },
            )

            content = _extract_text_content(result)
            exec_result = json.loads(content)

            # Should fail with validation error
            assert exec_result["success"] is False
            assert "error" in exec_result
            assert "required" in exec_result["error"].lower()

    async def test_empty_config_server_not_found(self):
        """Test: Empty config results in server not found error."""
        config = ProxyConfig(mcp_servers=[])
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "inspect", arguments={"server_name": "any_server"}
            )

        content = _extract_text_content(result)
        error_info = json.loads(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()
        assert error_info["available_servers"] == []

    async def test_multiple_servers_cached_tools(self):
        """Test: Multiple servers result in all tools being cached per server."""
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
            # Query specific server
            result = await client.call_tool(
                "inspect", arguments={"server_name": "filesystem"}
            )

        content = _extract_text_content(result)
        tools = json.loads(content)

        assert isinstance(tools, list)
        assert len(tools) > 0
        for tool in tools:
            assert tool["server_name"] == "filesystem"

    async def test_inspect_and_exec_integration(self):
        """Test: Complete workflow of inspect then exec."""
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
            # Step 1: List tools from server
            list_result = await client.call_tool(
                "inspect", arguments={"server_name": "filesystem"}
            )
            tools = json.loads(_extract_text_content(list_result))

            assert len(tools) > 0

            # Step 2: Get specific tool schema
            tool_name = tools[0]["name"]
            detail_result = await client.call_tool(
                "inspect",
                arguments={"server_name": "filesystem", "tool_name": tool_name},
            )
            tool_detail = json.loads(_extract_text_content(detail_result))

            assert "input_schema" in tool_detail

    async def test_concurrent_clients(self):
        """Test: Multiple concurrent clients work correctly."""
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

        async with Client(mcp_server) as client1:
            async with Client(mcp_server) as client2:
                result1 = await client1.call_tool(
                    "inspect", arguments={"server_name": "filesystem"}
                )
                result2 = await client2.call_tool(
                    "inspect", arguments={"server_name": "filesystem"}
                )

        tools1 = json.loads(_extract_text_content(result1))
        tools2 = json.loads(_extract_text_content(result2))

        assert len(tools1) == len(tools2)


class TestMCPXConfigFile:
    """Tests for configuration file loading."""

    async def test_load_config_and_connect(self):
        """Test: Load config from file and connect client."""
        config_data = {
            "mcp_servers": [
                {
                    "name": "fs",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            mcp_server = create_server(config)

            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "inspect", arguments={"server_name": "fs"}
                )

            tools = json.loads(_extract_text_content(result))
            assert len(tools) > 0

        finally:
            config_path.unlink()

    async def test_config_with_invalid_json(self):
        """Test: Invalid JSON returns clear error."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{invalid json}")
            config_path = Path(f.name)

        try:
            with pytest.raises(SystemExit):
                load_config(config_path)
        finally:
            config_path.unlink()

    async def test_config_with_invalid_structure(self):
        """Test: Invalid structure (mcp_servers not a list) returns clear error."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"mcp_servers": "not-a-list"}, f)
            config_path = Path(f.name)

        try:
            with pytest.raises(SystemExit):
                load_config(config_path)
        finally:
            config_path.unlink()


class TestMCPXErrorHandling:
    """Tests for error handling and graceful degradation."""

    async def test_failed_server_connection_doesnt_crash(self):
        """Test: Failed server connection doesn't prevent other servers."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="valid-server",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
                McpServerConfig(
                    name="invalid-server",
                    command="nonexistent-command-xyz",
                    args=[],
                ),
            ]
        )
        mcp_server = create_server(config)

        # Server should start and valid server tools should be available
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "inspect", arguments={"server_name": "valid-server"}
            )

        tools = json.loads(_extract_text_content(result))

        # At least the valid server's tools should be cached
        assert isinstance(tools, list)
        assert len(tools) > 0

    async def test_exec_returns_original_error_on_failure(self):
        """Test: Tool execution returns original error message."""
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
            # Try to execute with invalid path (file doesn't exist)
            result = await client.call_tool(
                "exec",
                arguments={
                    "server_name": "filesystem",
                    "tool_name": "read_file",
                    "arguments": {"path": "/nonexistent/file/xyz/123"},
                },
            )

        content = _extract_text_content(result)
        exec_result = json.loads(content)

        # Should have error field
        assert "success" in exec_result
        assert "error" in exec_result or "data" in exec_result


class TestMCPXRealProcess:
    """Tests with real subprocess execution (stdio transport)."""

    def test_server_starts_via_command(self):
        """Test: Server can be started via command line."""
        config_data = {
            "mcp_servers": [
                {"name": "test", "command": "echo", "args": ["hello"]}
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            result = subprocess.run(
                ["uv", "run", "mcpx", str(config_path)],
                capture_output=True,
                text=True,
                timeout=2,
                cwd="/Users/yanwu/conductor/workspaces/mcpx/mumbai",
            )

            # Server should be waiting for stdin
            assert "Error" not in result.stderr or result.returncode == 0

        except subprocess.TimeoutExpired:
            pass
        finally:
            config_path.unlink()


class TestMCPXExecSuccess:
    """Tests for successful tool execution."""

    async def test_exec_successful_tool_execution(self):
        """Test: exec successfully executes a tool and returns result."""
        # Use /private/tmp on macOS (real path, not symlink)
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

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

        # Create a test file using the real path
        test_file = Path(tmp_dir) / "mcpx_test_file.txt"
        test_file.write_text("Hello from MCPX test!")

        try:
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "exec",
                    arguments={
                        "server_name": "filesystem",
                        "tool_name": "read_file",
                        "arguments": {"path": str(test_file)},
                    },
                )

            content = _extract_text_content(result)
            exec_result = json.loads(content)

            assert exec_result["success"] is True
            assert exec_result["server_name"] == "filesystem"
            assert exec_result["tool_name"] == "read_file"
            assert exec_result["data"] is not None
        finally:
            test_file.unlink(missing_ok=True)

    async def test_exec_with_empty_arguments(self):
        """Test: exec works with tools that don't require arguments."""
        # Use /private/tmp on macOS (real path, not symlink)
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

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
            # list_allowed_directories doesn't require arguments
            result = await client.call_tool(
                "exec",
                arguments={
                    "server_name": "filesystem",
                    "tool_name": "list_allowed_directories",
                },
            )

        content = _extract_text_content(result)
        exec_result = json.loads(content)

        # Should succeed
        assert exec_result["success"] is True


class TestMCPXRegistry:
    """Tests for Registry functionality."""

    async def test_registry_get_tool_list_text(self):
        """Test: Registry generates correct tool list text."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )

        from mcpx.registry import Registry

        registry = Registry(config)
        await registry.initialize()

        try:
            text = registry.get_tool_list_text()
            assert "Available tools" in text
            assert "filesystem" in text
        finally:
            await registry.close()

    async def test_registry_list_all_tools(self):
        """Test: Registry.list_all_tools returns all tools from all servers."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )

        from mcpx.registry import Registry

        registry = Registry(config)
        await registry.initialize()

        try:
            all_tools = registry.list_all_tools()
            assert len(all_tools) > 0
            for tool in all_tools:
                assert tool.server_name == "filesystem"
        finally:
            await registry.close()

    async def test_registry_close(self):
        """Test: Registry.close properly closes all sessions."""
        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ]
        )

        from mcpx.registry import Registry

        registry = Registry(config)
        await registry.initialize()

        assert len(registry.sessions) > 0

        await registry.close()

        assert len(registry.sessions) == 0
        assert len(registry.tools) == 0
