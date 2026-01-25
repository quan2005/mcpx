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

    Uses session isolation pattern:
    - Creates client_factory for each server on startup
    - Fetches and caches tool/resource schemas
    - Each request uses a fresh session via client_factory
    - Sessions are automatically closed after use
    - Starts health checking if enabled
    """

    def __init__(self, config: ProxyConfig) -> None:
        """Initialize registry with configuration.

        Args:
            config: Proxy configuration with MCP server list
        """
        self._config = config
        self._client_factories: dict[str, Callable[[], McpClient]] = {}
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
        # Set callback for health checker to get client factory
        self._health_checker.set_session_callback(self._get_client_for_health_check)

    def _create_client_factory(
        self, server_config: McpServerConfig
    ) -> Callable[[], McpClient]:
        """Create a client factory for a server.

        The factory returns a new client instance on each call.
        This enables session isolation - each request gets a fresh connection.

        Args:
            server_config: Server configuration

        Returns:
            A callable that returns a new Client instance
        """
        from fastmcp.client.transports import StdioTransport, StreamableHttpTransport

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

        # Create base client (disconnected)
        base_client: McpClient = Client(transport, auto_initialize=True)

        # Factory function: returns new client each time
        def factory() -> McpClient:
            return base_client.new()

        return factory

    async def ensure_initialized(self) -> None:
        """Ensure registry is initialized (lazy initialization)."""
        if not self._initialized:
            await self.initialize()

    async def initialize(self) -> None:
        """Initialize client factories and fetch tool/resource schemas.

        Creates client factories for each server and uses temporary sessions
        to fetch and cache tool/resource schemas. Sessions are closed after
        schema fetching. Failed connections don't prevent other servers from loading.
        Starts health checking if enabled.
        """
        if self._initialized:
            return

        for server_config in self._config.mcp_servers:
            try:
                # Create client factory
                factory = self._create_client_factory(server_config)

                # Use temporary session to fetch schemas
                async with factory() as client:
                    # Only add factory after successful connection
                    self._client_factories[server_config.name] = factory
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

                    # Fetch and cache tools
                    tools = await client.list_tools()
                    logger.info(f"Server '{server_config.name}' has {len(tools)} tool(s)")

                    for tool in tools:
                        tool_key = f"{server_config.name}:{tool.name}"
                        self._tools[tool_key] = ToolInfo(
                            server_name=server_config.name,
                            name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema or {},
                        )

                    # Fetch and cache resources
                    try:
                        resources = await client.list_resources()
                        logger.info(f"Server '{server_config.name}' has {len(resources)} resource(s)")

                        for resource in resources:
                            resource_key = f"{server_config.name}:{resource.uri}"

                            # Generate description for text resources
                            description = resource.description
                            if not description and _is_text_mime_type(resource.mimeType):
                                try:
                                    contents = await client.read_resource(str(resource.uri))
                                    if contents and len(contents) > 0:
                                        first_content = contents[0]
                                        if hasattr(first_content, "text"):
                                            text_content = first_content.text
                                            description = text_content[:100]
                                            if len(text_content) > 100:
                                                description += "..."
                                except Exception as e:
                                    logger.debug(f"Failed to read resource for description: {e}")

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

            except Exception as e:
                logger.error(f"Failed to connect to server '{server_config.name}': {e}")

        self._initialized = True

        # Start health checker if enabled
        if self._config.health_check_enabled and self._client_factories:
            server_names = list(self._client_factories.keys())
            await self._health_checker.start(server_names)
            logger.info(f"Health checker started for {len(server_names)} server(s)")

    def get_tool_list_text(self) -> str:
        """Generate plain text list of available tools grouped by server.

        This is used for the inspect tool description.

        Returns:
            Plain text listing all available tools grouped by server
        """
        if not self._tools:
            return "No tools available."

        lines = ["Available tools (use inspect with server_name to get details):"]
        for server_name in sorted(self._client_factories.keys()):
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
        """Read resource content using a fresh session.

        Args:
            server_name: Name of the server
            uri: Resource URI to read

        Returns:
            List of content items, or None if factory not found/read fails
        """
        factory = self._client_factories.get(server_name)
        if factory is None:
            return None

        try:
            async with factory() as client:
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
        return list(self._client_factories.keys())

    def has_server(self, server_name: str) -> bool:
        """Check if a server is connected.

        Args:
            server_name: Name of the server

        Returns:
            True if server exists, False otherwise
        """
        return server_name in self._client_factories

    def get_server_info(self, server_name: str) -> ServerInfo | None:
        """Get cached server information.

        Args:
            server_name: Name of the server

        Returns:
            ServerInfo if found, None otherwise
        """
        return self._server_infos.get(server_name)

    def get_client_factory(self, server_name: str) -> Callable[[], McpClient] | None:
        """Get client factory for a server.

        Args:
            server_name: Name of the server

        Returns:
            Client factory if exists, None otherwise
        """
        return self._client_factories.get(server_name)

    @property
    def tools(self) -> dict[str, ToolInfo]:
        """Get all cached tools."""
        return self._tools.copy()

    async def close(self) -> None:
        """Stop health checker and clear caches.

        Sessions are auto-managed via client_factory + async with pattern,
        so no manual session cleanup needed.
        """
        # Stop health checker
        await self._health_checker.stop()

        # Clear caches and factories
        self._client_factories.clear()
        self._tools.clear()
        self._resources.clear()
        self._initialized = False

    async def _get_client_for_health_check(self, server_name: str) -> McpClient | None:
        """Get a fresh client for health checking.

        Returns a new client from the factory. The caller should use it
        with `async with client:` to ensure proper cleanup.

        Args:
            server_name: Name of the server

        Returns:
            New client if factory exists, None otherwise
        """
        factory = self._client_factories.get(server_name)
        if factory is None:
            return None
        return factory()

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
