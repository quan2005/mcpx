"""MCPX - MCP proxy server."""

from __future__ import annotations

from mcpx.config import McpServerConfig, ProxyConfig
from mcpx.content import ContentType, detect_content_type, is_multimodal_content
from mcpx.errors import (
    ExecutionError,
    MCPXError,
    ResourceNotFoundError,
    ServerNotFoundError,
    ToolNotFoundError,
    ValidationError,
)
from mcpx.server import ResourceInfo, ServerInfo, ServerManager, ToolInfo

__all__ = [
    # Config
    "McpServerConfig",
    "ProxyConfig",
    # Content
    "ContentType",
    "is_multimodal_content",
    "detect_content_type",
    # Errors
    "MCPXError",
    "ServerNotFoundError",
    "ToolNotFoundError",
    "ValidationError",
    "ResourceNotFoundError",
    "ExecutionError",
    # Server
    "ServerManager",
    "ServerInfo",
    "ToolInfo",
    "ResourceInfo",
]
