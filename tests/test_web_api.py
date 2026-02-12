"""Tests for REST API endpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient

from mcpx.config_manager import ConfigManager
from mcpx.server import ResourceInfo, ServerInfo, ServerManager, ToolInfo
from mcpx.web import DashboardApp


@pytest.fixture
def config_path():
    """Create a temporary config file."""
    config_data = {
        "mcpServers": {
            "test-server": {
                "type": "stdio",
                "command": "echo",
                "args": ["hello"],
                "enabled": True,
            },
            "disabled-server": {
                "type": "stdio",
                "command": "echo",
                "args": ["disabled"],
                "enabled": False,
            },
        },
        "disabled_tools": ["test-server.disabled_tool"],
        "health_check_enabled": True,
        "health_check_interval": 30,
        "health_check_timeout": 5,
        "health_check_failure_threshold": 2,
        "toon_compression_enabled": True,
        "toon_compression_min_size": 3,
        "schema_compression_enabled": True,
        "include_structured_content": False,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        path = Path(f.name)

    yield path
    path.unlink()


@pytest.fixture
def config_manager(config_path):
    """Create a ConfigManager instance."""
    manager = ConfigManager(config_path)
    # Load synchronously for test
    import asyncio

    asyncio.get_event_loop().run_until_complete(manager.load())
    return manager


@pytest.fixture
def mock_server_manager():
    """Create a mock ServerManager."""
    manager = MagicMock(spec=ServerManager)
    manager._initialized = True

    # Mock server info
    server_info = ServerInfo(
        name="test-server",
        server_name="TestServer",
        version="1.0.0",
        instructions="Test instructions",
    )
    manager.get_server_info.return_value = server_info

    # Mock health status
    manager.get_server_health.return_value = {
        "status": "healthy",
        "last_check": "2026-02-12T10:00:00Z",
        "last_success": "2026-02-12T10:00:00Z",
        "consecutive_failures": 0,
        "last_error": None,
    }

    # Mock server list
    manager.list_servers.return_value = ["test-server"]

    # Mock tools
    tool1 = ToolInfo(
        server_name="test-server",
        name="test_tool",
        description="A test tool",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
    )
    tool2 = ToolInfo(
        server_name="test-server",
        name="disabled_tool",
        description="A disabled tool",
        input_schema={"type": "object"},
    )
    manager.list_all_tools.return_value = [tool1, tool2]
    manager.list_tools.return_value = [tool1, tool2]
    manager.get_tool.return_value = tool1

    # Mock resources
    resource1 = ResourceInfo(
        server_name="test-server",
        uri="file:///test.txt",
        name="test.txt",
        description="Test file",
        mime_type="text/plain",
        size=100,
    )
    manager.list_all_resources.return_value = [resource1]
    manager.list_resources.return_value = [resource1]

    # Mock connect/disconnect
    manager.connect_server = AsyncMock(return_value=True)
    manager.disconnect_server = AsyncMock()
    manager.reload = AsyncMock()

    # Mock call
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.raw_data = {"result": "ok"}
    mock_result.compressed = False
    manager.call = AsyncMock(return_value=mock_result)

    # Mock read
    mock_content = MagicMock()
    mock_content.uri = "file:///test.txt"
    mock_content.text = "Test content"
    manager.read = AsyncMock(return_value=[mock_content])

    # Mock check_server_health
    manager.check_server_health = AsyncMock(return_value=True)

    # Mock get_health_status
    mock_health_status = MagicMock()
    mock_health_status.to_dict.return_value = {
        "summary": {"total": 2, "healthy": 1, "unhealthy": 0, "unknown": 1},
        "servers": {
            "test-server": {
                "status": "healthy",
                "last_check": "2026-02-12T10:00:00Z",
                "consecutive_failures": 0,
            }
        },
    }
    manager.get_health_status.return_value = mock_health_status

    return manager


@pytest.fixture
def client(config_manager, mock_server_manager):
    """Create a test client."""
    app = DashboardApp(manager=mock_server_manager, config_manager=config_manager)
    return TestClient(app.api)


class TestServerEndpoints:
    """Tests for server-related endpoints."""

    def test_list_servers(self, client):
        """Test GET /servers."""
        response = client.get("/servers")
        assert response.status_code == 200
        data = response.json()
        assert "servers" in data
        assert len(data["servers"]) == 2

        # Check first server
        server = next(s for s in data["servers"] if s["name"] == "test-server")
        assert server["enabled"] is True
        assert server["type"] == "stdio"
        assert server["connected"] is True
        assert server["server_name"] == "TestServer"

    def test_get_server(self, client):
        """Test GET /servers/{name}."""
        response = client.get("/servers/test-server")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-server"
        assert data["enabled"] is True
        assert "config" in data
        assert data["config"]["command"] == "echo"

    def test_get_server_not_found(self, client):
        """Test GET /servers/{name} with non-existent server."""
        response = client.get("/servers/nonexistent")
        assert response.status_code == 404
        assert "error" in response.json()

    def test_toggle_server_enable(self, client, mock_server_manager, config_manager):
        """Test POST /servers/{name}/toggle to enable server."""
        response = client.post("/servers/disabled-server/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "disabled-server"
        assert data["enabled"] is True
        mock_server_manager.connect_server.assert_called_once()

    def test_toggle_server_disable(self, client, mock_server_manager, config_manager):
        """Test POST /servers/{name}/toggle to disable server."""
        response = client.post("/servers/test-server/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-server"
        assert data["enabled"] is False
        mock_server_manager.disconnect_server.assert_called_once()

    def test_toggle_server_not_found(self, client):
        """Test POST /servers/{name}/toggle with non-existent server."""
        response = client.post("/servers/nonexistent/toggle")
        assert response.status_code == 404


class TestToolEndpoints:
    """Tests for tool-related endpoints."""

    def test_list_tools(self, client):
        """Test GET /tools."""
        response = client.get("/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) == 2

        # Check enabled tool
        tool = next(t for t in data["tools"] if t["name"] == "test_tool")
        assert tool["enabled"] is True
        assert tool["server"] == "test-server"

        # Check disabled tool
        disabled_tool = next(t for t in data["tools"] if t["name"] == "disabled_tool")
        assert disabled_tool["enabled"] is False

    def test_list_tools_with_filter(self, client, mock_server_manager):
        """Test GET /tools?server=test-server."""
        response = client.get("/tools?server=test-server")
        assert response.status_code == 200
        data = response.json()
        assert all(t["server"] == "test-server" for t in data["tools"])

    def test_get_tool(self, client):
        """Test GET /tools/{server}/{tool}."""
        response = client.get("/tools/test-server/test_tool")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_tool"
        assert data["server"] == "test-server"
        assert "input_schema" in data
        assert data["enabled"] is True

    def test_get_tool_not_found(self, client, mock_server_manager):
        """Test GET /tools/{server}/{tool} with non-existent tool."""
        mock_server_manager.get_tool.return_value = None
        response = client.get("/tools/test-server/nonexistent")
        assert response.status_code == 404

    def test_toggle_tool_enable(self, client, config_manager):
        """Test POST /tools/{server}/{tool}/toggle to enable tool."""
        response = client.post("/tools/test-server/disabled_tool/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "disabled_tool"
        assert data["enabled"] is True

    def test_toggle_tool_disable(self, client, config_manager):
        """Test POST /tools/{server}/{tool}/toggle to disable tool."""
        response = client.post("/tools/test-server/test_tool/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_tool"
        assert data["enabled"] is False

    def test_invoke_tool(self, client, mock_server_manager):
        """Test POST /invoke."""
        response = client.post(
            "/invoke",
            json={"method": "test-server.test_tool", "arguments": {"path": "/tmp"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == {"result": "ok"}
        mock_server_manager.call.assert_called_once_with(
            "test-server", "test_tool", {"path": "/tmp"}
        )

    def test_invoke_tool_missing_method(self, client):
        """Test POST /invoke without method."""
        response = client.post("/invoke", json={"arguments": {}})
        assert response.status_code == 400
        assert "error" in response.json()

    def test_invoke_tool_invalid_method_format(self, client):
        """Test POST /invoke with invalid method format."""
        response = client.post("/invoke", json={"method": "invalidmethod"})
        assert response.status_code == 400
        assert "error" in response.json()

    def test_invoke_tool_disabled(self, client):
        """Test POST /invoke with disabled tool."""
        response = client.post(
            "/invoke",
            json={"method": "test-server.disabled_tool", "arguments": {}},
        )
        assert response.status_code == 403
        assert "disabled" in response.json()["error"].lower()

    def test_invoke_tool_invalid_json(self, client):
        """Test POST /invoke with invalid JSON."""
        response = client.post(
            "/invoke",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400


class TestResourceEndpoints:
    """Tests for resource-related endpoints."""

    def test_list_resources(self, client):
        """Test GET /resources."""
        response = client.get("/resources")
        assert response.status_code == 200
        data = response.json()
        assert "resources" in data
        assert len(data["resources"]) == 1
        resource = data["resources"][0]
        assert resource["server"] == "test-server"
        assert resource["uri"] == "file:///test.txt"
        assert resource["name"] == "test.txt"

    def test_list_resources_with_filter(self, client, mock_server_manager):
        """Test GET /resources?server=test-server."""
        response = client.get("/resources?server=test-server")
        assert response.status_code == 200
        data = response.json()
        assert all(r["server"] == "test-server" for r in data["resources"])

    def test_read_resource(self, client, mock_server_manager):
        """Test POST /read."""
        response = client.post(
            "/read",
            json={"server": "test-server", "uri": "file:///test.txt"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["contents"]) == 1
        assert data["contents"][0]["type"] == "text"
        assert data["contents"][0]["text"] == "Test content"

    def test_read_resource_missing_fields(self, client):
        """Test POST /read without required fields."""
        response = client.post("/read", json={"server": "test-server"})
        assert response.status_code == 400
        assert "error" in response.json()


class TestHealthEndpoints:
    """Tests for health-related endpoints."""

    def test_get_health(self, client):
        """Test GET /health."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "servers" in data

    def test_get_server_health(self, client):
        """Test GET /health/{server}."""
        response = client.get("/health/test-server")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_get_server_health_not_found(self, client, mock_server_manager):
        """Test GET /health/{server} with non-existent server."""
        mock_server_manager.get_server_health.return_value = None
        response = client.get("/health/nonexistent")
        assert response.status_code == 404

    def test_check_server_health(self, client, mock_server_manager):
        """Test POST /health/{server}/check."""
        response = client.post("/health/test-server/check")
        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        mock_server_manager.check_server_health.assert_called_once()

    def test_check_server_health_not_found(self, client):
        """Test POST /health/{server}/check with non-existent server."""
        response = client.post("/health/nonexistent/check")
        assert response.status_code == 404


class TestConfigEndpoints:
    """Tests for config-related endpoints."""

    def test_get_config(self, client):
        """Test GET /config."""
        response = client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "mcpServers" in data
        assert "disabled_tools" in data
        assert data["health_check_enabled"] is True

    def test_update_config(self, client, mock_server_manager, config_manager):
        """Test PUT /config."""
        response = client.put(
            "/config",
            json={"health_check_interval": 60},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_server_manager.reload.assert_called_once()

    def test_update_config_invalid_json(self, client):
        """Test PUT /config with invalid JSON."""
        response = client.put(
            "/config",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_update_config_with_servers(self, client, mock_server_manager):
        """Test PUT /config with server updates."""
        response = client.put(
            "/config",
            json={
                "mcpServers": {
                    "test-server": {
                        "type": "stdio",
                        "command": "newcommand",
                        "args": [],
                        "enabled": True,
                    }
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
