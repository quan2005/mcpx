"""统一错误类型定义。"""

from __future__ import annotations

from typing import Any


class MCPXError(Exception):
    """MCPX 基础错误类。"""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or "UNKNOWN_ERROR"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {"error": self.message, "code": self.code}


class ServerNotFoundError(MCPXError):
    """服务器不存在错误。"""

    def __init__(self, server_name: str, available_servers: list[str] | None = None) -> None:
        self.server_name = server_name
        self.available_servers = available_servers or []

        if available_servers:
            msg = f"Server '{server_name}' not found. Available: {available_servers}"
        else:
            msg = f"Server '{server_name}' not found"

        super().__init__(msg, "SERVER_NOT_FOUND")

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        if self.available_servers:
            result["available_servers"] = self.available_servers
        else:
            result["hint"] = "No MCP servers are currently connected"
        return result


class ToolNotFoundError(MCPXError):
    """工具不存在错误。"""

    def __init__(
        self, server_name: str, tool_name: str, available_tools: list[str] | None = None
    ) -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        self.available_tools = available_tools or []

        if available_tools:
            msg = f"Tool '{tool_name}' not found on server '{server_name}'. Available: {available_tools}"
        else:
            msg = f"Tool '{tool_name}' not found on server '{server_name}'"

        super().__init__(msg, "TOOL_NOT_FOUND")

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        if self.available_tools:
            result["available_tools"] = self.available_tools
        return result


class ValidationError(MCPXError):
    """参数校验错误。"""

    def __init__(self, message: str, tool_schema: dict[str, Any] | None = None) -> None:
        self.tool_schema = tool_schema
        super().__init__(f"Argument validation failed: {message}", "VALIDATION_ERROR")

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        if self.tool_schema:
            result["tool_schema"] = self.tool_schema
        return result


class ResourceNotFoundError(MCPXError):
    """资源不存在错误。"""

    def __init__(self, server_name: str, uri: str) -> None:
        self.server_name = server_name
        self.uri = uri
        super().__init__(
            f"Resource '{uri}' not found on server '{server_name}'", "RESOURCE_NOT_FOUND"
        )


class ExecutionError(MCPXError):
    """工具执行错误。"""

    def __init__(self, server_name: str, tool_name: str, error: str) -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        super().__init__(f"Error executing '{server_name}.{tool_name}': {error}", "EXECUTION_ERROR")
