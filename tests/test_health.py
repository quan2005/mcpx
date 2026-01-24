"""Tests for health check functionality."""

from __future__ import annotations

import asyncio

import pytest

from mcpx.__main__ import McpServerConfig, ProxyConfig
from mcpx.health import HealthChecker, HealthStatus, ServerHealth


class TestServerHealth:
    """Tests for ServerHealth model."""

    def test_server_health_creation(self):
        """Test: ServerHealth can be created."""
        health = ServerHealth(
            server_name="test-server",
            status="healthy",
            consecutive_failures=0,
        )
        assert health.server_name == "test-server"
        assert health.status == "healthy"
        assert health.consecutive_failures == 0

    def test_server_health_with_error(self):
        """Test: ServerHealth with error info."""
        health = ServerHealth(
            server_name="test-server",
            status="unhealthy",
            last_error="Connection timeout",
            consecutive_failures=3,
        )
        assert health.status == "unhealthy"
        assert health.last_error == "Connection timeout"
        assert health.consecutive_failures == 3


class TestHealthStatus:
    """Tests for HealthStatus model."""

    def test_health_status_empty(self):
        """Test: HealthStatus starts empty."""
        status = HealthStatus()
        assert status.total_healthy == 0
        assert status.total_unhealthy == 0
        assert status.total_unknown == 0
        assert len(status.servers) == 0

    def test_health_status_update_healthy(self):
        """Test: Updating server to healthy."""
        status = HealthStatus()
        status.update_server("test-server", is_healthy=True)

        assert status.total_healthy == 1
        assert status.total_unhealthy == 0
        assert status.servers["test-server"].status == "healthy"

    def test_health_status_update_unhealthy(self):
        """Test: Updating server to unhealthy."""
        status = HealthStatus()
        status.update_server("test-server", is_healthy=False, error="Timeout")

        assert status.total_healthy == 0
        assert status.total_unhealthy == 1
        assert status.servers["test-server"].status == "unhealthy"
        assert status.servers["test-server"].last_error == "Timeout"

    def test_health_status_get_unhealthy_servers(self):
        """Test: Get list of unhealthy servers."""
        status = HealthStatus()
        status.update_server("server1", is_healthy=True)
        status.update_server("server2", is_healthy=False)
        status.update_server("server3", is_healthy=False)

        unhealthy = status.get_unhealthy_servers()
        assert set(unhealthy) == {"server2", "server3"}

    def test_health_status_consecutive_failures(self):
        """Test: Consecutive failures are tracked."""
        status = HealthStatus()
        status.update_server("test-server", is_healthy=False)
        status.update_server("test-server", is_healthy=False)
        status.update_server("test-server", is_healthy=False)

        assert status.servers["test-server"].consecutive_failures == 3

    def test_health_status_reset_on_success(self):
        """Test: Consecutive failures reset on success."""
        status = HealthStatus()
        status.update_server("test-server", is_healthy=False)
        status.update_server("test-server", is_healthy=False)
        assert status.servers["test-server"].consecutive_failures == 2

        status.update_server("test-server", is_healthy=True)
        assert status.servers["test-server"].consecutive_failures == 0
        assert status.servers["test-server"].status == "healthy"

    def test_health_status_to_dict(self):
        """Test: HealthStatus can be serialized to dict."""
        status = HealthStatus()
        status.update_server("server1", is_healthy=True)
        status.update_server("server2", is_healthy=False, error="Timeout")

        d = status.to_dict()
        assert d["summary"]["total"] == 2
        assert d["summary"]["healthy"] == 1
        assert d["summary"]["unhealthy"] == 1
        assert "servers" in d
        assert "server1" in d["servers"]
        assert "server2" in d["servers"]


class TestHealthChecker:
    """Tests for HealthChecker."""

    def test_health_checker_creation(self):
        """Test: HealthChecker can be created."""
        checker = HealthChecker(
            check_interval=10,
            check_timeout=3,
            failure_threshold=2,
        )
        assert checker._check_interval == 10
        assert checker._check_timeout == 3
        assert checker._failure_threshold == 2
        assert not checker.is_running

    @pytest.mark.asyncio
    async def test_health_checker_set_callback(self):
        """Test: Session callback can be set."""
        checker = HealthChecker()

        async def mock_callback(name: str):
            return None

        checker.set_session_callback(mock_callback)
        assert checker._get_session_callback is mock_callback

    @pytest.mark.asyncio
    async def test_health_checker_start_stop(self):
        """Test: Health checker can be started and stopped."""
        checker = HealthChecker(check_interval=1)

        async def mock_callback(name: str):
            return None

        checker.set_session_callback(mock_callback)

        await checker.start(["server1", "server2"])
        assert checker.is_running

        await checker.stop()
        assert not checker.is_running

    @pytest.mark.asyncio
    async def test_health_checker_check_server_no_callback(self):
        """Test: Check server fails gracefully without callback."""
        checker = HealthChecker()
        result = await checker.check_server("test-server")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_checker_check_server_success(self):
        """Test: Check server with successful ping."""
        checker = HealthChecker()

        # Mock session with ping
        class MockSession:
            async def ping(self):
                return None

        async def mock_callback(name: str):
            return MockSession()

        checker.set_session_callback(mock_callback)

        result = await checker.check_server("test-server")
        assert result is True
        assert checker.is_server_healthy("test-server")

    @pytest.mark.asyncio
    async def test_health_checker_check_server_timeout(self):
        """Test: Check server handles timeout."""
        checker = HealthChecker(check_timeout=0.1)

        # Mock session that times out
        class MockSession:
            async def ping(self):
                await asyncio.sleep(1)  # Longer than timeout

        async def mock_callback(name: str):
            return MockSession()

        checker.set_session_callback(mock_callback)

        result = await checker.check_server("test-server")
        assert result is False
        assert not checker.is_server_healthy("test-server")

    @pytest.mark.asyncio
    async def test_health_checker_check_server_ping_fallback(self):
        """Test: Check server falls back to list_tools when no ping."""
        checker = HealthChecker()

        # Mock session without ping but with list_tools
        class MockSession:
            async def list_tools(self):
                return []

        async def mock_callback(name: str):
            return MockSession()

        checker.set_session_callback(mock_callback)

        result = await checker.check_server("test-server")
        assert result is True

    @pytest.mark.asyncio
    async def test_health_checker_get_server_health(self):
        """Test: Get health status for specific server."""
        checker = HealthChecker()

        class MockSession:
            async def ping(self):
                return None

        async def mock_callback(name: str):
            return MockSession()

        checker.set_session_callback(mock_callback)

        # Check a server
        await checker.check_server("test-server")

        # Get health status
        health = checker.get_server_health("test-server")
        assert health is not None
        assert health.server_name == "test-server"
        assert health.status == "healthy"

        # Non-existent server
        health = checker.get_server_health("nonexistent")
        assert health is None


class TestHealthIntegration:
    """Integration tests for health check with Registry."""

    @pytest.mark.asyncio
    async def test_registry_health_check_disabled(self):
        """Test: Registry doesn't start health checker when disabled."""
        from mcpx.registry import Registry

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(name="test", command="echo", args=["hello"]),
            ],
            health_check_enabled=False,
        )

        registry = Registry(config)
        await registry.initialize()

        try:
            assert not registry._health_checker.is_running
        finally:
            await registry.close()

    @pytest.mark.asyncio
    async def test_registry_health_check_enabled(self):
        """Test: Registry starts health checker when enabled."""
        from mcpx.registry import Registry

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ],
            health_check_enabled=True,
            health_check_interval=60,  # Long interval for test
        )

        registry = Registry(config)
        await registry.initialize()

        try:
            assert registry._health_checker.is_running
            # Check that health status was initialized
            status = registry.get_health_status()
            assert "filesystem" in status.servers
        finally:
            await registry.close()

    @pytest.mark.asyncio
    async def test_registry_get_server_health(self):
        """Test: Registry can get server health."""
        from mcpx.registry import Registry

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ],
            health_check_enabled=False,  # Disable for simpler test
        )

        registry = Registry(config)
        await registry.initialize()

        try:
            # Need to trigger a health check first since auto-check is disabled
            await registry.check_server_health("filesystem")
            health = registry.get_server_health("filesystem")
            assert health is not None
            assert health["server_name"] == "filesystem"
        finally:
            await registry.close()

    @pytest.mark.asyncio
    async def test_registry_manual_health_check(self):
        """Test: Registry can trigger manual health check."""
        from mcpx.registry import Registry

        config = ProxyConfig(
            mcp_servers=[
                McpServerConfig(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                ),
            ],
            health_check_enabled=False,
        )

        registry = Registry(config)
        await registry.initialize()

        try:
            # Trigger manual health check
            is_healthy = await registry.check_server_health("filesystem")
            assert is_healthy is True
        finally:
            await registry.close()
