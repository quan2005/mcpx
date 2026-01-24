"""Tests for MCPX."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from mcpx.__main__ import McpServerConfig, ProxyConfig, create_server, load_config


def test_load_config_from_file():
    """Test loading configuration from a file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "mcp_servers": [
                    {"name": "test", "command": "echo", "args": ["hello"]},
                    {"name": "test2", "command": "cat", "args": []},
                ]
            },
            f,
        )
        config_path = Path(f.name)

    try:
        config = load_config(config_path)
        assert len(config.mcp_servers) == 2
        assert config.mcp_servers[0].name == "test"
        assert config.mcp_servers[0].command == "echo"
        assert config.mcp_servers[0].args == ["hello"]
    finally:
        config_path.unlink()


def test_load_config_file_not_found():
    """Test loading from non-existent file."""
    with pytest.raises(SystemExit):
        load_config(Path("/nonexistent/config.json"))


def test_load_config_invalid_json():
    """Test loading with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{invalid json}")
        config_path = Path(f.name)

    try:
        with pytest.raises(SystemExit):
            load_config(config_path)
    finally:
        config_path.unlink()


def test_load_config_invalid_structure():
    """Test loading with invalid structure (mcp_servers not a list)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"mcp_servers": "not-a-list"}, f)
        config_path = Path(f.name)

    try:
        with pytest.raises(SystemExit):
            load_config(config_path)
    finally:
        config_path.unlink()


def test_proxy_config_validation():
    """Test ProxyConfig validation."""
    data = {
        "mcp_servers": [
            {"name": "test", "command": "echo", "args": ["hello"]},
        ]
    }
    config = ProxyConfig(**data)
    assert len(config.mcp_servers) == 1
    assert config.mcp_servers[0].name == "test"


def test_proxy_config_empty_servers():
    """Test ProxyConfig with no servers."""
    config = ProxyConfig()
    assert config.mcp_servers == []


def test_mcp_server_config_validation():
    """Test McpServerConfig validation."""
    # Valid config
    config = McpServerConfig(name="test", command="echo", args=["hello"])
    assert config.name == "test"
    assert config.args == ["hello"]

    # Missing required field
    with pytest.raises(ValidationError):
        McpServerConfig(name="test")


def test_mcp_server_config_with_env():
    """Test McpServerConfig with environment variables."""
    config = McpServerConfig(
        name="test",
        command="node",
        args=["server.js"],
        env={"API_KEY": "secret", "DEBUG": "true"},
    )
    assert config.name == "test"
    assert config.env == {"API_KEY": "secret", "DEBUG": "true"}


def test_create_server():
    """Test creating FastMCP server."""
    config = ProxyConfig(
        mcp_servers=[
            McpServerConfig(name="test", command="echo", args=["hello"]),
        ]
    )
    mcp = create_server(config)

    assert mcp is not None
    assert hasattr(mcp, "_config")
    assert hasattr(mcp, "_registry")
    assert hasattr(mcp, "_executor")


def test_create_server_multiple_servers():
    """Test creating server with multiple MCP servers."""
    config = ProxyConfig(
        mcp_servers=[
            McpServerConfig(name="s1", command="cmd1", args=[]),
            McpServerConfig(name="s2", command="cmd2", args=[]),
            McpServerConfig(name="s3", command="cmd3", args=[]),
        ]
    )
    mcp = create_server(config)

    assert mcp is not None
    assert len(mcp._config.mcp_servers) == 3
