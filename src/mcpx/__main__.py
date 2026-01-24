"""MCPX - MCP proxy server with progressive tool loading."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from mcpx.executor import Executor
    from mcpx.registry import Registry

logger = logging.getLogger(__name__)

__all__ = [
    "McpServerConfig",
    "ProxyConfig",
    "load_config",
    "create_server",
    "main",
    "main_http",
]


class McpServerConfig(BaseModel):
    """MCP server configuration."""

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    mcp_servers: list[McpServerConfig] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


def load_config(config_path: Path) -> ProxyConfig:
    """Load configuration from file.

    Args:
        config_path: Path to config.json file

    Returns:
        ProxyConfig with server list

    Raises:
        SystemExit: If config file not found
    """
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        logger.error("Create a config.json file with MCP server configurations.")
        sys.exit(1)

    try:
        with open(config_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        sys.exit(1)

    try:
        return ProxyConfig(**data)
    except Exception as e:
        logger.error(f"Invalid config structure: {e}")
        sys.exit(1)


def create_server(config: ProxyConfig, tools_description: str = "") -> FastMCP:
    """Create MCP server from configuration.

    The server exposes only two tools:
    - inspect: Get full schema of cached tools
    - exec: Execute tools through long-lived connections

    Args:
        config: Proxy configuration
        tools_description: Pre-generated description of available tools

    Returns:
        FastMCP server instance
    """
    from mcpx.executor import Executor
    from mcpx.registry import Registry

    mcp = FastMCP("MCPX")

    # Store config and components (dynamic attributes for type checking)
    mcp._config = config  # type: ignore[attr-defined]
    mcp._registry = Registry(config)  # type: ignore[attr-defined]
    mcp._executor = Executor(mcp._registry)  # type: ignore[attr-defined]

    # Build the inspect description
    base_desc = "Inspect available MCP tools and their schemas.\n\n"
    if tools_description:
        full_desc = base_desc + tools_description
    else:
        full_desc = base_desc + "Tools will be listed after initialization."

    @mcp.tool(description=full_desc)
    async def inspect(
        server_name: str,
        tool_name: str | None = None,
    ) -> str:
        """Query tool information from MCP servers.

        Args:
            server_name: Server name (required). Lists all tools from this server.
            tool_name: Specific tool name (optional). If provided, returns detailed schema for this tool.

        Returns:
            JSON string with tool information

        Examples:
            # List all tools from a server
            inspect(server_name="filesystem")

            # Get details for a specific tool
            inspect(server_name="filesystem", tool_name="read_file")
        """
        registry: Registry = mcp._registry  # type: ignore[attr-defined]

        # Ensure registry is initialized
        await registry.ensure_initialized()

        # Check if server exists
        if server_name not in registry.sessions:
            servers = registry.list_servers()
            return json.dumps(
                {
                    "error": f"Server '{server_name}' not found",
                    "available_servers": servers,
                },
                ensure_ascii=False,
                indent=2,
            )

        # Get specific tool
        if tool_name:
            tool = registry.get_tool(server_name, tool_name)
            if tool is None:
                available = [t.name for t in registry.list_tools(server_name)]
                return json.dumps(
                    {
                        "error": f"Tool '{tool_name}' not found on server '{server_name}'",
                        "available_tools": available,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            return json.dumps(
                {
                    "server_name": tool.server_name,
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                },
                ensure_ascii=False,
                indent=2,
            )

        # List all tools from the server
        tools = registry.list_tools(server_name)
        return json.dumps(
            [
                {
                    "server_name": t.server_name,
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ],
            ensure_ascii=False,
            indent=2,
        )

    def _validate_arguments(
        arguments: dict[str, object] | None,
        input_schema: dict[str, object],
    ) -> str | None:
        """Validate arguments against input schema.

        Args:
            arguments: Arguments to validate
            input_schema: JSON schema for the tool's input

        Returns:
            Error message if validation fails, None if valid
        """
        args = arguments or {}

        # Check required fields
        required = input_schema.get("required", [])
        if isinstance(required, list):
            for field in required:
                if field not in args:
                    return f"Missing required argument: '{field}'"

        # Check properties
        properties = input_schema.get("properties", {})
        if isinstance(properties, dict):
            for key in args:
                if key not in properties:
                    available = list(properties.keys())
                    return f"Unknown argument: '{key}'. Available: {available}"

        return None

    @mcp.tool
    async def exec(
        server_name: str,
        tool_name: str,
        arguments: dict[str, object] | None = None,
    ) -> str:
        """Execute an MCP tool through the proxy.

        Args:
            server_name: Server name (required)
            tool_name: Tool name (required)
            arguments: Tool arguments (must match the tool's input schema)

        Returns:
            JSON string with execution result

        Examples:
            # Execute a tool
            exec(server_name="filesystem", tool_name="read_file", arguments={"path": "/tmp/file.txt"})

        Notes:
            - Use inspect to get the correct schema for arguments
            - Arguments must match the tool's input schema or execution will fail
        """
        executor: Executor = mcp._executor  # type: ignore[attr-defined]

        # Ensure registry is initialized
        registry: Registry = mcp._registry  # type: ignore[attr-defined]
        await registry.ensure_initialized()

        # Check if server exists
        if server_name not in registry.sessions:
            servers = registry.list_servers()
            return json.dumps(
                {
                    "tool_name": tool_name,
                    "server_name": server_name,
                    "success": False,
                    "data": None,
                    "error": f"Server '{server_name}' not found. Available: {servers}",
                },
                ensure_ascii=False,
                indent=2,
            )

        # Check if tool exists
        tool_info = registry.get_tool(server_name, tool_name)
        if tool_info is None:
            available = [t.name for t in registry.list_tools(server_name)]
            return json.dumps(
                {
                    "tool_name": tool_name,
                    "server_name": server_name,
                    "success": False,
                    "data": None,
                    "error": f"Tool '{tool_name}' not found on server '{server_name}'. Available: {available}",
                },
                ensure_ascii=False,
                indent=2,
            )

        # Validate arguments before execution
        validation_error = _validate_arguments(arguments, tool_info.input_schema)
        if validation_error:
            return json.dumps(
                {
                    "tool_name": tool_name,
                    "server_name": server_name,
                    "success": False,
                    "data": None,
                    "error": f"Argument validation failed: {validation_error}",
                },
                ensure_ascii=False,
                indent=2,
            )

        args = arguments or {}

        result = await executor.execute(server_name, tool_name, args)

        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    return mcp


def main() -> None:
    """Main entry point for stdio transport."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Default config path
    config_path = Path(__file__).parent.parent.parent / "config.json"

    # Allow override via command line
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])

    # Load configuration
    config = load_config(config_path)
    logger.info(f"Loaded {len(config.mcp_servers)} server(s) from {config_path}")

    # Initialize registry first to generate tools description
    from mcpx.registry import Registry

    temp_registry = Registry(config)
    asyncio.run(temp_registry.initialize())

    # Generate tools description
    tools = temp_registry.list_all_tools()
    logger.info(f"Connected to {len(temp_registry.sessions)} server(s)")
    logger.info(f"Cached {len(tools)} tool(s)")

    # Build compact tools description grouped by server
    tools_desc_lines = ["Available tools:"]
    for server_name in sorted(temp_registry.list_servers()):
        # Get server info for description
        server_info = temp_registry.get_server_info(server_name)
        if server_info and server_info.instructions:
            # Use instructions as server description
            server_desc = server_info.instructions
            if len(server_desc) > 100:
                server_desc = server_desc[:97] + "..."
            tools_desc_lines.append(f"  Server: {server_name} - {server_desc}")
        else:
            tools_desc_lines.append(f"  Server: {server_name}")

        for tool in temp_registry.list_tools(server_name):
            # Truncate description if too long
            desc = tool.description
            if len(desc) > 80:
                desc = desc[:77] + "..."
            tools_desc_lines.append(f"    - {tool.name}: {desc}")
    tools_description = "\n".join(tools_desc_lines)

    # Create server with pre-generated tools description
    mcp = create_server(config, tools_description)
    # Transfer the initialized registry to the mcp instance
    mcp._registry = temp_registry  # type: ignore[attr-defined]

    # Run the server
    asyncio.run(mcp.run_async())


def main_http(port: int = 8000, host: str = "0.0.0.0") -> None:
    """Main entry point for HTTP/SSE transport.

    Args:
        port: Port to listen on (default: 8000)
        host: Host to bind to (default: 0.0.0.0)
    """

    import uvicorn
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Default config path
    config_path = Path(__file__).parent.parent.parent / "config.json"

    # Allow override via command line
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])

    # Load configuration
    config = load_config(config_path)
    logger.info(f"Loaded {len(config.mcp_servers)} server(s) from {config_path}")

    # Initialize registry first to generate tools description
    from mcpx.registry import Registry

    temp_registry = Registry(config)
    asyncio.run(temp_registry.initialize())

    # Generate tools description
    tools = temp_registry.list_all_tools()
    logger.info(f"Connected to {len(temp_registry.sessions)} server(s)")
    logger.info(f"Cached {len(tools)} tool(s)")

    # Build compact tools description grouped by server
    tools_desc_lines = ["Available tools:"]
    for server_name in sorted(temp_registry.list_servers()):
        # Get server info for description
        server_info = temp_registry.get_server_info(server_name)
        if server_info and server_info.instructions:
            # Use instructions as server description
            server_desc = server_info.instructions
            if len(server_desc) > 100:
                server_desc = server_desc[:97] + "..."
            tools_desc_lines.append(f"  Server: {server_name} - {server_desc}")
        else:
            tools_desc_lines.append(f"  Server: {server_name}")

        for tool in temp_registry.list_tools(server_name):
            # Truncate description if too long
            desc = tool.description
            if len(desc) > 80:
                desc = desc[:77] + "..."
            tools_desc_lines.append(f"    - {tool.name}: {desc}")
    tools_description = "\n".join(tools_desc_lines)

    # Create server with pre-generated tools description
    mcp = create_server(config, tools_description)
    # Transfer the initialized registry to the mcp instance
    mcp._registry = temp_registry  # type: ignore[attr-defined]

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "mcp-protocol-version",
                "mcp-session-id",
                "Authorization",
                "Content-Type",
            ],
            expose_headers=["mcp-session-id"],
        )
    ]

    http_app = mcp.http_app(middleware=middleware)

    logger.info(f"Starting HTTP server on {host}:{port}")
    logger.info(f"MCP endpoint: http://{host}:{port}/mcp/")
    uvicorn.run(http_app, host=host, port=port)


if __name__ == "__main__":
    main()
