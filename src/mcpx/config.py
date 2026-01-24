"""MCPX 配置模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass

__all__ = ["McpServerConfig", "ProxyConfig"]


class McpServerConfig(BaseModel):
    """MCP server configuration.

    Supports two transport types:
    - stdio: Uses command + args to spawn a subprocess
    - http: Uses url + optional headers for HTTP/SSE transport
    """

    name: str
    type: str = "stdio"  # "stdio" or "http"

    # stdio transport fields
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None

    # http transport fields
    url: str | None = None
    headers: dict[str, str] | None = None

    def model_post_init(self, __context: object) -> None:
        """Validate that required fields are present based on type."""
        if self.type == "stdio":
            if not self.command:
                raise ValueError(f"Server '{self.name}': stdio type requires 'command' field")
        elif self.type == "http":
            if not self.url:
                raise ValueError(f"Server '{self.name}': http type requires 'url' field")
        else:
            raise ValueError(f"Server '{self.name}': unknown type '{self.type}', must be 'stdio' or 'http'")


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    mcp_servers: list[McpServerConfig] = Field(default_factory=list)

    # Health check configuration
    health_check_enabled: bool = True
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 5  # seconds
    health_check_failure_threshold: int = 2  # consecutive failures

    # TOON compression configuration
    toon_compression_enabled: bool = True
    toon_compression_min_size: int = 3  # minimum items/keys to compress

    # Schema compression configuration (TypeScript style)
    schema_compression_enabled: bool = True

    model_config = {"extra": "ignore"}
