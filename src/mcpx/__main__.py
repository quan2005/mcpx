"""MCPX - MCP proxy server with progressive tool loading."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import EmbeddedResource, ImageContent, TextContent

from mcpx.config import McpServerConfig, ProxyConfig
from mcpx.schema_ts import json_schema_to_typescript

if TYPE_CHECKING:
    from mcpx.executor import Executor
    from mcpx.registry import Registry

logger = logging.getLogger(__name__)


class ValidationErrorFilter(logging.Filter):
    """Filter to suppress validation error logs from FastMCP.

    These errors occur when clients pass invalid arguments (e.g., string instead of dict),
    which is a normal situation that should be handled gracefully without logging errors.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress, True to keep the log record."""
        # Suppress "Error validating tool" messages
        if "Error validating tool" in record.getMessage():
            return False
        return True


def _setup_fastmcp_logging() -> None:
    """Configure FastMCP logger to suppress validation error logs."""
    fastmcp_server_logger = logging.getLogger("fastmcp.server.server")
    fastmcp_server_logger.addFilter(ValidationErrorFilter())

__all__ = [
    "McpServerConfig",
    "ProxyConfig",
    "load_config",
    "create_server",
    "main",
]


def generate_tools_description(registry: "Registry") -> str:
    """Generate a compact description of all available tools.

    Format: server.tool(param, param?): description

    Args:
        registry: Initialized registry with cached tools

    Returns:
        Formatted string with all tools in compact format
    """
    tools_desc_lines = ["Available tools:"]

    for server_name in sorted(registry.list_servers()):
        for tool in registry.list_tools(server_name):
            # Extract parameter list from input_schema
            params = []
            properties = tool.input_schema.get("properties", {})
            required = set(tool.input_schema.get("required", []))
            for param_name in sorted(properties.keys()):
                # Required params shown as-is, optional with ?
                params.append(param_name if param_name in required else f"{param_name}?")
            params_str = ", ".join(params) if params else ""

            # Truncate description if too long (60 chars)
            desc = tool.description
            if len(desc) > 60:
                desc = desc[:57] + "..."

            # Format: server.tool(params): desc
            full_name = f"{server_name}.{tool.name}"
            if params_str:
                tools_desc_lines.append(f"  - {full_name}({params_str}): {desc}")
            else:
                tools_desc_lines.append(f"  - {full_name}: {desc}")

    return "\n".join(tools_desc_lines)


def generate_resources_description(registry: "Registry") -> str:
    """Generate a compact description of all available resources.

    Args:
        registry: Initialized registry with cached resources

    Returns:
        Formatted string with all resources grouped by server
    """
    resources_desc_lines = ["Available resources:"]
    for server_name in sorted(registry.list_servers()):
        resources = registry.list_resources(server_name)
        if not resources:
            continue

        # Get server info for description
        server_info = registry.get_server_info(server_name)
        if server_info and server_info.instructions:
            server_desc = server_info.instructions
            if len(server_desc) > 300:
                server_desc = server_desc[:297] + "..."
            resources_desc_lines.append(f"  Server: {server_name} - {server_desc}")
        else:
            resources_desc_lines.append(f"  Server: {server_name}")

        for resource in resources:
            # Build resource info line
            mime_info = f" [{resource.mime_type}]" if resource.mime_type else ""
            size_info = f" ({resource.size} bytes)" if resource.size is not None else ""

            # Truncate description if too long (consistent with tools)
            desc = ""
            if resource.description:
                desc_text = resource.description
                if len(desc_text) > 80:
                    desc_text = desc_text[:77] + "..."
                desc = f": {desc_text}"

            resources_desc_lines.append(
                f"    - {resource.name} ({resource.uri}){mime_info}{size_info}{desc}"
            )
    return "\n".join(resources_desc_lines) if len(resources_desc_lines) > 1 else "No resources available."


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
    resources_description: str = "",
    registry: "Registry | None" = None,
) -> FastMCP:
    """Create MCP server from configuration.

    The server exposes three tools:
    - describe: Get full schema of cached tools (with TOON compression support)
    - call: Execute tools through long-lived connections (with TOON compression support)
    - resources: List or read resources from MCP servers

    Args:
        config: Proxy configuration
        tools_description: Pre-generated description of available tools
        resources_description: Pre-generated description of available resources
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

    def _maybe_compress_schema(input_schema: dict[str, object]) -> str | dict[str, object]:
        """Compress input_schema to TypeScript format if enabled.

        Args:
            input_schema: JSON Schema dictionary

        Returns:
            TypeScript type string if compression enabled, otherwise original schema
        """
        if config.schema_compression_enabled:
            # Keep descriptions with reasonable length limit
            return json_schema_to_typescript(input_schema, max_description_len=300)
        return input_schema

    # Build the describe description
    base_desc = "Query tool information from MCP servers.\n\n"
    if tools_description:
        full_desc = base_desc + tools_description
    else:
        full_desc = base_desc + "Tools will be listed after initialization."

    @mcp.tool(description=full_desc)
    async def describe(
        method: str,
    ) -> ToolResult | str:
        """Query tool information from MCP servers.

        Args:
            method: Method identifier in "server" or "server.tool" format
                - "server": List all tools from this server
                - "server.tool": Get detailed schema for this tool

        Returns:
            ToolResult with:
            - content: TOON 压缩后的数据（用于 AI 阅读）
            - structured_content: 原始未压缩的 JSON 数据（用于程序解析）

        Examples:
            # List all tools from a server
            describe(method="filesystem")

            # Get details for a specific tool
            describe(method="filesystem.read_file")
        """
        registry: Registry = mcp._registry  # type: ignore[attr-defined]
        executor: Executor = mcp._executor  # type: ignore[attr-defined]

        # Ensure registry is initialized
        await registry.ensure_initialized()

        def _build_result(data: Any) -> ToolResult:
            """Build ToolResult with compressed content and optional structured_content."""
            compressed, was_compressed = executor._compressor.compress(
                data, min_size=config.toon_compression_min_size
            )
            if was_compressed and isinstance(compressed, str):
                # content: 压缩后的 TOON 字符串
                if config.include_structured_content:
                    # structured_content: 原始未压缩数据
                    return ToolResult(content=compressed, structured_content={"result": data})
                # 仅返回压缩内容
                return ToolResult(content=compressed)
            # 未压缩
            if config.include_structured_content:
                return ToolResult(content=data, structured_content={"result": data})
            return ToolResult(content=data)

        # Parse method string
        parts = method.split(".", 1)
        server_name = parts[0]
        tool_name = parts[1] if len(parts) > 1 else None

        # Check if server exists
        if not registry.has_server(server_name):
            servers = registry.list_servers()
            if servers:
                error_data = {
                    "error": f"Server '{server_name}' not found",
                    "available_servers": servers,
                }
            else:
                logger.warning(f"Server '{server_name}' not found - no MCP servers connected")
                error_data = {
                    "error": f"Server '{server_name}' not found",
                    "hint": "No MCP servers are currently connected",
                }
            return json.dumps(error_data, ensure_ascii=False)

        # Get specific tool
        if tool_name:
            tool = registry.get_tool(server_name, tool_name)
            if tool is None:
                available = [t.name for t in registry.list_tools(server_name)]
                error_data = {
                    "error": f"Tool '{tool_name}' not found on server '{server_name}'",
                    "available_tools": available,
                }
                return json.dumps(error_data, ensure_ascii=False)
            tool_data = {
                "method": f"{tool.server_name}.{tool.name}",
                "description": tool.description,
                "input_schema": _maybe_compress_schema(tool.input_schema),
            }
            return _build_result(tool_data)

        # List all tools from the server
        tools = registry.list_tools(server_name)
        tools_data = [
            {
                "method": f"{t.server_name}.{t.name}",
                "description": t.description,
                "input_schema": _maybe_compress_schema(t.input_schema),
            }
            for t in tools
        ]
        return _build_result(tools_data)

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
    async def call(
        method: str,
        arguments: dict[str, object] | None = None,
    ) -> ToolResult | str | TextContent | ImageContent | EmbeddedResource | list[TextContent | ImageContent | EmbeddedResource]:
        """Execute an MCP tool.

        Args:
            method: Method identifier in "server.tool" format
            arguments: Tool arguments (use describe to get schema)

        Example:
            call(method="filesystem.read_file", arguments={"path": "/tmp/file.txt"})
        """
        executor: Executor = mcp._executor  # type: ignore[attr-defined]

        # Ensure registry is initialized
        registry: Registry = mcp._registry  # type: ignore[attr-defined]
        await registry.ensure_initialized()

        # Parse method string
        parts = method.split(".", 1)
        if len(parts) != 2:
            error_data = {"error": f"Invalid method format: '{method}'. Expected 'server.tool'"}
            return json.dumps(error_data, ensure_ascii=False)

        server_name, tool_name = parts

        # Check if server exists
        if not registry.has_server(server_name):
            servers = registry.list_servers()
            if servers:
                error_data = {"error": f"Server '{server_name}' not found. Available: {servers}"}
            else:
                logger.warning(f"Server '{server_name}' not found - no MCP servers connected")
                error_data = {
                    "error": f"Server '{server_name}' not found",
                    "hint": "No MCP servers are currently connected",
                }
            return json.dumps(error_data, ensure_ascii=False)

        # Check if tool exists
        tool_info = registry.get_tool(server_name, tool_name)
        if tool_info is None:
            available = [t.name for t in registry.list_tools(server_name)]
            error_data = {
                "error": f"Tool '{tool_name}' not found on server '{server_name}'. Available: {available}",
            }
            return json.dumps(error_data, ensure_ascii=False)

        # Validate arguments before execution
        validation_error = _validate_arguments(arguments, tool_info.input_schema)
        if validation_error:
            validation_error_data = {
                "error": f"Argument validation failed: {validation_error}",
                "tool_schema": _maybe_compress_schema(tool_info.input_schema),
            }
            return json.dumps(validation_error_data, ensure_ascii=False)

        args = arguments or {}

        result = await executor.execute(server_name, tool_name, args)

        # Success: return ToolResult with compressed and optionally structured_content
        if result.success:
            raw_data = result.raw_data
            compressed_data = result.data

            # 多模态内容：直接返回原始对象（不适用 ToolResult）
            if isinstance(raw_data, (TextContent, ImageContent, EmbeddedResource)):
                return raw_data
            # 包含多模态内容的列表：直接返回
            if isinstance(raw_data, list):
                if any(isinstance(item, (TextContent, ImageContent, EmbeddedResource)) for item in raw_data):
                    return raw_data

            # 普通数据：返回 ToolResult
            # content: 压缩后的数据（TOON 字符串或原始数据）
            # structured_content: 原始未压缩的 JSON 数据（如果配置启用）
            if result.compressed and isinstance(compressed_data, str):
                # 压缩成功：content 是 TOON 字符串
                if config.include_structured_content:
                    return ToolResult(content=compressed_data, structured_content={"result": raw_data})
                return ToolResult(content=compressed_data)
            else:
                # 未压缩
                if config.include_structured_content:
                    return ToolResult(content=raw_data, structured_content={"result": raw_data})
                return ToolResult(content=raw_data)

        # Failure: return error message
        exec_error_data = {"error": result.error}
        return json.dumps(exec_error_data, ensure_ascii=False)

    # Build the resources description
    base_resources_desc = "Read MCP server resources.\n\n"
    if resources_description:
        full_resources_desc = base_resources_desc + resources_description
    else:
        full_resources_desc = base_resources_desc + "Resources will be listed after initialization."

    @mcp.tool(description=full_resources_desc)
    async def resources(
        server_name: str,
        uri: str,
    ) -> Any:
        """Read a resource from MCP servers.

        Args:
            server_name: Server name (required)
            uri: Resource URI (required)

        Returns:
            - Text resource: string content
            - Binary resource: dict with uri, mime_type, and blob (base64)
            - Multiple contents: list of content items

        Examples:
            # Read a specific resource
            resources(server_name="filesystem", uri="file:///tmp/file.txt")
        """
        registry: Registry = mcp._registry  # type: ignore[attr-defined]

        # Ensure registry is initialized
        await registry.ensure_initialized()

        # Check if server exists
        if not registry.has_server(server_name):
            servers = registry.list_servers()
            if servers:
                error_data = {
                    "error": f"Server '{server_name}' not found",
                    "available_servers": servers,
                }
            else:
                logger.warning(f"Server '{server_name}' not found - no MCP servers connected")
                error_data = {
                    "error": f"Server '{server_name}' not found",
                    "hint": "No MCP servers are currently connected",
                }
            return json.dumps(error_data, ensure_ascii=False)

        # Read resource
        contents = await registry.read_resource(server_name, uri)
        if contents is None:
            error_data = {
                "error": f"Failed to read resource '{uri}' from server '{server_name}'",
            }
            return json.dumps(error_data, ensure_ascii=False)

        # Return raw content (TextResourceContents or BlobResourceContents)
        # Each content has a `uri` and either `text` or `blob`
        if len(contents) == 1:
            single_content = contents[0]
            # TextResourceContents: return text directly
            if hasattr(single_content, "text"):
                return single_content.text
            # BlobResourceContents: return as dict with base64 blob
            if hasattr(single_content, "blob"):
                return {
                    "uri": str(single_content.uri),
                    "mime_type": single_content.mimeType,
                    "blob": single_content.blob,
                }
        # Multiple contents: return list of dicts
        result_list = []
        for content in contents:
            if hasattr(content, "text"):
                result_list.append({"uri": str(content.uri), "text": content.text})
            elif hasattr(content, "blob"):
                result_list.append({
                    "uri": str(content.uri),
                    "mime_type": content.mimeType,
                    "blob": content.blob,
                })
        return result_list

    return mcp


def main(port: int = 8000, host: str = "0.0.0.0") -> None:
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
    _setup_fastmcp_logging()

    # Default config path
    config_path = Path(__file__).parent.parent.parent / "config.json"

    # Allow override via command line
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])

    # Load configuration
    config = load_config(config_path)
    logger.info(f"Loaded {len(config.mcpServers)} server(s) from {config_path}")

    from mcpx.registry import Registry

    # Initialize a temporary registry to get tools description
    # This is needed because MCP tool descriptions must be set at creation time
    temp_registry = Registry(config)
    asyncio.run(temp_registry.initialize())

    # Generate tools description from temporary registry
    tools = temp_registry.list_all_tools()
    logger.info(f"Pre-connected to {len(temp_registry.list_servers())} server(s)")
    logger.info(f"Discovered {len(tools)} tool(s)")
    tools_description = generate_tools_description(temp_registry)

    # Generate resources description from temporary registry
    all_resources = temp_registry.list_all_resources()
    logger.info(f"Discovered {len(all_resources)} resource(s)")
    resources_description = generate_resources_description(temp_registry)

    # Close temporary registry connections (will be re-established in lifespan)
    asyncio.run(temp_registry.close())

    # Create a fresh registry for the actual server (will be initialized in lifespan)
    registry = Registry(config)

    # Create server with full tools and resources description
    mcp = create_server(config, tools_description, resources_description, registry=registry)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        """Initialize registry in uvicorn's event loop."""
        logger.info("Initializing MCP server connections...")
        await registry.initialize()

        tools = registry.list_all_tools()
        logger.info(f"Connected to {len(registry.list_servers())} server(s)")
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
    import argparse

    parser = argparse.ArgumentParser(description="MCPX - MCP proxy server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("config", nargs="?", default=None, help="Path to config.json file")

    args = parser.parse_args()

    # Override config path if provided
    if args.config:
        sys.argv = [sys.argv[0], args.config]

    main(port=args.port, host=args.host)
