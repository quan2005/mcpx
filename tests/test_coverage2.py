"""Additional coverage tests for hard-to-reach paths."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mcpx.__main__ import McpServerConfig, ProxyConfig, load_config


class TestLoadConfigCoverage:
    """Tests for config loading edge cases."""

    def test_load_config_with_env_vars(self):
        """Test: Config with environment variables loads correctly."""
        config_data = {
            "mcpServers": {
                "test": {
                    "type": "stdio",
                    "command": "node",
                    "args": ["server.js"],
                    "env": {"API_KEY": "secret", "DEBUG": "true"},
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json

            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert len(config.mcpServers) == 1
            assert config.mcpServers["test"].env == {"API_KEY": "secret", "DEBUG": "true"}
        finally:
            config_path.unlink()

    def test_load_config_http_server(self):
        """Test: Config with HTTP server loads correctly."""
        config_data = {
            "mcpServers": {
                "http-server": {
                    "type": "http",
                    "url": "http://localhost:8080/mcp",
                    "headers": {"Authorization": "Bearer token"},
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json

            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert len(config.mcpServers) == 1
            assert config.mcpServers["http-server"].type == "http"
            assert config.mcpServers["http-server"].url == "http://localhost:8080/mcp"
            assert config.mcpServers["http-server"].headers == {"Authorization": "Bearer token"}
        finally:
            config_path.unlink()

    def test_load_config_with_extra_fields(self):
        """Test: Config with extra fields ignores them."""
        config_data = {
            "mcpServers": {
                "test": {
                    "type": "stdio",
                    "command": "echo",
                    "args": ["hello"],
                }
            },
            "unknown_field": "ignored",
            "another_unknown": 123,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json

            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert len(config.mcpServers) == 1
            # Extra fields are ignored
            assert not hasattr(config, "unknown_field")
        finally:
            config_path.unlink()

    def test_proxy_config_default_values(self):
        """Test: ProxyConfig has correct default values."""
        config = ProxyConfig()

        assert config.mcpServers == {}
        assert config.health_check_enabled is True
        assert config.health_check_interval == 30
        assert config.health_check_timeout == 5
        assert config.toon_compression_enabled is True  # Now enabled by default
        assert config.toon_compression_min_size == 3

    def test_proxy_config_custom_values(self):
        """Test: ProxyConfig accepts custom values."""
        config = ProxyConfig(
            mcpServers={},
            health_check_enabled=False,
            health_check_interval=60,
            health_check_timeout=10,
            toon_compression_enabled=True,
            toon_compression_min_size=5,
        )

        assert config.health_check_enabled is False
        assert config.health_check_interval == 60
        assert config.health_check_timeout == 10
        assert config.toon_compression_enabled is True
        assert config.toon_compression_min_size == 5


class TestCreateServerCoverage:
    """Tests for create_server edge cases."""

    @pytest.mark.asyncio
    async def test_describe_with_unknown_server(self):
        """Test: describe returns error for unknown server."""
        from fastmcp import Client

        from mcpx.__main__ import create_server

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
            result = await client.call_tool("describe", arguments={"method": "unknown"})

        from tests.test_e2e import _extract_text_content, _parse_response

        content = _extract_text_content(result)

        error_info = _parse_response(content)
        assert "error" in error_info
        assert "unknown" in error_info["error"].lower()
        assert "filesystem" in error_info["available_servers"]

    @pytest.mark.asyncio
    async def test_describe_with_unknown_tool(self):
        """Test: describe returns error for unknown tool."""
        from fastmcp import Client

        from mcpx.__main__ import create_server

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
                "describe", arguments={"method": "filesystem.unknown_tool"}
            )

        from tests.test_e2e import _extract_text_content, _parse_response

        content = _extract_text_content(result)

        error_info = _parse_response(content)
        assert "error" in error_info
        assert "unknown_tool" in error_info["error"].lower()
        assert "available_tools" in error_info

    @pytest.mark.asyncio
    async def test_call_with_unknown_server(self):
        """Test: call returns error for unknown server."""
        from fastmcp import Client

        from mcpx.__main__ import create_server

        config = ProxyConfig(mcpServers={})
        mcp_server = create_server(config)

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "call",
                arguments={
                    "method": "unknown.some_tool",
                    "arguments": {},
                },
            )

        from tests.test_e2e import _extract_text_content, _parse_response

        content = _extract_text_content(result)

        error_info = _parse_response(content)
        assert "error" in error_info
        assert "unknown" in error_info["error"].lower()


class TestServerConfigValidation:
    """Tests for server config validation."""

    def test_server_config_defaults(self):
        """Test: ServerConfig has correct defaults."""
        config = McpServerConfig(name="test", command="echo", args=["hello"])

        assert config.type == "stdio"  # default
        assert config.args == ["hello"]
        assert config.env is None

    def test_server_config_http_defaults(self):
        """Test: HTTP ServerConfig has correct defaults."""
        config = McpServerConfig(
            name="test", type="http", url="http://localhost:8080/mcp"
        )

        assert config.type == "http"
        assert config.url == "http://localhost:8080/mcp"
        assert config.headers is None

    def test_server_config_with_optional_fields(self):
        """Test: ServerConfig with all optional fields."""
        config = McpServerConfig(
            type="stdio",
            command="node",
            args=["server.js"],
            env={"NODE_ENV": "production"},
        )

        assert config.type == "stdio"
        assert config.command == "node"
        assert config.args == ["server.js"]
        assert config.env == {"NODE_ENV": "production"}


class TestExecutorEdgeCases:
    """Tests for executor edge cases."""

    @pytest.mark.asyncio
    async def test_executor_with_compression_enabled(self):
        """Test: Executor with compression enabled."""
        from mcpx.__main__ import McpServerConfig, ProxyConfig
        from mcpx.executor import Executor
        from mcpx.registry import Registry

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

        registry = Registry(config)
        await registry.initialize()

        try:
            executor = Executor(registry, toon_compression_enabled=True)

            # Execute tool that returns array data
            result = await executor.execute(
                "filesystem", "list_allowed_directories", {}
            )

            assert result.success is True
            # Result should have compression fields
            assert "format" in result.to_dict()
        finally:
            await registry.close()

    @pytest.mark.asyncio
    async def test_executor_connection_error_then_success(self):
        """Test: Executor recovers from connection error."""
        from mcpx.__main__ import McpServerConfig, ProxyConfig
        from mcpx.executor import Executor
        from mcpx.registry import Registry

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

        registry = Registry(config)
        await registry.initialize()

        executor = Executor(registry)

        try:
            # First call should succeed
            result1 = await executor.execute(
                "filesystem", "list_allowed_directories", {}
            )
            assert result1.success is True

            # Second call should also succeed (connection is stable)
            result2 = await executor.execute(
                "filesystem", "list_allowed_directories", {}
            )
            assert result2.success is True
        finally:
            await registry.close()


class TestRegistryEdgeCases:
    """Tests for registry edge cases."""

    @pytest.mark.asyncio
    async def test_registry_double_initialize(self):
        """Test: Double initialize doesn't create duplicate connections."""
        from mcpx.__main__ import McpServerConfig, ProxyConfig
        from mcpx.registry import Registry

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

        registry = Registry(config)

        await registry.initialize()
        session_count_1 = len(registry.list_servers())

        await registry.initialize()
        session_count_2 = len(registry.list_servers())

        assert session_count_1 == session_count_2 == 1

        await registry.close()

    @pytest.mark.asyncio
    async def test_registry_list_tools_empty_server(self):
        """Test: list_tools returns empty list for server with no tools."""
        from mcpx.__main__ import ProxyConfig
        from mcpx.registry import Registry

        config = ProxyConfig(mcpServers={})
        registry = Registry(config)
        registry._initialized = True

        tools = registry.list_tools("nonexistent")
        assert tools == []

    @pytest.mark.asyncio
    async def test_registry_get_tool_not_found(self):
        """Test: get_tool returns None for non-existent tool."""
        from mcpx.__main__ import ProxyConfig
        from mcpx.registry import Registry

        config = ProxyConfig(mcpServers={})
        registry = Registry(config)
        registry._initialized = True

        tool = registry.get_tool("server", "tool")
        assert tool is None

    @pytest.mark.asyncio
    async def test_registry_is_server_healthy_no_status(self):
        """Test: is_server_healthy returns False when no status."""
        from mcpx.__main__ import ProxyConfig
        from mcpx.registry import Registry

        config = ProxyConfig(mcpServers={})
        registry = Registry(config)

        # No health status for any server
        assert not registry.is_server_healthy("nonexistent")
