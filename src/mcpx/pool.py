"""MCP 连接池实现。

提供连接复用，替代每次请求创建新会话的 Session Isolation 模式。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["ConnectionPool"]


class ConnectionPool:
    """MCP 客户端连接池。

    使用连接复用提升性能，同时通过上下文管理器确保连接正确释放。
    """

    def __init__(
        self,
        factory: Callable[[], Any],
        max_size: int = 10,
        name: str = "",
    ) -> None:
        """初始化连接池。

        Args:
            factory: 创建新客户端的工厂函数
            max_size: 连接池最大容量
            name: 连接池名称（用于日志）
        """
        self._factory = factory
        self._max_size = max_size
        self._name = name or "unnamed"
        self._available: asyncio.Queue[Any] = asyncio.Queue()
        self._in_use: set[Any] = set()
        self._lock = asyncio.Lock()
        self._closed = False

    @asynccontextmanager
    async def acquire(self) -> Any:
        """获取连接上下文管理器。

        使用示例:
            async with pool.acquire() as client:
                result = await client.call_tool(...)
        """
        client = await self._get_client()
        try:
            # 使用 async with 确保客户端正确初始化
            async with client:
                yield client
        finally:
            await self._release_client(client)

    async def _get_client(self) -> Any:
        """获取一个可用连接。"""
        if self._closed:
            raise RuntimeError(f"Connection pool '{self._name}' is closed")

        async with self._lock:
            # 优先从可用队列获取
            if not self._available.empty():
                client = await self._available.get()
                self._in_use.add(client)
                logger.debug(f"Pool '{self._name}': Reused connection ({len(self._in_use)} in use)")
                return client

            # 创建新连接
            client = self._factory()
            self._in_use.add(client)
            logger.debug(
                f"Pool '{self._name}': Created new connection ({len(self._in_use)} in use)"
            )
            return client

    async def _release_client(self, client: Any) -> None:
        """释放连接回池或关闭。"""
        async with self._lock:
            self._in_use.discard(client)

            if self._closed:
                # 池已关闭，直接关闭连接
                try:
                    await client.close()
                except Exception as e:
                    logger.debug(f"Error closing client: {e}")
                return

            # 如果池未满，放回可用队列
            if self._available.qsize() < self._max_size:
                await self._available.put(client)
                logger.debug(f"Pool '{self._name}': Connection returned to pool")
            else:
                # 池已满，关闭连接
                try:
                    await client.close()
                except Exception as e:
                    logger.debug(f"Error closing client: {e}")
                logger.debug(f"Pool '{self._name}': Connection closed (pool full)")

    async def close(self) -> None:
        """关闭连接池和所有连接。"""
        async with self._lock:
            if self._closed:
                return

            self._closed = True

            # 关闭所有可用连接
            while not self._available.empty():
                try:
                    client = await self._available.get()
                    await client.close()
                except Exception as e:
                    logger.debug(f"Error closing client: {e}")

            # 关闭所有在用连接（尽力而为）
            for client in list(self._in_use):
                try:
                    await client.close()
                except Exception as e:
                    logger.debug(f"Error closing in-use client: {e}")
            self._in_use.clear()

            logger.info(f"Pool '{self._name}': Closed")

    @property
    def size(self) -> int:
        """当前池中的连接数（可用 + 在用）。"""
        return self._available.qsize() + len(self._in_use)

    @property
    def available_count(self) -> int:
        """可用连接数。"""
        return self._available.qsize()

    @property
    def in_use_count(self) -> int:
        """在用连接数。"""
        return len(self._in_use)
