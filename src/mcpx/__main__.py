"""MCPX - MCP proxy server."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import EmbeddedResource, ImageContent, TextContent

from mcpx.config import McpServerConfig, ProxyConfig
from mcpx.description import generate_tools_description
from mcpx.errors import MCPXError, ValidationError
from mcpx.port_utils import find_available_port
from mcpx.schema_ts import json_schema_to_typescript
from mcpx.server import ServerManager

logger = logging.getLogger(__name__)

__all__ = ["McpServerConfig", "ProxyConfig", "load_config", "create_server", "main"]


def load_config(config_path: Path) -> ProxyConfig:
    """Load configuration from file.

    Args:
        config_path: Path to config.json file

    Returns:
        ProxyConfig with server list

    Raises:
        SystemExit: If config file not found or invalid
    """
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
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


def _maybe_compress_schema(
    input_schema: dict[str, object], enabled: bool
) -> str | dict[str, object]:
    """Compress input_schema to TypeScript format if enabled."""
    if enabled:
        return json_schema_to_typescript(input_schema, max_description_len=300)
    return input_schema


def create_server(
    config: ProxyConfig,
    tools_description: str = "",
    resources_description: str = "",
    manager: ServerManager | None = None,
    registry: Any = None,  # Backward compatibility
) -> FastMCP:
    """Create MCP server from configuration.

    Args:
        config: Proxy configuration
        tools_description: Pre-generated description of available tools
        resources_description: Pre-generated description of available resources
        manager: Optional pre-initialized ServerManager
        registry: Deprecated, use manager instead

    Returns:
        FastMCP server instance
    """
    mcp = FastMCP("MCPX")

    # Use provided manager or create new one
    # Support deprecated 'registry' parameter for backward compatibility
    active_manager = manager or registry or ServerManager(config)

    # Store for access in tools
    mcp._manager = active_manager  # type: ignore[attr-defined]
    mcp._config = config  # type: ignore[attr-defined]
    # Backward compatibility aliases
    mcp._registry = active_manager  # type: ignore[attr-defined]
    mcp._executor = active_manager  # type: ignore[attr-defined]

    @mcp.tool()
    async def invoke(
        method: str,
        arguments: dict[str, object] | None = None,
    ) -> (
        ToolResult
        | str
        | TextContent
        | ImageContent
        | EmbeddedResource
        | list[TextContent | ImageContent | EmbeddedResource]
    ):
        """Invoke an MCP tool.

        Args:
            method: Method identifier in "server.tool" format
            arguments: Tool arguments

        Example:
            invoke(method="filesystem.read_file", arguments={"path": "/tmp/file.txt"})

        Error Handling:
            When invoke fails, it returns helpful information:
            - Server not found: returns error + available_servers list
            - Tool not found: returns error + available_tools list
            - Invalid arguments: returns error + tool_schema
        """
        manager: ServerManager = mcp._manager  # type: ignore[attr-defined]
        config: ProxyConfig = mcp._config  # type: ignore[attr-defined]

        # Parse method string
        parts = method.split(".", 1)
        if len(parts) != 2:
            return json.dumps(
                {"error": f"Invalid method format: '{method}'. Expected 'server.tool'"},
                ensure_ascii=False,
            )

        server_name, tool_name = parts

        try:
            result = await manager.call(server_name, tool_name, arguments or {})

            if not result.success:
                return json.dumps({"error": result.error}, ensure_ascii=False)

            raw_data = result.raw_data
            compressed_data = result.data

            # 多模态内容：直接返回
            if isinstance(raw_data, (TextContent, ImageContent, EmbeddedResource)):
                return raw_data

            # 包含多模态内容的列表
            if isinstance(raw_data, list):
                if any(
                    isinstance(item, (TextContent, ImageContent, EmbeddedResource))
                    for item in raw_data
                ):
                    return raw_data

            # 普通数据：返回 ToolResult
            if result.compressed and isinstance(compressed_data, str):
                if config.include_structured_content:
                    return ToolResult(
                        content=compressed_data, structured_content={"result": raw_data}
                    )
                return ToolResult(content=compressed_data)
            else:
                if config.include_structured_content:
                    return ToolResult(content=raw_data, structured_content={"result": raw_data})
                return ToolResult(content=raw_data)

        except MCPXError as e:
            error_dict = e.to_dict()
            # Apply schema compression if it's a validation error with schema
            if (
                isinstance(e, ValidationError)
                and e.tool_schema
                and config.schema_compression_enabled
            ):
                error_dict["tool_schema"] = json_schema_to_typescript(
                    e.tool_schema, max_description_len=300
                )
            return json.dumps(error_dict, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Unexpected error in invoke: {e}")
            return json.dumps({"error": str(e), "code": "UNEXPECTED_ERROR"}, ensure_ascii=False)

    @mcp.tool()
    async def read(
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
            read(server_name="filesystem", uri="file:///tmp/file.txt")
        """
        manager: ServerManager = mcp._manager  # type: ignore[attr-defined]

        try:
            contents = await manager.read(server_name, uri)

            if len(contents) == 1:
                single_content = contents[0]
                if hasattr(single_content, "text"):
                    return single_content.text
                if hasattr(single_content, "blob"):
                    return {
                        "uri": str(single_content.uri),
                        "mime_type": single_content.mimeType,
                        "blob": single_content.blob,
                    }

            # Multiple contents
            result_list = []
            for content in contents:
                if hasattr(content, "text"):
                    result_list.append({"uri": str(content.uri), "text": content.text})
                elif hasattr(content, "blob"):
                    result_list.append(
                        {
                            "uri": str(content.uri),
                            "mime_type": content.mimeType,
                            "blob": content.blob,
                        }
                    )
            return result_list

        except MCPXError as e:
            return json.dumps(e.to_dict(), ensure_ascii=False)
        except Exception as e:
            logger.error(f"Unexpected error in read: {e}")
            return json.dumps({"error": str(e), "code": "UNEXPECTED_ERROR"}, ensure_ascii=False)

    return mcp


def main() -> None:
    """Main entry point for HTTP/SSE transport."""
    from contextlib import asynccontextmanager
    from typing import AsyncGenerator

    import uvicorn
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.routing import Mount

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Suppress HTTP client noise
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Parse arguments
    parser = argparse.ArgumentParser(
        prog="mcpx-toolkit",
        description="MCPX - MCP proxy server",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("config", nargs="?", default=None, help="Path to config.json")

    args = parser.parse_args()

    # Load config
    if args.config:
        config_path = Path(args.config)
    else:
        config_path = Path(__file__).parent.parent.parent / "config.json"

    config = load_config(config_path)
    logger.info(f"Loaded {len(config.mcpServers)} server(s) from {config_path}")

    # Create and initialize manager once
    manager = ServerManager(config)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        """Initialize manager in uvicorn's event loop."""
        logger.info("Initializing MCP server connections...")
        await manager.initialize()

        tools = manager.list_all_tools()
        resources = manager.list_all_resources()
        logger.info(f"Connected to {len(manager.list_servers())} server(s)")
        logger.info(f"Cached {len(tools)} tool(s), {len(resources)} resource(s)")

        # Log available tools for debugging
        tools_desc = generate_tools_description(manager)
        logger.debug(f"Tools description:\n{tools_desc}")

        yield

        # Cleanup
        logger.info("Shutting down MCP server connections...")
        await manager.close()

    # Create server (manager will be initialized in lifespan)
    mcp = create_server(config, manager=manager)

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

    # Get MCP HTTP app
    mcp_app = mcp.http_app(middleware=middleware)

    # Combined lifespan
    @asynccontextmanager
    async def combined_lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        async with mcp_app.lifespan(app):
            async with lifespan(app):
                yield

    # Create Starlette app
    app = Starlette(
        lifespan=combined_lifespan,
        routes=[Mount("/", app=mcp_app)],
    )

    # Find available port
    actual_port = find_available_port(args.port, host=args.host)
    if actual_port != args.port:
        logger.warning(f"Port {args.port} is occupied, using port {actual_port}")

    logger.info(f"Starting HTTP server on {args.host}:{actual_port}")
    logger.info(f"MCP endpoint: http://{args.host}:{actual_port}/mcp/")
    logger.info("")
    logger.info("Thanks for using mcpx-toolkit!")
    logger.info("https://github.com/quan2005/mcpx")
    logger.info("")

    uvicorn.run(app, host=args.host, port=actual_port)


if __name__ == "__main__":
    main()
