"""Additional tests to improve code coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcpx.__main__ import McpServerConfig, ProxyConfig
from mcpx.compression import ToonCompressor, compress_toon, is_compressible
from mcpx.executor import Executor


class TestExecutorCoverage:
    """Tests to improve executor coverage."""

    @pytest.mark.asyncio
    async def test_executor_session_not_connected(self):
        """Test: Executor handles no client factory gracefully."""
        from mcpx.registry import Registry

        config = ProxyConfig(mcpServers={})
        registry = Registry(config)
        registry._initialized = True  # Skip initialization

        executor = Executor(registry)

        result = await executor.execute("nonexistent", "some_tool", {})
        assert not result.success
        assert "No client factory" in result.error

    @pytest.mark.asyncio
    async def test_executor_creates_fresh_session(self):
        """Test: Executor creates fresh session for each request."""
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
            # Each execution creates a fresh session via factory
            result1 = await executor.execute("filesystem", "list_allowed_directories", {})
            assert result1.success

            result2 = await executor.execute("filesystem", "list_allowed_directories", {})
            assert result2.success

            # Both should succeed because each request gets a fresh session
        finally:
            await registry.close()

    @pytest.mark.asyncio
    async def test_executor_non_connection_error(self):
        """Test: Executor handles non-connection errors."""
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
            # Try to execute non-existent tool - should get error but not connection error
            result = await executor.execute("filesystem", "nonexistent_tool", {})
            # This should fail with tool error, not connection error
            assert not result.success
            assert result.error is not None
        finally:
            await registry.close()


class TestCompressionCoverage:
    """Tests to improve compression coverage."""

    def test_toon_compressor_available_package(self):
        """Test: Compressor works when toons package is available."""
        compressor = ToonCompressor(enabled=True)

        # The package should be available (we have toons installed)
        assert compressor._toon_available

        # Test compression attempt
        data = [{"id": i} for i in range(10)]
        result, was_compressed = compressor.compress(data)
        # Should return TOON compressed data
        assert was_compressed
        # TOON format is different from JSON
        assert isinstance(result, str)

    def test_toon_compressor_encode_error(self):
        """Test: Compressor handles encoding errors."""
        compressor = ToonCompressor(enabled=True)

        # Create data that might cause encoding issues
        class BadData:
            def __str__(self):
                raise ValueError("Cannot encode")

        # Should handle gracefully - falls back to original data on error
        result, was_compressed = compressor.compress({"key": BadData()})
        # On error, returns original data without compression
        assert not was_compressed

    def test_compress_toon_convenience(self):
        """Test: compress_toon convenience function."""
        data = [{"id": i} for i in range(10)]

        # Test with enabled=False
        result = compress_toon(data, enabled=False)
        assert result == data

        # Test with small data (won't compress)
        result = compress_toon({"a": 1})
        assert result == {"a": 1}

    def test_is_compressible_edge_cases(self):
        """Test: is_compressible with edge cases."""
        # Empty structures
        assert not is_compressible([])
        assert not is_compressible({})

        # Single item
        assert not is_compressible([{"a": 1}], min_size=2)

        # Large object
        large_obj = {f"key{i}": f"value{i}" for i in range(10)}
        assert is_compressible(large_obj, min_size=5)

        # Mixed array just at threshold
        mixed = [{"a": i} if i % 2 == 0 else i for i in range(8)]
        assert is_compressible(mixed, min_size=4)


class TestRegistryCoverage:
    """Tests to improve registry coverage."""

    @pytest.mark.asyncio
    async def test_registry_get_client_factory_nonexistent_server(self):
        """Test: Getting factory for non-existent server returns None."""
        from mcpx.registry import Registry

        config = ProxyConfig(mcpServers={})
        registry = Registry(config)

        factory = registry.get_client_factory("nonexistent")
        assert factory is None

    @pytest.mark.asyncio
    async def test_registry_get_server_info_not_found(self):
        """Test: Getting info for non-existent server returns None."""
        from mcpx.registry import Registry

        config = ProxyConfig(mcpServers={})
        registry = Registry(config)

        info = registry.get_server_info("nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_registry_close_all_sessions(self):
        """Test: Close properly clears all data."""
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

        assert len(registry.list_servers()) > 0
        assert len(registry.tools) > 0

        await registry.close()

        assert len(registry.list_servers()) == 0
        assert len(registry.tools) == 0
        assert not registry._initialized

    @pytest.mark.asyncio
    async def test_registry_session_isolation_pattern(self):
        """Test: Registry uses session isolation - each request gets fresh client."""
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

        # Verify client factory works
        factory = registry.get_client_factory("filesystem")
        assert factory is not None

        # Each call creates a new client instance
        client1 = factory()
        client2 = factory()
        assert client1 is not client2

        await registry.close()

    def test_get_tool_list_text_empty(self):
        """Test: get_tool_list_text returns message when no tools."""
        from mcpx.registry import Registry

        config = ProxyConfig(mcpServers={})
        registry = Registry(config)

        text = registry.get_tool_list_text()
        assert "No tools available" in text


class TestConfigCoverage:
    """Tests to improve config coverage."""

    def test_server_config_validation_http_missing_url(self):
        """Test: HTTP config without url raises error."""
        config = McpServerConfig(type="http", command="echo")
        with pytest.raises(ValueError) as exc_info:
            config.validate_for_server("test")
        assert "requires 'url' field" in str(exc_info.value)

    def test_server_config_validation_stdio_missing_command(self):
        """Test: stdio config without command raises error."""
        config = McpServerConfig(type="stdio")
        with pytest.raises(ValueError) as exc_info:
            config.validate_for_server("test")
        assert "requires 'command' field" in str(exc_info.value)

    def test_server_config_validation_unknown_type(self):
        """Test: Unknown type raises error."""
        config = McpServerConfig(type="unknown")
        with pytest.raises(ValueError) as exc_info:
            config.validate_for_server("test")
        assert "must be 'stdio' or 'http'" in str(exc_info.value)

    def test_proxy_config_extra_fields_ignored(self):
        """Test: Extra fields in ProxyConfig are ignored."""
        config = ProxyConfig(
            mcpServers={},
            unknown_field="should_be_ignored",
        )
        assert config.mcpServers == {}


class TestHealthCoverage:
    """Additional health check coverage tests."""

    @pytest.mark.asyncio
    async def test_health_checker_without_callback_returns_healthy(self):
        """Test: Health checker returns False when no callback set."""
        from mcpx.health import HealthChecker

        checker = HealthChecker()

        # Without callback, should return False
        result = await checker.check_server("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_checker_session_exception(self):
        """Test: Health checker handles session exceptions."""
        from mcpx.health import HealthChecker

        class BrokenClient:
            async def ping(self):
                raise ValueError("Session broken")

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        async def callback(name):
            return BrokenClient()

        checker = HealthChecker()
        checker.set_session_callback(callback)

        result = await checker.check_server("test")
        assert result is False

        # Check error was recorded
        health = checker.get_server_health("test")
        assert health is not None
        assert health.status == "unhealthy"
        assert "Session broken" in health.last_error

    @pytest.mark.asyncio
    async def test_health_checker_list_tools_fallback(self):
        """Test: Health checker falls back to list_tools."""
        from mcpx.health import HealthChecker

        class ClientNoPing:
            async def list_tools(self):
                return []  # Success

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        async def callback(name):
            return ClientNoPing()

        checker = HealthChecker()
        checker.set_session_callback(callback)

        result = await checker.check_server("test")
        assert result is True


class TestExecutionResultCoverage:
    """Tests for ExecutionResult coverage."""

    def test_execution_result_to_dict(self):
        """Test: ExecutionResult.to_dict works."""
        from mcpx.executor import ExecutionResult

        result = ExecutionResult(
            server_name="test",
            tool_name="test_tool",
            success=True,
            data={"key": "value"},
        )

        d = result.to_dict()
        assert d["server_name"] == "test"
        assert d["tool_name"] == "test_tool"
        assert d["success"] is True
        assert d["data"] == {"key": "value"}
        assert d["compressed"] is False
        assert d["format"] == "json"

    def test_execution_result_with_compression(self):
        """Test: ExecutionResult with compression fields."""
        from mcpx.executor import ExecutionResult

        result = ExecutionResult(
            server_name="test",
            tool_name="test_tool",
            success=True,
            data=[1, 2, 3],
            compressed=True,
            format="toon",
        )

        d = result.to_dict()
        assert d["compressed"] is True
        assert d["format"] == "toon"
