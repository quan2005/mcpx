"""MCP Registry - Manages connections and caches tool schemas."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from pydantic import BaseModel

from mcpx.config import McpServerConfig, ProxyConfig
from mcpx.health import HealthChecker, HealthStatus

# Type alias for MCP Client
McpClient = Any  # FastMCP Client doesn't have type stubs yet

logger = logging.getLogger(__name__)

__all__ = ["ToolInfo", "ServerInfo", "ResourceInfo", "Registry"]


def _is_text_mime_type(mime_type: str | None) -> bool:
    """Check if a MIME type represents text content.

    Args:
        mime_type: MIME type string (e.g., "text/plain", "application/json")

    Returns:
        True if the MIME type represents text content, False otherwise
    """
    if mime_type is None:
        return False

    mime_type_lower = mime_type.lower()

    # Common text MIME types
    text_prefixes = (
        "text/",
        "application/json",
        "application/xml",
        "application/javascript",
        "application/x-javascript",
        "application/x-yaml",
        "application/yaml",
        "application/x-sh",
        "application/x-python",
        "application/x-toml",
        "application/json+",
        "application/xml+",
    )

    return any(mime_type_lower.startswith(prefix) for prefix in text_prefixes)


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


class ResourceInfo(BaseModel):
    """Cached resource information."""

    server_name: str
    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None
    size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "server_name": self.server_name,
            "uri": str(self.uri),
            "name": self.name,
            "description": self.description,
            "mime_type": self.mime_type,
            "size": self.size,
        }


class Registry:
    """Registry for MCP servers and their tools.

    On startup:
    - Connects to all configured MCP servers
    - Maintains long-lived connections
    - Fetches and caches tool lists and schemas
    - Starts health checking if enabled
    """

    def __init__(self, config: ProxyConfig) -> None:
        """Initialize registry with configuration.

        Args:
            config: Proxy configuration with MCP server list
        """
        self._config = config
        self._sessions: dict[str, McpClient] = {}  # TODO: Remove after refactor
        self._client_factories: dict[str, Callable[[], McpClient]] = {}  # New: session isolation
        self._tools: dict[str, ToolInfo] = {}
        self._resources: dict[str, ResourceInfo] = {}
        self._server_infos: dict[str, ServerInfo] = {}
        self._initialized = False

        # Initialize health checker
        self._health_checker = HealthChecker(
            check_interval=config.health_check_interval,
            check_timeout=config.health_check_timeout,
            failure_threshold=config.health_check_failure_threshold,
        )
        # Set callback for health checker to get sessions
        self._health_checker.set_session_callback(self._get_session_for_health_check)

    async def ensure_initialized(self) -> None:
        """Ensure registry is initialized (lazy initialization)."""
        if not self._initialized:
            await self.initialize()

    async def initialize(self) -> None:
        """Initialize connections to all MCP servers.

        Connects to each server and caches tool schemas.
        Failed connections don't prevent other servers from loading.
        Starts health checking if enabled.
        """
        if self._initialized:
            return

        for server_config in self._config.mcp_servers:
            try:
                await self._connect_server(server_config)
            except Exception as e:
                logger.error(f"Failed to connect to server '{server_config.name}': {e}")

        self._initialized = True

        # Start health checker if enabled and we have connected servers
        if self._config.health_check_enabled and self._sessions:
            server_names = list(self._sessions.keys())
            await self._health_checker.start(server_names)
            logger.info(f"Health checker started for {len(server_names)} server(s)")

    async def _connect_server(self, server_config: McpServerConfig) -> None:
        """Connect to a single MCP server and cache its tools.

        Args:
            server_config: Server configuration
        """
        logger.info(f"Connecting to MCP server: {server_config.name}")

        # Create transport based on type
        if server_config.type == "http":
            transport: StdioTransport | StreamableHttpTransport = StreamableHttpTransport(
                url=server_config.url,  # type: ignore[arg-type]
                headers=server_config.headers or {},
            )
        else:
            # Default to stdio
            transport = StdioTransport(
                command=server_config.command,  # type: ignore[arg-type]
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

            # Cache resource information
            try:
                resources = await client.list_resources()
                logger.info(f"Server '{server_config.name}' has {len(resources)} resource(s)")
                for resource in resources:
                    resource_key = f"{server_config.name}:{resource.uri}"

                    # Generate description for text resources without description
                    description = resource.description
                    if not description and _is_text_mime_type(resource.mimeType):
                        try:
                            contents = await client.read_resource(str(resource.uri))
                            if contents and len(contents) > 0:
                                first_content = contents[0]
                                if hasattr(first_content, "text"):
                                    text_content = first_content.text
                                    # Use first 100 characters as description
                                    description = text_content[:100]
                                    if len(text_content) > 100:
                                        description += "..."
                        except Exception as e:
                            logger.debug(f"Failed to read resource '{resource.uri}' for description: {e}")

                    self._resources[resource_key] = ResourceInfo(
                        server_name=server_config.name,
                        uri=str(resource.uri),
                        name=resource.name,
                        description=description,
                        mime_type=resource.mimeType,
                        size=resource.size,
                    )
            except Exception as e:
                logger.warning(f"Failed to list resources from '{server_config.name}': {e}")

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

    def list_resources(self, server_name: str) -> list[ResourceInfo]:
        """List all cached resources for a specific server.

        Args:
            server_name: Name of the server to list resources for

        Returns:
            List of resource information for the specified server
        """
        return [
            resource for resource in self._resources.values()
            if resource.server_name == server_name
        ]

    def list_all_resources(self) -> list[ResourceInfo]:
        """List all cached resources from all servers.

        Returns:
            List of all cached resource information
        """
        return list(self._resources.values())

    def get_resource(self, server_name: str, uri: str) -> ResourceInfo | None:
        """Get cached resource information by server name and URI.

        Args:
            server_name: Name of the server
            uri: Resource URI

        Returns:
            ResourceInfo if found, None otherwise
        """
        resource_key = f"{server_name}:{uri}"
        return self._resources.get(resource_key)

    async def read_resource(
        self, server_name: str, uri: str
    ) -> Any | None:
        """Read resource content from MCP server.

        Args:
            server_name: Name of the server
            uri: Resource URI to read

        Returns:
            List of content items (TextResourceContents or BlobResourceContents),
            or None if server not found/read fails
        """
        client = self._sessions.get(server_name)
        if client is None:
            return None

        try:
            contents = await client.read_resource(uri)
            return contents
        except Exception as e:
            logger.error(f"Error reading resource '{uri}' from '{server_name}': {e}")
            return None

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

    async def reconnect_server(self, server_name: str) -> bool:
        """Reconnect to a specific server.

        Args:
            server_name: Name of the server to reconnect

        Returns:
            True if reconnection succeeded, False otherwise
        """
        # Find the server config
        server_config = None
        for cfg in self._config.mcp_servers:
            if cfg.name == server_name:
                server_config = cfg
                break

        if server_config is None:
            logger.error(f"Cannot reconnect: server '{server_name}' not in config")
            return False

        # Close existing session if any
        old_client = self._sessions.pop(server_name, None)
        if old_client is not None:
            try:
                await old_client.__aexit__(None, None, None)
            except Exception:
                pass

        # Remove old tools for this server
        keys_to_remove = [k for k in self._tools if k.startswith(f"{server_name}:")]
        for key in keys_to_remove:
            del self._tools[key]

        # Remove old resources for this server
        resource_keys_to_remove = [k for k in self._resources if k.startswith(f"{server_name}:")]
        for key in resource_keys_to_remove:
            del self._resources[key]

        # Reconnect
        try:
            await self._connect_server(server_config)
            logger.info(f"Reconnected to server '{server_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to reconnect to server '{server_name}': {e}")
            return False

    async def close(self) -> None:
        """Close all sessions and stop health checker."""
        import asyncio

        # Stop health checker
        await self._health_checker.stop()

        # Close all sessions
        for server_name, client in self._sessions.items():
            try:
                await client.__aexit__(None, None, None)
                logger.info(f"Closed connection to '{server_name}'")
            except asyncio.CancelledError:
                # Expected when closing in a separate asyncio.run() context
                logger.debug(f"Connection to '{server_name}' cancelled during close")
            except Exception as e:
                logger.error(f"Error closing connection to '{server_name}': {e}")

        self._sessions.clear()
        self._tools.clear()
        self._resources.clear()
        self._initialized = False

    async def _get_session_for_health_check(self, server_name: str) -> McpClient | None:
        """Get session for health checking.

        Args:
            server_name: Name of the server

        Returns:
            Session if available, None otherwise
        """
        return self._sessions.get(server_name)

    def get_health_status(self) -> HealthStatus:
        """Get current health status of all servers.

        Returns:
            HealthStatus with current health information
        """
        return self._health_checker.status

    def get_server_health(self, server_name: str) -> dict[str, Any] | None:
        """Get health status for a specific server.

        Args:
            server_name: Name of the server

        Returns:
            Server health dict or None if not found
        """
        health = self._health_checker.get_server_health(server_name)
        if health:
            return {
                "server_name": health.server_name,
                "status": health.status,
                "last_check": health.last_check.isoformat() if health.last_check else None,
                "last_success": health.last_success.isoformat() if health.last_success else None,
                "consecutive_failures": health.consecutive_failures,
                "last_error": health.last_error,
            }
        return None

    def is_server_healthy(self, server_name: str) -> bool:
        """Check if a specific server is healthy.

        Args:
            server_name: Name of the server

        Returns:
            True if server is healthy, False otherwise
        """
        return self._health_checker.is_server_healthy(server_name)

    async def check_server_health(self, server_name: str) -> bool:
        """Manually trigger health check for a server.

        Args:
            server_name: Name of the server

        Returns:
            True if server is healthy, False otherwise
        """
        return await self._health_checker.check_server(server_name)
