"""MCPX - MCP proxy server with progressive tool loading."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import EmbeddedResource, ImageContent, TextContent

from mcpx.config import McpServerConfig, ProxyConfig

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


def create_server(
    config: ProxyConfig,
    tools_description: str = "",
    registry: "Registry | None" = None,
) -> FastMCP:
    """Create MCP server from configuration.

    The server exposes two tools:
    - inspect: Get full schema of cached tools (with TOON compression support)
    - exec: Execute tools through long-lived connections (with TOON compression support)

    Args:
        config: Proxy configuration
        tools_description: Pre-generated description of available tools
        registry: Optional pre-initialized registry

    Returns:
        FastMCP server instance
    """
    from mcpx.executor import Executor
    from mcpx.registry import Registry

    mcp = FastMCP("MCPX")

    active_registry = registry or Registry(config)

    # Store config and components (dynamic attributes for type checking)
    mcp._config = config  # type: ignore[attr-defined]
    mcp._registry = active_registry  # type: ignore[attr-defined]
    mcp._executor = Executor(  # type: ignore[attr-defined]
        active_registry,
        toon_compression_enabled=config.toon_compression_enabled,
        toon_compression_min_size=config.toon_compression_min_size,
    )

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
            JSON string with tool information (optionally TOON compressed)

        Examples:
            # List all tools from a server
            inspect(server_name="filesystem")

            # Get details for a specific tool
            inspect(server_name="filesystem", tool_name="read_file")
        """
        registry: Registry = mcp._registry  # type: ignore[attr-defined]
        executor: Executor = mcp._executor  # type: ignore[attr-defined]

        # Ensure registry is initialized
        await registry.ensure_initialized()

        # Check if server exists
        if server_name not in registry.sessions:
            servers = registry.list_servers()
            error_data = {
                "error": f"Server '{server_name}' not found",
                "available_servers": servers,
            }
            # Apply compression with lower threshold for inspect responses
            compressed, _ = executor._compressor.compress(error_data, min_size=1)
            if isinstance(compressed, str):
                return compressed
            return json.dumps(error_data, ensure_ascii=False, indent=2)

        # Get specific tool
        if tool_name:
            tool = registry.get_tool(server_name, tool_name)
            if tool is None:
                available = [t.name for t in registry.list_tools(server_name)]
                error_data = {
                    "error": f"Tool '{tool_name}' not found on server '{server_name}'",
                    "available_tools": available,
                }
                # Apply compression with lower threshold
                compressed, _ = executor._compressor.compress(error_data, min_size=1)
                if isinstance(compressed, str):
                    return compressed
                return json.dumps(error_data, ensure_ascii=False, indent=2)
            tool_data = {
                "server_name": tool.server_name,
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            # Apply compression with lower threshold
            compressed, _ = executor._compressor.compress(tool_data, min_size=1)
            if isinstance(compressed, str):
                return compressed
            return json.dumps(tool_data, ensure_ascii=False, indent=2)

        # List all tools from the server
        tools = registry.list_tools(server_name)
        tools_data = [
            {
                "server_name": t.server_name,
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]
        # Apply compression with lower threshold (tool schemas are large even for single items)
        compressed, _ = executor._compressor.compress(tools_data, min_size=1)
        if isinstance(compressed, str):
            return compressed
        return json.dumps(tools_data, ensure_ascii=False, indent=2)

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
    ) -> str | TextContent | ImageContent | EmbeddedResource | list[TextContent | ImageContent | EmbeddedResource]:
        """Execute an MCP tool through the proxy.

        Args:
            server_name: Server name (required)
            tool_name: Tool name (required)
            arguments: Tool arguments (must match the tool's input schema)

        Returns:
            - str: 纯文本或 JSON 字符串
            - TextContent: 文本内容
            - ImageContent: 图片内容（base64 编码）
            - EmbeddedResource: 资源引用
            - list: 多个内容项

        Examples:
            # Execute a tool
            exec(server_name="filesystem", tool_name="read_file", arguments={"path": "/tmp/file.txt"})

        Notes:
            - Use inspect to get the correct schema for arguments
            - Arguments must match the tool's input schema or execution will fail
            - 支持透传多模态内容（图片、资源等）
        """
        executor: Executor = mcp._executor  # type: ignore[attr-defined]

        # Ensure registry is initialized
        registry: Registry = mcp._registry  # type: ignore[attr-defined]
        await registry.ensure_initialized()

        # Check if server exists
        if server_name not in registry.sessions:
            servers = registry.list_servers()
            error_data = {"error": f"Server '{server_name}' not found. Available: {servers}"}
            # Error responses: use lower min_size for compression
            compressed, _ = executor._compressor.compress(error_data, min_size=1)
            if isinstance(compressed, str) and compressed != str(error_data):
                return compressed
            return json.dumps(error_data, ensure_ascii=False)

        # Check if tool exists
        tool_info = registry.get_tool(server_name, tool_name)
        if tool_info is None:
            available = [t.name for t in registry.list_tools(server_name)]
            error_data = {
                "error": f"Tool '{tool_name}' not found on server '{server_name}'. Available: {available}",
            }
            compressed, _ = executor._compressor.compress(error_data, min_size=1)
            if isinstance(compressed, str) and compressed != str(error_data):
                return compressed
            return json.dumps(error_data, ensure_ascii=False)

        # Validate arguments before execution
        validation_error = _validate_arguments(arguments, tool_info.input_schema)
        if validation_error:
            validation_error_data = {
                "error": f"Argument validation failed: {validation_error}",
                "tool_schema": tool_info.input_schema,
            }
            compressed, _ = executor._compressor.compress(validation_error_data, min_size=1)
            if isinstance(compressed, str) and compressed != str(validation_error_data):
                return compressed
            return json.dumps(validation_error_data, ensure_ascii=False)

        args = arguments or {}

        result = await executor.execute(server_name, tool_name, args)

        # Success: return data directly
        if result.success:
            data = result.data
            # 多模态内容：直接返回原始对象
            if isinstance(data, (TextContent, ImageContent, EmbeddedResource)):
                return data
            # 包含多模态内容的列表：直接返回
            if isinstance(data, list):
                if any(isinstance(item, (TextContent, ImageContent, EmbeddedResource)) for item in data):
                    return data
            # 字符串：直接返回
            if isinstance(data, str):
                return data
            # 其他 JSON 数据：序列化
            return json.dumps(data, ensure_ascii=False, indent=2)

        # Failure: return error message with compression
        exec_error_data = {"error": result.error}
        compressed, _ = executor._compressor.compress(exec_error_data, min_size=1)
        if isinstance(compressed, str) and compressed != str(exec_error_data):
            return compressed
        return json.dumps(exec_error_data, ensure_ascii=False)

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

    # Create server with pre-generated tools description and initialized registry
    mcp = create_server(config, tools_description, registry=temp_registry)

    # Run the server
    asyncio.run(mcp.run_async())


def main_http(port: int = 8000, host: str = "0.0.0.0") -> None:
    """Main entry point for HTTP/SSE transport.

    Uses lazy initialization to ensure registry connections are established
    in uvicorn's event loop, not a separate asyncio.run() loop.

    Args:
        port: Port to listen on (default: 8000)
        host: Host to bind to (default: 0.0.0.0)
    """
    from contextlib import asynccontextmanager
    from typing import AsyncGenerator

    import uvicorn
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.routing import Mount

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Default config path
    config_path = Path(__file__).parent.parent.parent / "config.json"

    # Allow override via command line
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])

    # Load configuration
    config = load_config(config_path)
    logger.info(f"Loaded {len(config.mcp_servers)} server(s) from {config_path}")

    # Create registry but DON'T initialize yet - will be done in lifespan
    from mcpx.registry import Registry

    registry = Registry(config)

    # Create server with placeholder description (registry not yet initialized)
    # The tools list will be generated dynamically after initialization
    server_names = [s.name for s in config.mcp_servers]
    placeholder_desc = f"Available servers: {', '.join(server_names)}\nUse inspect(server_name) to list tools."
    mcp = create_server(config, placeholder_desc, registry=registry)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        """Initialize registry in uvicorn's event loop."""
        logger.info("Initializing MCP server connections...")
        await registry.initialize()

        tools = registry.list_all_tools()
        logger.info(f"Connected to {len(registry.sessions)} server(s)")
        logger.info(f"Cached {len(tools)} tool(s)")

        # Log available tools
        for server_name in sorted(registry.list_servers()):
            server_tools = registry.list_tools(server_name)
            logger.info(f"  Server '{server_name}': {len(server_tools)} tool(s)")

        yield

        # Cleanup on shutdown
        logger.info("Shutting down MCP server connections...")
        await registry.close()

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

    # Get the MCP HTTP app - it has its own lifespan for task group initialization
    mcp_app = mcp.http_app(middleware=middleware)

    # Create a combined lifespan that runs both our registry init and FastMCP's lifespan
    @asynccontextmanager
    async def combined_lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        """Combined lifespan: FastMCP task group + registry initialization."""
        # First, run FastMCP's lifespan to initialize task group
        async with mcp_app.lifespan(app):
            # Then run our registry initialization
            async with lifespan(app):
                yield

    # Wrap with combined lifespan
    app = Starlette(
        lifespan=combined_lifespan,
        routes=[Mount("/", app=mcp_app)],
    )

    logger.info(f"Starting HTTP server on {host}:{port}")
    logger.info(f"MCP endpoint: http://{host}:{port}/mcp/")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
