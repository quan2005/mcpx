"""配置管理器 - 封装配置读写和状态管理。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from mcpx.config import McpServerConfig, ProxyConfig

logger = logging.getLogger(__name__)

__all__ = ["ConfigManager"]


class ConfigManager:
    """配置管理器，封装配置读写和状态管理。

    支持服务器和工具的启用/禁用状态管理，配置持久化和热重载。
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """初始化配置管理器。

        Args:
            config_path: 配置文件路径，None 则使用空配置
        """
        self._config_path = config_path
        self._config = ProxyConfig()
        self._modified = False

    @classmethod
    def from_file(cls, config_path: Path) -> "ConfigManager":
        """从文件创建配置管理器。

        Args:
            config_path: 配置文件路径

        Returns:
            配置管理器实例
        """
        manager = cls(config_path)
        return manager

    async def load(self) -> None:
        """从文件加载配置。"""
        if self._config_path is None or not self._config_path.exists():
            self._config = ProxyConfig()
            return

        try:
            with open(self._config_path, encoding="utf-8") as f:
                data = json.load(f)
            self._config = ProxyConfig(**data)
            self._modified = False
            logger.info(f"Loaded config from {self._config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    async def save(self) -> None:
        """保存配置到文件。"""
        if self._config_path is None:
            raise ValueError("Config path not set")

        try:
            # 序列化为 JSON
            data = self._config.model_dump()
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._modified = False
            logger.info(f"Saved config to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise

    @property
    def config(self) -> ProxyConfig:
        """获取当前配置。"""
        return self._config

    @property
    def config_path(self) -> Path | None:
        """获取配置文件路径。"""
        return self._config_path

    @property
    def is_modified(self) -> bool:
        """检查配置是否被修改但未保存。"""
        return self._modified

    def get_server(self, name: str) -> McpServerConfig | None:
        """获取服务器配置。

        Args:
            name: 服务器名称

        Returns:
            服务器配置或 None
        """
        return self._config.mcpServers.get(name)

    def add_server(self, name: str, config: McpServerConfig) -> None:
        """添加服务器配置。

        Args:
            name: 服务器名称
            config: 服务器配置
        """
        self._config.mcpServers[name] = config
        self._modified = True

    def remove_server(self, name: str) -> bool:
        """移除服务器配置。

        Args:
            name: 服务器名称

        Returns:
            是否成功移除
        """
        if name in self._config.mcpServers:
            del self._config.mcpServers[name]
            self._modified = True
            return True
        return False

    # 服务器状态管理

    def set_server_enabled(self, name: str, enabled: bool) -> bool:
        """设置服务器启用状态。

        Args:
            name: 服务器名称
            enabled: 是否启用

        Returns:
            是否成功设置
        """
        server = self._config.mcpServers.get(name)
        if server is None:
            return False
        if server.enabled != enabled:
            server.enabled = enabled
            self._modified = True
        return True

    def is_server_enabled(self, name: str) -> bool:
        """检查服务器是否启用。

        Args:
            name: 服务器名称

        Returns:
            是否启用
        """
        server = self._config.mcpServers.get(name)
        return server.enabled if server else False

    def get_enabled_servers(self) -> dict[str, McpServerConfig]:
        """获取所有启用的服务器。

        Returns:
            启用的服务器配置字典
        """
        return {name: config for name, config in self._config.mcpServers.items() if config.enabled}

    def get_disabled_servers(self) -> dict[str, McpServerConfig]:
        """获取所有禁用的服务器。

        Returns:
            禁用的服务器配置字典
        """
        return {
            name: config for name, config in self._config.mcpServers.items() if not config.enabled
        }

    # 工具状态管理

    def is_tool_disabled(self, tool_key: str) -> bool:
        """检查工具是否被禁用。

        Args:
            tool_key: 工具标识，格式为 "server.tool"

        Returns:
            是否被禁用
        """
        return tool_key in self._config.disabled_tools

    def is_tool_enabled(self, server_name: str, tool_name: str) -> bool:
        """检查工具是否启用。

        Args:
            server_name: 服务器名称
            tool_name: 工具名称

        Returns:
            是否启用
        """
        tool_key = f"{server_name}.{tool_name}"
        return tool_key not in self._config.disabled_tools

    def disable_tool(self, tool_key: str) -> None:
        """禁用工具。

        Args:
            tool_key: 工具标识，格式为 "server.tool"
        """
        if tool_key not in self._config.disabled_tools:
            self._config.disabled_tools.append(tool_key)
            self._modified = True

    def enable_tool(self, tool_key: str) -> None:
        """启用工具。

        Args:
            tool_key: 工具标识，格式为 "server.tool"
        """
        if tool_key in self._config.disabled_tools:
            self._config.disabled_tools.remove(tool_key)
            self._modified = True

    def set_tool_enabled(self, server_name: str, tool_name: str, enabled: bool) -> None:
        """设置工具启用状态。

        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            enabled: 是否启用
        """
        tool_key = f"{server_name}.{tool_name}"
        if enabled:
            self.enable_tool(tool_key)
        else:
            self.disable_tool(tool_key)

    def get_disabled_tools(self) -> list[str]:
        """获取所有禁用的工具列表。

        Returns:
            禁用的工具标识列表
        """
        return self._config.disabled_tools.copy()

    def get_server_disabled_tools(self, server_name: str) -> list[str]:
        """获取指定服务器禁用的工具列表。

        Args:
            server_name: 服务器名称

        Returns:
            禁用的工具名称列表
        """
        return [
            tool_key.split(".", 1)[1]
            for tool_key in self._config.disabled_tools
            if tool_key.startswith(f"{server_name}.")
        ]

    # 配置更新

    def update_config(self, updates: dict[str, Any]) -> None:
        """批量更新配置。

        Args:
            updates: 更新字典
        """
        # 更新顶层字段
        for key, value in updates.items():
            if key == "mcpServers":
                # 服务器配置需要特殊处理
                continue
            if key == "disabled_tools":
                self._config.disabled_tools = value
                self._modified = True
            elif hasattr(self._config, key):
                setattr(self._config, key, value)
                self._modified = True

        # 处理服务器配置更新
        if "mcpServers" in updates:
            new_servers = updates["mcpServers"]

            # 删除不在新配置中的服务器
            servers_to_remove = [
                name for name in self._config.mcpServers if name not in new_servers
            ]
            for name in servers_to_remove:
                del self._config.mcpServers[name]

            # 添加或更新服务器
            for name, config_data in new_servers.items():
                if name in self._config.mcpServers:
                    existing = self._config.mcpServers[name]
                    # 更新其他字段但保留 enabled
                    new_config = McpServerConfig(**config_data)
                    new_config.enabled = existing.enabled
                    self._config.mcpServers[name] = new_config
                else:
                    self._config.mcpServers[name] = McpServerConfig(**config_data)
            self._modified = True

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。

        Returns:
            配置字典
        """
        return self._config.model_dump()
