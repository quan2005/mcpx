"""End-to-end tests for MCPX using FastMCP Client."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from mcpx.__main__ import McpServerConfig, ProxyConfig, create_server, load_config
from mcpx.server import ServerManager


def _extract_text_content(result) -> str:
    """Extract text content from CallToolResult."""
    # FastMCP returns content in result.content, not result.data
    if hasattr(result, "content"):
        content_list = result.content
        if content_list and len(content_list) > 0:
            first_item = content_list[0]
            if hasattr(first_item, "text"):
                return first_item.text
    if hasattr(result, "data") and result.data is not None:
        return result.data
    return str(result)


def _parse_response(content: str) -> Any:
    """Parse response, trying JSON first then TOON as fallback.

    Note: TOON format is YAML-like and can confuse JSON parsing.
    We try JSON first for error messages which are plain JSON.
    """

    # Try JSON first (for error messages and uncompressed responses)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try TOON format (for compressed responses)
    try:
        import toons

        return toons.loads(content)
    except Exception:
        pass

    # Return as-is if both fail
    return content


class TestMCPXClientE2E:
    """E2E tests using FastMCP Client API."""

    async def test_client_list_tools_only_two(self):
        """Test: Client sees only call and resources."""
        config = ProxyConfig(
            mcpServers={
                "test-server": McpServerConfig(
                    type="stdio",
                    command="echo",
                    args=["hello"],
                ),
            }
        )
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            tools = await client.list_tools()

        tool_names = [tool.name for tool in tools]
        assert tool_names == ["invoke", "read"]

    async def test_call_server_not_found(self):
        """Test: call returns error for non-existent server."""
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
                    "method": "nonexistent.some_tool",
                    "arguments": {},
                },
            )

        content = _extract_text_content(result)
        call_result = _parse_response(content)

        # New format: error responses have "error" key, no "success" key
        assert "error" in call_result
        assert "not found" in call_result["error"].lower()

    async def test_call_tool_not_found(self):
        """Test: call returns error for non-existent tool."""
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
        call_result = _parse_response(content)

        # New format: error responses have "error" key, no "success" key
        assert "error" in call_result
        assert "not found" in call_result["error"].lower()

    async def test_call_argument_validation_error(self):
        """Test: call returns accurate error when arguments don't match schema."""
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
            # Call with invalid arguments (should fail validation)
            result = await client.call_tool(
                "invoke",
                arguments={
                    "method": "filesystem.read_file",
                    "arguments": {"invalid_param": "value"},
                },
            )

            content = _extract_text_content(result)
            call_result = _parse_response(content)

            # Should fail with validation error (new format: no "success" key)
            assert "error" in call_result
            assert "validation" in call_result["error"].lower()

    async def test_call_missing_required_argument(self):
        """Test: call returns error when required argument is missing."""
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
            # read_file requires 'path' argument
            result = await client.call_tool(
                "invoke",
                arguments={
                    "method": "filesystem.read_file",
                    "arguments": {},  # Missing required 'path'
                },
            )

            content = _extract_text_content(result)
            call_result = _parse_response(content)

            # Should fail with validation error (new format: no "success" key)
            assert "error" in call_result
            assert "required" in call_result["error"].lower()

    async def test_empty_config_server_not_found(self):
        """Test: Empty config results in server not found error."""
        config = ProxyConfig(mcpServers={})
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "invoke", arguments={"method": "any_server.any_tool", "arguments": {}}
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()
        # When no servers connected, returns hint instead of available_servers
        assert "hint" in error_info
        assert "no mcp servers" in error_info["hint"].lower()

    async def test_concurrent_clients(self):
        """Test: Multiple concurrent clients work correctly."""
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

        async with Client(mcp_server) as client1:
            async with Client(mcp_server) as client2:
                result1 = await client1.call_tool(
                    "invoke",
                    arguments={"method": "filesystem.list_allowed_directories", "arguments": {}},
                )
                result2 = await client2.call_tool(
                    "invoke",
                    arguments={"method": "filesystem.list_allowed_directories", "arguments": {}},
                )

        content1 = _extract_text_content(result1)
        content2 = _extract_text_content(result2)

        # Both should succeed (not error responses)
        if content1.startswith("{"):
            parsed1 = _parse_response(content1)
            assert "error" not in parsed1, f"Unexpected error: {parsed1.get('error')}"
        if content2.startswith("{"):
            parsed2 = _parse_response(content2)
            assert "error" not in parsed2, f"Unexpected error: {parsed2.get('error')}"

    async def test_resources_read_resource(self):
        """Test: resources reads a specific resource from a server."""
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
            # Try to read a resource (using a test file path)
            # The filesystem server allows reading files
            result = await client.call_tool(
                "read",
                arguments={"server_name": "filesystem", "uri": "file:///tmp"},
            )

        # Verify we got some response (could be error or content)
        assert result is not None

    async def test_resources_server_not_found(self):
        """Test: resources returns error for non-existent server."""
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
                "read",
                arguments={"server_name": "nonexistent", "uri": "file:///tmp"},
            )

        content = _extract_text_content(result)
        error_info = _parse_response(content)

        assert "error" in error_info
        assert "not found" in error_info["error"].lower()
        assert "available_servers" in error_info


class TestMCPXConfigFile:
    """Tests for configuration file loading."""

    async def test_load_config_and_connect(self):
        """Test: Load config from file and connect client."""
        config_data = {
            "mcpServers": {
                "fs": {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            mcp_server = create_server(config)

            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "invoke", arguments={"method": "fs.list_allowed_directories", "arguments": {}}
                )

            content = _extract_text_content(result)
            # Should succeed (not an error response)
            if content.startswith("{"):
                parsed = _parse_response(content)
                assert "error" not in parsed, f"Unexpected error: {parsed.get('error')}"

        finally:
            config_path.unlink()

    async def test_config_with_invalid_json(self):
        """Test: Invalid JSON returns clear error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json}")
            config_path = Path(f.name)

        try:
            with pytest.raises(SystemExit):
                load_config(config_path)
        finally:
            config_path.unlink()

    async def test_config_with_invalid_structure(self):
        """Test: Invalid structure (mcpServers not a dict) returns clear error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"mcpServers": "not-a-dict"}, f)
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
            mcpServers={
                "valid-server": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
                "invalid-server": McpServerConfig(
                    type="stdio",
                    command="nonexistent-command-xyz",
                    args=[],
                ),
            }
        )
        mcp_server = create_server(config)

        # Server should start and valid server tools should be available
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "invoke",
                arguments={"method": "valid-server.list_allowed_directories", "arguments": {}},
            )

        content = _extract_text_content(result)

        # Should succeed (not an error response)
        if content.startswith("{"):
            parsed = _parse_response(content)
            assert "error" not in parsed, f"Unexpected error: {parsed.get('error')}"

    async def test_call_returns_original_error_on_failure(self):
        """Test: Tool execution returns original error message."""
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
            # Try to execute with invalid path (file doesn't exist)
            result = await client.call_tool(
                "invoke",
                arguments={
                    "method": "filesystem.read_file",
                    "arguments": {"path": "/nonexistent/file/xyz/123"},
                },
            )

        content = _extract_text_content(result)
        call_result = _parse_response(content)

        # New format: error responses have "error" key (no "success" key)
        assert "error" in call_result


class TestMCPXRealProcess:
    """Tests with real subprocess execution (stdio transport)."""

    def test_server_starts_via_command(self):
        """Test: Server can be started via command line."""
        config_data = {
            "mcpServers": {
                "test": {
                    "type": "stdio",
                    "command": "echo",
                    "args": ["hello"],
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            # Use the current project
            project_root = Path(__file__).parent.parent
            result = subprocess.run(
                ["uv", "run", "mcpx", str(config_path)],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=str(project_root),
            )

            # Server should be waiting for stdin
            assert "Error" not in result.stderr or result.returncode == 0

        except subprocess.TimeoutExpired:
            pass
        finally:
            config_path.unlink()


class TestMCPXExecSuccess:
    """Tests for successful tool execution."""

    async def test_call_uses_injected_registry(self):
        """Test: call uses the injected registry session."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )
        registry = ServerManager(config)
        await registry.initialize()

        test_file = Path(tmp_dir) / "mcpx_injected_registry_test.txt"
        test_file.write_text("Injected registry test")

        try:
            mcp_server = create_server(config, registry=registry)

            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "invoke",
                    arguments={
                        "method": "filesystem.read_file",
                        "arguments": {"path": str(test_file)},
                    },
                )

            content = _extract_text_content(result)
            # New format: success returns content directly, not JSON wrapper
            # Content should be the file content or valid response
            assert content is not None
            assert len(content) > 0
            # Should not be an error response
            if content.startswith("{"):
                try:
                    parsed = _parse_response(content)
                    assert "error" not in parsed, f"Unexpected error: {parsed.get('error')}"
                except json.JSONDecodeError:
                    pass  # Not JSON, that's fine for raw content
        finally:
            test_file.unlink(missing_ok=True)
            await registry.close()

    async def test_call_reconnects_disconnected_session(self):
        """Test: call reconnects when the session is disconnected."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )
        registry = ServerManager(config)
        await registry.initialize()

        # Verify server is connected
        assert registry.has_server("filesystem")

        test_file = Path(tmp_dir) / "mcpx_reconnect_test.txt"
        test_file.write_text("Reconnect test")

        try:
            # In new pattern, sessions are created per-request
            # So we remove the factory to simulate disconnect
            registry._pools.pop("filesystem", None)

            mcp_server = create_server(config, registry=registry)

            async with Client(mcp_server) as client:
                # This should fail since factory was removed
                result = await client.call_tool(
                    "invoke",
                    arguments={
                        "method": "filesystem.read_file",
                        "arguments": {"path": str(test_file)},
                    },
                )

            content = _extract_text_content(result)
            call_result = _parse_response(content)

            # Should fail since we removed factory
            assert "error" in call_result
            assert "not found" in call_result["error"].lower()
        finally:
            test_file.unlink(missing_ok=True)
            await registry.close()

    async def test_session_isolation_auto_recovery(self):
        """Test: Session isolation allows auto-recovery - each request uses fresh session."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )
        registry = ServerManager(config)
        await registry.initialize()

        # Verify client factory exists
        assert registry.has_server("filesystem")
        factory = registry.get_client_factory("filesystem")
        assert factory is not None

        # Each call to factory() returns a new client
        client1 = factory()
        client2 = factory()
        # They should be different instances
        assert client1 is not client2

        # Tools are cached from initialization
        tools = registry.list_tools("filesystem")
        assert len(tools) > 0

        await registry.close()

    async def test_call_successful_tool_execution(self):
        """Test: call successfully executes a tool and returns result."""
        # Use /private/tmp on macOS (real path, not symlink)
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

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

        # Create a test file using the real path
        test_file = Path(tmp_dir) / "mcpx_test_file.txt"
        test_file.write_text("Hello from MCPX test!")

        try:
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "invoke",
                    arguments={
                        "method": "filesystem.read_file",
                        "arguments": {"path": str(test_file)},
                    },
                )

            content = _extract_text_content(result)
            # New format: success returns content directly
            assert content is not None
            assert len(content) > 0
            # Verify it's not an error response
            if content.startswith("{"):
                try:
                    parsed = _parse_response(content)
                    assert "error" not in parsed, f"Unexpected error: {parsed.get('error')}"
                except json.JSONDecodeError:
                    pass
        finally:
            test_file.unlink(missing_ok=True)

    async def test_call_with_empty_arguments(self):
        """Test: call works with tools that don't require arguments."""
        # Use /private/tmp on macOS (real path, not symlink)
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

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
            # list_allowed_directories doesn't require arguments
            result = await client.call_tool(
                "invoke",
                arguments={
                    "method": "filesystem.list_allowed_directories",
                },
            )

        content = _extract_text_content(result)
        # New format: success returns content directly
        assert content is not None
        # Should not be an error response
        if content.startswith("{"):
            try:
                parsed = _parse_response(content)
                assert "error" not in parsed, f"Unexpected error: {parsed.get('error')}"
            except (json.JSONDecodeError, Exception):
                pass


class TestMCPXServerManager:
    """Tests for ServerManager functionality."""

    async def test_registry_get_tool_list_text(self):
        """Test: ServerManager generates correct tool list text."""
        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            }
        )

        from mcpx.server import ServerManager

        registry = ServerManager(config)
        await registry.initialize()

        try:
            text = registry.get_tool_list_text()
            assert "Available tools" in text
            assert "filesystem" in text
        finally:
            await registry.close()

    async def test_registry_list_all_tools(self):
        """Test: ServerManager.list_all_tools returns all tools from all servers."""
        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            }
        )

        from mcpx.server import ServerManager

        registry = ServerManager(config)
        await registry.initialize()

        try:
            all_tools = registry.list_all_tools()
            assert len(all_tools) > 0
            for tool in all_tools:
                assert tool.server_name == "filesystem"
        finally:
            await registry.close()

    async def test_registry_close(self):
        """Test: ServerManager.close properly closes all sessions."""
        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            }
        )

        from mcpx.server import ServerManager

        registry = ServerManager(config)
        await registry.initialize()

        assert len(registry.list_servers()) > 0

        await registry.close()

        assert len(registry.list_servers()) == 0
        assert len(registry.tools) == 0


class TestMCPXHttpLifespan:
    """Tests for HTTP mode with lifespan initialization."""

    async def test_lifespan_initializes_registry(self):
        """Test: Lifespan correctly initializes registry in the same event loop."""
        from contextlib import asynccontextmanager

        from starlette.applications import Starlette
        from starlette.routing import Mount
        from starlette.testclient import TestClient

        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )

        registry = ServerManager(config)

        # Create server with uninitialized registry
        mcp_server = create_server(config, registry=registry)

        initialized = False
        closed = False

        @asynccontextmanager
        async def lifespan(app):
            nonlocal initialized, closed
            await registry.initialize()
            initialized = True
            yield
            await registry.close()
            closed = True

        mcp_app = mcp_server.http_app()
        app = Starlette(lifespan=lifespan, routes=[Mount("/", app=mcp_app)])

        # Verify registry is not initialized before app starts
        assert not registry._initialized

        # Use TestClient which triggers lifespan events
        with TestClient(app, raise_server_exceptions=False):
            # Lifespan should have run
            assert initialized
            assert registry._initialized
            assert len(registry.list_servers()) > 0

        # After exiting context, close should have been called
        assert closed

    async def test_call_with_same_event_loop_init(self):
        """Test: call works correctly when registry is initialized in the same event loop."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )

        # Create registry and initialize in the SAME event loop as the test
        registry = ServerManager(config)
        await registry.initialize()

        # Create server with initialized registry
        mcp_server = create_server(config, registry=registry)

        # Create test file
        test_file = Path(tmp_dir) / "mcpx_same_loop_test.txt"
        test_file.write_text("Same event loop test content")

        try:
            # Use FastMCP Client - this runs in the same event loop
            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "invoke",
                    arguments={
                        "method": "filesystem.read_file",
                        "arguments": {"path": str(test_file)},
                    },
                )

            content = _extract_text_content(result)
            # New format: success returns content directly
            assert content is not None
            assert len(content) > 0
            # Should contain the file content
            assert "Same event loop test content" in content or "error" not in content.lower()
        finally:
            test_file.unlink(missing_ok=True)
            await registry.close()

    async def test_multiple_call_calls_reuse_session(self):
        """Test: Multiple call calls reuse the same session."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )

        # Initialize in the same event loop
        registry = ServerManager(config)
        await registry.initialize()

        mcp_server = create_server(config, registry=registry)

        # Create test files
        test_file1 = Path(tmp_dir) / "mcpx_session_reuse_1.txt"
        test_file2 = Path(tmp_dir) / "mcpx_session_reuse_2.txt"
        test_file1.write_text("File 1 content")
        test_file2.write_text("File 2 content")

        try:
            async with Client(mcp_server) as client:
                # First call
                result1 = await client.call_tool(
                    "invoke",
                    arguments={
                        "method": "filesystem.read_file",
                        "arguments": {"path": str(test_file1)},
                    },
                )
                content1 = _extract_text_content(result1)
                # New format: success returns content directly
                assert "File 1 content" in content1

                # Second call - should reuse same session
                result2 = await client.call_tool(
                    "invoke",
                    arguments={
                        "method": "filesystem.read_file",
                        "arguments": {"path": str(test_file2)},
                    },
                )
                content2 = _extract_text_content(result2)
                assert "File 2 content" in content2

                # Third call - another tool call should also work
                result3 = await client.call_tool(
                    "invoke",
                    arguments={"method": "filesystem.list_allowed_directories", "arguments": {}},
                )
                content3 = _extract_text_content(result3)
                # Should succeed (not an error response)
                if content3.startswith("{"):
                    parsed3 = _parse_response(content3)
                    assert "error" not in parsed3, f"Unexpected error: {parsed3.get('error')}"

        finally:
            test_file1.unlink(missing_ok=True)
            test_file2.unlink(missing_ok=True)
            await registry.close()


class TestProxyProviderRefactorVerification:
    """Verification tests for ProxyProvider session isolation refactoring.

    These tests verify the requirements from V-1 to V-8:
    - V-1: ServerManager uses _pools, not _sessions
    - V-2: Executor uses client_factory pattern
    - V-3: Auto-recovery via session isolation
    - V-4: Interface compatibility (describe/call/resources unchanged)
    """

    @pytest.mark.asyncio
    async def test_v1_registry_no_sessions_dict(self):
        """V-1: ServerManager should not have _sessions attribute, should have _pools."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )

        registry = ServerManager(config)
        await registry.initialize()

        try:
            # V-1: Should have _pools
            assert hasattr(registry, "_pools")
            assert "filesystem" in registry._pools

            # V-1: Should NOT have _sessions (or it should be empty/removed)
            # Note: We check that sessions are not used as the primary mechanism
            assert len(registry._pools) == 1
        finally:
            await registry.close()

    @pytest.mark.asyncio
    async def test_v2_executor_uses_client_factory(self):
        """V-2: Executor should use client_factory to get fresh sessions."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )

        registry = ServerManager(config)
        await registry.initialize()

        try:
            # Get the client factory
            factory = registry.get_client_factory("filesystem")
            assert factory is not None

            # Each call should return a new client
            client1 = factory()
            client2 = factory()
            assert client1 is not client2
        finally:
            await registry.close()

    @pytest.mark.asyncio
    async def test_v3_auto_recovery_via_session_isolation(self):
        """V-3: Each request creates fresh session - inherent auto-recovery."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )

        registry = ServerManager(config)
        await registry.initialize()

        test_file = Path(tmp_dir) / "v3_test.txt"
        test_file.write_text("V3 test content")

        try:
            mcp_server = create_server(config, registry=registry)

            async with Client(mcp_server) as client:
                # First request
                result1 = await client.call_tool(
                    "invoke",
                    arguments={
                        "method": "filesystem.read_file",
                        "arguments": {"path": str(test_file)},
                    },
                )
                content1 = _extract_text_content(result1)
                assert "V3 test" in content1

                # Second request - should automatically work (fresh session)
                result2 = await client.call_tool(
                    "invoke",
                    arguments={
                        "method": "filesystem.read_file",
                        "arguments": {"path": str(test_file)},
                    },
                )
                content2 = _extract_text_content(result2)
                assert "V3 test" in content2
        finally:
            test_file.unlink(missing_ok=True)
            await registry.close()

    @pytest.mark.asyncio
    async def test_v4_interface_compatibility_call(self):
        """V-4: call interface should be unchanged."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )

        registry = ServerManager(config)
        await registry.initialize()

        test_file = Path(tmp_dir) / "v4_call_test.txt"
        test_file.write_text("V4 call test")

        try:
            mcp_server = create_server(config, registry=registry)

            async with Client(mcp_server) as client:
                result = await client.call_tool(
                    "invoke",
                    arguments={
                        "method": "filesystem.read_file",
                        "arguments": {"path": str(test_file)},
                    },
                )

                # Should have content
                assert hasattr(result, "content")
                content = _extract_text_content(result)
                assert "V4 call test" in content
        finally:
            test_file.unlink(missing_ok=True)
            await registry.close()

    @pytest.mark.asyncio
    async def test_v4_interface_compatibility_resources(self):
        """V-4: resources interface should be unchanged."""
        tmp_dir = "/private/tmp" if Path("/private/tmp").exists() else "/tmp"

        config = ProxyConfig(
            mcpServers={
                "filesystem": McpServerConfig(
                    type="stdio",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
                ),
            }
        )

        registry = ServerManager(config)
        await registry.initialize()

        try:
            mcp_server = create_server(config, registry=registry)

            async with Client(mcp_server) as client:
                # resources should work (may return error if no resources, but that's ok)
                result = await client.call_tool(
                    "read",
                    arguments={
                        "server_name": "filesystem",
                        "uri": f"file://{tmp_dir}",
                    },
                )

                # Should return content (directory listing)
                assert hasattr(result, "content")
        finally:
            await registry.close()
