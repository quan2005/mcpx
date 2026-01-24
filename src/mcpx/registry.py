"""MCP Registry - Manages connections and caches tool schemas."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic import BaseModel

from mcpx.__main__ import McpServerConfig, ProxyConfig

# Type alias for MCP Client
McpClient = Any  # FastMCP Client doesn't have type stubs yet

logger = logging.getLogger(__name__)

__all__ = ["ToolInfo", "ServerInfo", "Registry"]


class ServerInfo(BaseModel):
    """Cached MCP server information."""

    name: str  # Config name (user-defined)
    server_name: str  # Actual server name from MCP
    version: str
    instructions: str | None = None  # Server usage instructions


class ToolInfo(BaseModel):
    """Cached tool information."""

    server_name: str
    name: str
    description: str
    input_schema: dict[str, Any]

    def get_full_description(self) -> str:
        """Get full description including schema."""
        return f"""Tool: {self.name} (from {self.server_name})

Description:
{self.description}

Input Schema:
{self.input_schema}
"""


class Registry:
    """Registry for MCP servers and their tools.

    On startup:
    - Connects to all configured MCP servers
    - Maintains long-lived connections
    - Fetches and caches tool lists and schemas
    """

    def __init__(self, config: ProxyConfig) -> None:
        """Initialize registry with configuration.

        Args:
            config: Proxy configuration with MCP server list
        """
        self._config = config
        self._sessions: dict[str, McpClient] = {}
        self._tools: dict[str, ToolInfo] = {}
        self._server_infos: dict[str, ServerInfo] = {}
        self._initialized = False

    async def ensure_initialized(self) -> None:
        """Ensure registry is initialized (lazy initialization)."""
        if not self._initialized:
            await self.initialize()

    async def initialize(self) -> None:
        """Initialize connections to all MCP servers.

        Connects to each server and caches tool schemas.
        Failed connections don't prevent other servers from loading.
        """
        if self._initialized:
            return

        for server_config in self._config.mcp_servers:
            try:
                await self._connect_server(server_config)
            except Exception as e:
                logger.error(f"Failed to connect to server '{server_config.name}': {e}")

        self._initialized = True

    async def _connect_server(self, server_config: McpServerConfig) -> None:
        """Connect to a single MCP server and cache its tools.

        Args:
            server_config: Server configuration
        """
        logger.info(f"Connecting to MCP server: {server_config.name}")

        # Create stdio transport
        transport = StdioTransport(
            command=server_config.command,
            args=server_config.args,
            env=server_config.env or {},
        )

        # Create client with transport
        client: McpClient = Client(transport)

        try:
            # Connect and fetch tools
            await client.__aenter__()

            # Cache server information
            init_result = client.initialize_result
            if init_result and init_result.serverInfo:
                self._server_infos[server_config.name] = ServerInfo(
                    name=server_config.name,
                    server_name=init_result.serverInfo.name or server_config.name,
                    version=init_result.serverInfo.version or "unknown",
                    instructions=init_result.instructions,
                )
            else:
                self._server_infos[server_config.name] = ServerInfo(
                    name=server_config.name,
                    server_name=server_config.name,
                    version="unknown",
                    instructions=None,
                )

            tools = await client.list_tools()
            logger.info(f"Server '{server_config.name}' has {len(tools)} tool(s)")

            # Cache tool information
            for tool in tools:
                tool_key = f"{server_config.name}:{tool.name}"
                self._tools[tool_key] = ToolInfo(
                    server_name=server_config.name,
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema or {},
                )

            # Store session for later use
            self._sessions[server_config.name] = client

        except Exception as e:
            logger.error(f"Error connecting to '{server_config.name}': {e}")
            try:
                await client.__aexit__(None, None, None)
            except Exception:
                pass
            raise

    def get_tool_list_text(self) -> str:
        """Generate plain text list of available tools grouped by server.

        This is used for the inspect tool description.

        Returns:
            Plain text listing all available tools grouped by server
        """
        if not self._tools:
            return "No tools available."

        lines = ["Available tools (use inspect with server_name to get details):"]
        for server_name in sorted(self._sessions.keys()):
            lines.append(f"  Server: {server_name}")
            for tool in self.list_tools(server_name):
                desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
                lines.append(f"    - {tool.name}: {desc}")
        return "\n".join(lines)

    def get_tool(self, server_name: str, tool_name: str) -> ToolInfo | None:
        """Get cached tool information by server name and tool name.

        Args:
            server_name: Name of the server
            tool_name: Name of the tool

        Returns:
            ToolInfo if found, None otherwise
        """
        tool_key = f"{server_name}:{tool_name}"
        return self._tools.get(tool_key)

    def list_tools(self, server_name: str) -> list[ToolInfo]:
        """List all cached tools for a specific server.

        Args:
            server_name: Name of the server to list tools for

        Returns:
            List of tool information for the specified server
        """
        return [
            tool for tool in self._tools.values()
            if tool.server_name == server_name
        ]

    def list_all_tools(self) -> list[ToolInfo]:
        """List all cached tools from all servers.

        Returns:
            List of all cached tool information
        """
        return list(self._tools.values())

    def list_servers(self) -> list[str]:
        """List all connected server names.

        Returns:
            List of server names
        """
        return list(self._sessions.keys())

    def get_server_info(self, server_name: str) -> ServerInfo | None:
        """Get cached server information.

        Args:
            server_name: Name of the server

        Returns:
            ServerInfo if found, None otherwise
        """
        return self._server_infos.get(server_name)

    def get_session(self, server_name: str) -> McpClient | None:
        """Get active session for a server.

        Args:
            server_name: Name of the server

        Returns:
            Client session if exists, None otherwise
        """
        return self._sessions.get(server_name)

    @property
    def sessions(self) -> dict[str, McpClient]:
        """Get all active sessions."""
        return self._sessions.copy()

    @property
    def tools(self) -> dict[str, ToolInfo]:
        """Get all cached tools."""
        return self._tools.copy()

    async def close(self) -> None:
        """Close all sessions."""
        for server_name, client in self._sessions.items():
            try:
                await client.__aexit__(None, None, None)
                logger.info(f"Closed connection to '{server_name}'")
            except Exception as e:
                logger.error(f"Error closing connection to '{server_name}': {e}")

        self._sessions.clear()
        self._tools.clear()
