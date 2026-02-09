"""MCPX 核心服务器管理类。

合并 Registry 和 Executor 功能，使用连接池管理 MCP 服务器连接。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import SSETransport, StdioTransport, StreamableHttpTransport
from fastmcp.mcp_config import infer_transport_type_from_url
from pydantic import BaseModel

from mcpx.compression import ToonCompressor
from mcpx.config import McpServerConfig, ProxyConfig
from mcpx.config_manager import ConfigManager
from mcpx.content import is_multimodal_content
from mcpx.errors import (
    ExecutionError,
    ResourceNotFoundError,
    ServerNotFoundError,
    ToolNotFoundError,
    ValidationError,
)
from mcpx.health import HealthChecker
from mcpx.pool import ConnectionPool

logger = logging.getLogger(__name__)

__all__ = ["ServerInfo", "ToolInfo", "ResourceInfo", "ServerManager"]


class ServerInfo(BaseModel):
    """MCP 服务器信息缓存。"""

    name: str  # 配置名称（用户定义）
    server_name: str  # 实际 MCP 服务器名称
    version: str
    instructions: str | None = None  # 服务器使用说明


class ToolInfo(BaseModel):
    """工具信息缓存。"""

    server_name: str
    name: str
    description: str
    input_schema: dict[str, Any]


class ResourceInfo(BaseModel):
    """资源信息缓存。"""

    server_name: str
    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None
    size: int | None = None


class ExecutionResult:
    """工具执行结果。"""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        raw_data: Any = None,
        error: str | None = None,
        compressed: bool = False,
    ):
        self.success = success
        self.data = data
        self.raw_data = raw_data
        self.error = error
        self.compressed = compressed


class ServerManager:
    """管理所有 MCP 服务器连接。

    使用连接池实现连接复用，合并 Registry 和 Executor 功能。
    支持增量启停服务器。
    """

    def __init__(self, config_or_manager: ProxyConfig | ConfigManager) -> None:
        """初始化服务器管理器。

        Args:
            config_or_manager: 代理配置或配置管理器
        """
        if isinstance(config_or_manager, ConfigManager):
            self._config_manager: ConfigManager | None = config_or_manager
            self._config = config_or_manager.config
        else:
            self._config_manager = None
            self._config = config_or_manager

        self._pools: dict[str, ConnectionPool] = {}
        self._tools: dict[str, ToolInfo] = {}
        self._resources: dict[str, ResourceInfo] = {}
        self._server_infos: dict[str, ServerInfo] = {}
        self._initialized = False

        # 初始化 TOON 压缩器
        self._compressor = ToonCompressor(
            enabled=self._config.toon_compression_enabled,
            min_size=self._config.toon_compression_min_size,
        )

        # 初始化健康检查器
        self._health_checker = HealthChecker(
            check_interval=self._config.health_check_interval,
            check_timeout=self._config.health_check_timeout,
            failure_threshold=self._config.health_check_failure_threshold,
        )
        self._health_checker.set_session_callback(self._get_client_for_health_check)

    def _create_client_factory(self, server_config: McpServerConfig) -> Any:
        """创建客户端工厂函数。

        Args:
            server_config: 服务器配置

        Returns:
            返回新 Client 实例的工厂函数
        """
        # 根据类型创建传输层
        if server_config.type == "http":
            assert server_config.url is not None, "HTTP type requires url"
            transport_type = infer_transport_type_from_url(server_config.url)

            if transport_type == "sse":
                transport: Any = SSETransport(
                    url=server_config.url,
                    headers=server_config.headers or {},
                )
            else:
                transport = StreamableHttpTransport(
                    url=server_config.url,
                    headers=server_config.headers or {},
                )
        else:
            assert server_config.command is not None, "stdio type requires command"
            transport = StdioTransport(
                command=server_config.command,
                args=server_config.args,
                env=server_config.env or {},
            )

        # 创建基础客户端（未连接）
        base_client = Client(transport, auto_initialize=True)

        # 工厂函数：每次返回新客户端
        def factory() -> Any:
            return base_client.new()

        return factory

    async def ensure_initialized(self) -> None:
        """确保管理器已初始化（懒加载）。"""
        if not self._initialized:
            await self.initialize()

    async def initialize(self) -> None:
        """初始化所有服务器连接池。

        创建连接池，预热连接并获取工具/资源列表。
        """
        if self._initialized:
            return

        for server_name, server_config in self._config.mcpServers.items():
            # 跳过禁用的服务器
            if not server_config.enabled:
                logger.info(f"Server '{server_name}' is disabled, skipping")
                continue

            try:
                # 验证配置
                server_config.validate_for_server(server_name)

                # 创建客户端工厂
                factory = self._create_client_factory(server_config)

                # 创建连接池
                pool = ConnectionPool(
                    factory=factory,
                    max_size=10,
                    name=server_name,
                )

                # 预热连接并获取工具/资源列表
                async with pool.acquire() as client:
                    # 缓存服务器信息
                    init_result = client.initialize_result
                    if init_result and init_result.serverInfo:
                        self._server_infos[server_name] = ServerInfo(
                            name=server_name,
                            server_name=init_result.serverInfo.name or server_name,
                            version=init_result.serverInfo.version or "unknown",
                            instructions=init_result.instructions,
                        )
                    else:
                        self._server_infos[server_name] = ServerInfo(
                            name=server_name,
                            server_name=server_name,
                            version="unknown",
                            instructions=None,
                        )

                    # 获取并缓存工具列表
                    tools = await client.list_tools()
                    logger.info(f"Server '{server_name}' has {len(tools)} tool(s)")

                    for tool in tools:
                        tool_key = f"{server_name}:{tool.name}"
                        self._tools[tool_key] = ToolInfo(
                            server_name=server_name,
                            name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema or {},
                        )

                    # 获取并缓存资源列表
                    try:
                        resources = await client.list_resources()
                        logger.info(f"Server '{server_name}' has {len(resources)} resource(s)")

                        for resource in resources:
                            resource_key = f"{server_name}:{resource.uri}"
                            self._resources[resource_key] = ResourceInfo(
                                server_name=server_name,
                                uri=str(resource.uri),
                                name=resource.name,
                                description=resource.description,
                                mime_type=resource.mimeType,
                                size=resource.size,
                            )
                    except Exception as e:
                        logger.warning(f"Failed to list resources from '{server_name}': {e}")

                # 保存连接池
                self._pools[server_name] = pool

            except Exception as e:
                logger.error(f"Failed to connect to server '{server_name}': {e}")

        self._initialized = True

        # 启动健康检查
        if self._config.health_check_enabled and self._pools:
            server_names = list(self._pools.keys())
            await self._health_checker.start(server_names)
            logger.info(f"Health checker started for {len(server_names)} server(s)")

    async def connect_server(self, name: str) -> bool:
        """增量启用并连接单个服务器。

        Args:
            name: 服务器名称

        Returns:
            是否成功连接
        """
        if name in self._pools:
            logger.warning(f"Server '{name}' already connected")
            return True

        server_config = self._config.mcpServers.get(name)
        if server_config is None:
            logger.error(f"Server '{name}' not found in config")
            return False

        # 如果服务器被禁用，不连接
        if not server_config.enabled:
            logger.info(f"Server '{name}' is disabled, skipping")
            return False

        try:
            # 验证配置
            server_config.validate_for_server(name)

            # 创建客户端工厂
            factory = self._create_client_factory(server_config)

            # 创建连接池
            pool = ConnectionPool(
                factory=factory,
                max_size=10,
                name=name,
            )

            # 预热连接并获取工具/资源列表
            async with pool.acquire() as client:
                # 缓存服务器信息
                init_result = client.initialize_result
                if init_result and init_result.serverInfo:
                    self._server_infos[name] = ServerInfo(
                        name=name,
                        server_name=init_result.serverInfo.name or name,
                        version=init_result.serverInfo.version or "unknown",
                        instructions=init_result.instructions,
                    )
                else:
                    self._server_infos[name] = ServerInfo(
                        name=name,
                        server_name=name,
                        version="unknown",
                        instructions=None,
                    )

                # 获取并缓存工具列表
                tools = await client.list_tools()
                logger.info(f"Server '{name}' has {len(tools)} tool(s)")

                for tool in tools:
                    tool_key = f"{name}:{tool.name}"
                    self._tools[tool_key] = ToolInfo(
                        server_name=name,
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.inputSchema or {},
                    )

                # 获取并缓存资源列表
                try:
                    resources = await client.list_resources()
                    logger.info(f"Server '{name}' has {len(resources)} resource(s)")

                    for resource in resources:
                        resource_key = f"{name}:{resource.uri}"
                        self._resources[resource_key] = ResourceInfo(
                            server_name=name,
                            uri=str(resource.uri),
                            name=resource.name,
                            description=resource.description,
                            mime_type=resource.mimeType,
                            size=resource.size,
                        )
                except Exception as e:
                    logger.warning(f"Failed to list resources from '{name}': {e}")

            # 保存连接池
            self._pools[name] = pool

            # 添加到健康检查器
            self._health_checker.add_server(name)

            logger.info(f"Successfully connected to server '{name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to server '{name}': {e}")
            return False

    async def disconnect_server(self, name: str) -> bool:
        """增量禁用并断开单个服务器。

        Args:
            name: 服务器名称

        Returns:
            是否成功断开
        """
        if name not in self._pools:
            logger.warning(f"Server '{name}' not connected")
            return False

        try:
            # 从健康检查器移除
            self._health_checker.remove_server(name)

            # 关闭连接池
            pool = self._pools.pop(name)
            await pool.close()

            # 清理工具缓存
            tools_to_remove = [key for key in self._tools.keys() if key.startswith(f"{name}:")]
            for key in tools_to_remove:
                del self._tools[key]

            # 清理资源缓存
            resources_to_remove = [
                key for key in self._resources.keys() if key.startswith(f"{name}:")
            ]
            for key in resources_to_remove:
                del self._resources[key]

            # 清理服务器信息
            if name in self._server_infos:
                del self._server_infos[name]

            logger.info(f"Successfully disconnected from server '{name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to disconnect from server '{name}': {e}")
            return False

    async def reload(self) -> None:
        """全量重载：关闭所有连接并重新初始化。"""
        await self.close()
        await self.initialize()
        logger.info("Server manager reloaded")

    def is_tool_enabled(self, server_name: str, tool_name: str) -> bool:
        """检查工具是否启用。

        Args:
            server_name: 服务器名称
            tool_name: 工具名称

        Returns:
            是否启用
        """
        if self._config_manager:
            return self._config_manager.is_tool_enabled(server_name, tool_name)
        # 如果没有配置管理器，检查本地配置
        tool_key = f"{server_name}.{tool_name}"
        return tool_key not in self._config.disabled_tools

    def set_tool_enabled(self, server_name: str, tool_name: str, enabled: bool) -> None:
        """设置工具启用状态。

        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            enabled: 是否启用
        """
        if self._config_manager:
            self._config_manager.set_tool_enabled(server_name, tool_name, enabled)
        else:
            tool_key = f"{server_name}.{tool_name}"
            if enabled:
                if tool_key in self._config.disabled_tools:
                    self._config.disabled_tools.remove(tool_key)
            else:
                if tool_key not in self._config.disabled_tools:
                    self._config.disabled_tools.append(tool_key)

    @property
    def config_manager(self) -> ConfigManager | None:
        """获取配置管理器。"""
        return self._config_manager

    async def call(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> ExecutionResult:
        """执行工具调用。

        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            ExecutionResult 执行结果

        Raises:
            ServerNotFoundError: 服务器不存在
            ToolNotFoundError: 工具不存在
            ValidationError: 参数校验失败
            ExecutionError: 执行失败
        """
        # 确保已初始化
        await self.ensure_initialized()

        # 检查服务器
        pool = self._pools.get(server_name)
        if pool is None:
            available = self.list_servers()
            raise ServerNotFoundError(server_name, available)

        # 检查工具
        tool_key = f"{server_name}:{tool_name}"
        tool_info = self._tools.get(tool_key)
        if tool_info is None:
            available = [t.name for t in self.list_tools(server_name)]
            raise ToolNotFoundError(server_name, tool_name, available)

        # 校验参数
        self._validate_arguments(arguments, tool_info.input_schema)

        # 执行调用
        try:
            async with pool.acquire() as client:
                result = await client.call_tool(tool_name, arguments=arguments)

            # 提取数据
            data = self._extract_result_data(result)

            # TOON 压缩
            compressed_data, was_compressed = self._compressor.compress(data)

            return ExecutionResult(
                success=True,
                data=compressed_data,
                raw_data=data,
                compressed=was_compressed,
            )

        except Exception as e:
            logger.error(f"Error executing '{server_name}.{tool_name}': {e}")
            raise ExecutionError(server_name, tool_name, str(e))

    def _validate_arguments(self, arguments: dict[str, Any], input_schema: dict[str, Any]) -> None:
        """校验参数。

        Args:
            arguments: 参数字典
            input_schema: 输入 schema

        Raises:
            ValidationError: 校验失败
        """
        args = arguments or {}

        # 检查必填字段
        required = input_schema.get("required", [])
        if isinstance(required, list):
            for field in required:
                if field not in args:
                    raise ValidationError(f"Missing required argument: '{field}'", input_schema)

        # 检查未知参数
        properties = input_schema.get("properties", {})
        if isinstance(properties, dict):
            for key in args:
                if key not in properties:
                    available = list(properties.keys())
                    raise ValidationError(
                        f"Unknown argument: '{key}'. Available: {available}", input_schema
                    )

    def _extract_result_data(self, result: Any) -> Any:
        """从 CallToolResult 提取数据。

        Args:
            result: call_tool 返回结果

        Returns:
            提取的数据
        """
        # MCP 协议使用 content 属性
        if hasattr(result, "content"):
            content_list = result.content

            if not content_list:
                return None

            # 单项内容处理
            if len(content_list) == 1:
                first_item = content_list[0]

                # TextContent: 尝试解析 JSON
                if hasattr(first_item, "text"):
                    text = first_item.text
                    return self._unwrap_json_string(text)

                # 多模态内容：直接返回
                if is_multimodal_content(first_item):
                    return first_item

                # 其他类型：返回字典
                if hasattr(first_item, "model_dump"):
                    return first_item.model_dump()
                return str(first_item)

            # 多项内容处理
            has_multimodal = any(is_multimodal_content(item) for item in content_list)

            if has_multimodal:
                return list(content_list)

            # 纯文本内容
            texts = []
            for item in content_list:
                if hasattr(item, "text"):
                    texts.append(item.text)
                elif hasattr(item, "model_dump"):
                    texts.append(item.model_dump())
                else:
                    texts.append(str(item))
            return texts if len(texts) > 1 else (texts[0] if texts else None)

        # FastMCP 3.0+ 可能提供直接数据访问
        if hasattr(result, "data") and result.data is not None:
            return self._ensure_serializable(result.data)

        # Fallback
        if hasattr(result, "model_dump"):
            return result.model_dump()

        return str(result)

    def _unwrap_json_string(self, text: str) -> Any:
        """解析 JSON 字符串。

        处理双重编码的情况。
        """
        if not text:
            return text

        try:
            parsed = json.loads(text)
            # 检查双重编码
            if isinstance(parsed, str):
                try:
                    return json.loads(parsed)
                except (json.JSONDecodeError, TypeError):
                    return parsed
            return parsed
        except (json.JSONDecodeError, TypeError):
            return text

    def _ensure_serializable(self, data: Any) -> Any:
        """确保数据可 JSON 序列化。"""
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool)):
            return data
        if isinstance(data, (list, tuple)):
            return [self._ensure_serializable(item) for item in data]
        if isinstance(data, dict):
            return {k: self._ensure_serializable(v) for k, v in data.items()}
        if hasattr(data, "model_dump"):
            return data.model_dump()
        return str(data)

    async def read(self, server_name: str, uri: str) -> Any:
        """读取资源。

        Args:
            server_name: 服务器名称
            uri: 资源 URI

        Returns:
            资源内容

        Raises:
            ServerNotFoundError: 服务器不存在
            ResourceNotFoundError: 资源不存在
        """
        # 确保已初始化
        await self.ensure_initialized()

        pool = self._pools.get(server_name)
        if pool is None:
            available = self.list_servers()
            raise ServerNotFoundError(server_name, available)

        try:
            async with pool.acquire() as client:
                contents = await client.read_resource(uri)

            if contents is None or len(contents) == 0:
                raise ResourceNotFoundError(server_name, uri)

            return contents

        except Exception as e:
            if isinstance(e, ResourceNotFoundError):
                raise
            logger.error(f"Error reading resource '{uri}' from '{server_name}': {e}")
            raise ResourceNotFoundError(server_name, uri)

    def list_servers(self) -> list[str]:
        """列出所有服务器名称。"""
        return list(self._pools.keys())

    def has_server(self, server_name: str) -> bool:
        """检查服务器是否存在。"""
        return server_name in self._pools

    def list_tools(self, server_name: str) -> list[ToolInfo]:
        """列出指定服务器的所有工具。"""
        return [tool for tool in self._tools.values() if tool.server_name == server_name]

    def list_all_tools(self) -> list[ToolInfo]:
        """列出所有工具。"""
        return list(self._tools.values())

    def get_tool(self, server_name: str, tool_name: str) -> ToolInfo | None:
        """获取指定工具信息。"""
        tool_key = f"{server_name}:{tool_name}"
        return self._tools.get(tool_key)

    def list_resources(self, server_name: str) -> list[ResourceInfo]:
        """列出指定服务器的所有资源。"""
        return [r for r in self._resources.values() if r.server_name == server_name]

    def list_all_resources(self) -> list[ResourceInfo]:
        """列出所有资源。"""
        return list(self._resources.values())

    def get_tool_list_text(self) -> str:
        """生成纯文本工具列表（向后兼容）。

        Returns:
            按服务器分组的工具列表文本
        """
        if not self._tools:
            return "No tools available."

        lines = ["Available tools (use inspect with server_name to get details):"]
        for server_name in sorted(self._pools.keys()):
            lines.append(f"  Server: {server_name}")
            for tool in self.list_tools(server_name):
                desc = (
                    tool.description[:60] + "..."
                    if len(tool.description) > 60
                    else tool.description
                )
                lines.append(f"    - {tool.name}: {desc}")
        return "\n".join(lines)

    @property
    def tools(self) -> dict[str, ToolInfo]:
        """获取所有工具（向后兼容）。"""
        return self._tools.copy()

    def get_resource(self, server_name: str, uri: str) -> ResourceInfo | None:
        """获取指定资源信息。"""
        resource_key = f"{server_name}:{uri}"
        return self._resources.get(resource_key)

    def get_server_info(self, server_name: str) -> ServerInfo | None:
        """获取服务器信息。"""
        return self._server_infos.get(server_name)

    def get_health_status(self) -> Any:
        """获取健康状态。"""
        return self._health_checker.status

    def get_server_health(self, server_name: str) -> dict[str, Any] | None:
        """获取指定服务器的健康状态。"""
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
        """检查服务器是否健康。"""
        return self._health_checker.is_server_healthy(server_name)

    async def check_server_health(self, server_name: str) -> bool:
        """手动触发健康检查。"""
        return await self._health_checker.check_server(server_name)

    def get_client_factory(self, server_name: str) -> Any | None:
        """获取客户端工厂（向后兼容）。

        Args:
            server_name: 服务器名称

        Returns:
            客户端工厂函数或 None
        """
        pool = self._pools.get(server_name)
        if pool is None:
            return None

        # 返回池的工厂函数
        return pool._factory

    async def _get_client_for_health_check(self, server_name: str) -> Any | None:
        """为健康检查获取客户端。"""
        pool = self._pools.get(server_name)
        if pool is None:
            return None

        # 创建临时客户端（不在池中管理）
        try:
            async with pool.acquire() as client:
                # 返回一个新客户端用于健康检查
                # 注意：这里实际上需要返回一个可以 async with 的客户端
                # 由于 pool.acquire() 已经返回上下文管理器，我们需要调整
                return client
        except Exception:
            return None

    async def close(self) -> None:
        """关闭所有连接池。"""
        # 停止健康检查
        await self._health_checker.stop()

        # 关闭所有连接池
        for name, pool in self._pools.items():
            try:
                await pool.close()
            except Exception as e:
                logger.debug(f"Error closing pool '{name}': {e}")

        self._pools.clear()
        self._tools.clear()
        self._resources.clear()
        self._server_infos.clear()
        self._initialized = False
