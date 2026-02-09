"""Tests for MCPX."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from mcpx.__main__ import McpServerConfig, ProxyConfig, create_server, load_config


def _parse_response(content: str) -> Any:
    """Parse response, trying JSON first then TOON as fallback."""
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


def test_load_config_from_file():
    """Test loading configuration from a file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "mcpServers": {
                    "test": {"type": "stdio", "command": "echo", "args": ["hello"]},
                    "test2": {"type": "stdio", "command": "cat", "args": []},
                }
            },
            f,
        )
        config_path = Path(f.name)

    try:
        config = load_config(config_path)
        assert len(config.mcpServers) == 2
        assert "test" in config.mcpServers
        assert config.mcpServers["test"].command == "echo"
        assert config.mcpServers["test"].args == ["hello"]
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
    """Test loading with invalid structure (mcpServers not a dict)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"mcpServers": "not-a-dict"}, f)
        config_path = Path(f.name)

    try:
        with pytest.raises(SystemExit):
            load_config(config_path)
    finally:
        config_path.unlink()


def test_proxy_config_validation():
    """Test ProxyConfig validation."""
    data = {
        "mcpServers": {
            "test": {"type": "stdio", "command": "echo", "args": ["hello"]},
        }
    }
    config = ProxyConfig(**data)
    assert len(config.mcpServers) == 1
    assert "test" in config.mcpServers


def test_proxy_config_empty_servers():
    """Test ProxyConfig with no servers."""
    config = ProxyConfig()
    assert config.mcpServers == {}


def test_mcp_server_config_validation():
    """Test McpServerConfig validation."""
    # Valid config (name is no longer a field, it's the key in mcpServers)
    config = McpServerConfig(type="stdio", command="echo", args=["hello"])
    assert config.type == "stdio"
    assert config.args == ["hello"]

    # Missing required field for stdio type
    config = McpServerConfig(type="stdio")
    with pytest.raises(ValueError, match="stdio type requires 'command' field"):
        config.validate_for_server("test")


def test_mcp_server_config_with_env():
    """Test McpServerConfig with environment variables."""
    config = McpServerConfig(
        type="stdio",
        command="node",
        args=["server.js"],
        env={"API_KEY": "secret", "DEBUG": "true"},
    )
    assert config.type == "stdio"
    assert config.env == {"API_KEY": "secret", "DEBUG": "true"}


def test_create_server():
    """Test creating FastMCP server."""
    config = ProxyConfig(
        mcpServers={
            "test": McpServerConfig(type="stdio", command="echo", args=["hello"]),
        }
    )
    mcp = create_server(config)

    assert mcp is not None
    assert hasattr(mcp, "_config")
    assert hasattr(mcp, "_registry")
    assert hasattr(mcp, "_executor")


def test_create_server_multiple_servers():
    """Test creating server with multiple MCP servers."""
    config = ProxyConfig(
        mcpServers={
            "s1": McpServerConfig(type="stdio", command="cmd1", args=[]),
            "s2": McpServerConfig(type="stdio", command="cmd2", args=[]),
            "s3": McpServerConfig(type="stdio", command="cmd3", args=[]),
        }
    )
    mcp = create_server(config)

    assert mcp is not None
    assert len(mcp._config.mcpServers) == 3


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


async def test_call_validation_returns_tool_schema():
    """Test: call returns tool schema on argument validation error."""
    from mcpx.server import ServerManager, ToolInfo

    config = ProxyConfig()
    manager = ServerManager(config)
    manager._initialized = True

    # Add a dummy pool
    class DummyPool:
        pass

    manager._pools["dummy"] = DummyPool()

    tool_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "mode": {"type": "string", "enum": ["fast", "safe"]},
        },
        "required": ["path"],
    }
    manager._tools["dummy:read_file"] = ToolInfo(
        server_name="dummy",
        name="read_file",
        description="Read file content",
        input_schema=tool_schema,
    )

    mcp_server = create_server(config, manager=manager)

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "invoke",
            arguments={
                "method": "dummy.read_file",
                "arguments": {"mode": "fast"},
            },
        )

    content = _extract_text_content(result)
    call_result = _parse_response(content)

    # New simplified format: no "success" key
    assert "error" in call_result
    assert "Argument validation failed" in call_result["error"]
    # tool_schema is now compressed to TypeScript format (default enabled)
    assert "tool_schema" in call_result
    # TypeScript format: {path: string; mode?: "fast" | "safe"}
    assert "path: string" in call_result["tool_schema"]
    assert "mode?" in call_result["tool_schema"]  # optional field
