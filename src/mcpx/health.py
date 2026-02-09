"""Health check and heartbeat monitoring for MCP servers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

__all__ = ["ServerHealth", "HealthStatus", "HealthChecker"]


class ServerHealth(BaseModel):
    """Health status of a single MCP server."""

    server_name: str
    status: str = "unknown"  # "healthy", "unhealthy", "unknown"
    last_check: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    last_success: datetime | None = None


class HealthStatus(BaseModel):
    """Overall health status of all servers."""

    servers: dict[str, ServerHealth] = Field(default_factory=dict)
    total_healthy: int = 0
    total_unhealthy: int = 0
    total_unknown: int = 0

    def update_server(self, name: str, is_healthy: bool, error: str | None = None) -> None:
        """Update health status for a server."""
        now = datetime.now()

        if name not in self.servers:
            self.servers[name] = ServerHealth(server_name=name)

        server = self.servers[name]

        if is_healthy:
            server.status = "healthy"
            server.last_check = now
            server.last_success = now
            server.consecutive_failures = 0
            server.last_error = None
        else:
            server.status = "unhealthy"
            server.last_check = now
            server.consecutive_failures += 1
            server.last_error = error or "Unknown error"

        self._recalculate()

    def _recalculate(self) -> None:
        """Recalculate totals."""
        self.total_healthy = sum(1 for s in self.servers.values() if s.status == "healthy")
        self.total_unhealthy = sum(1 for s in self.servers.values() if s.status == "unhealthy")
        self.total_unknown = sum(1 for s in self.servers.values() if s.status == "unknown")

    def get_unhealthy_servers(self) -> list[str]:
        """Get list of unhealthy server names."""
        return [name for name, server in self.servers.items() if server.status == "unhealthy"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": {
                "total": len(self.servers),
                "healthy": self.total_healthy,
                "unhealthy": self.total_unhealthy,
                "unknown": self.total_unknown,
            },
            "servers": {
                name: {
                    "status": server.status,
                    "last_check": server.last_check.isoformat() if server.last_check else None,
                    "last_success": server.last_success.isoformat()
                    if server.last_success
                    else None,
                    "consecutive_failures": server.consecutive_failures,
                    "last_error": server.last_error,
                }
                for name, server in self.servers.items()
            },
        }


class HealthChecker:
    """Health checker for MCP server connections.

    Periodically checks server health by calling a lightweight tool or ping.
    Runs as a background task.
    """

    def __init__(
        self,
        check_interval: int = 30,  # seconds
        check_timeout: int = 5,  # seconds
        failure_threshold: int = 2,  # consecutive failures before marking unhealthy
    ) -> None:
        """Initialize health checker.

        Args:
            check_interval: Seconds between health checks
            check_timeout: Timeout for each health check
            failure_threshold: Consecutive failures before marking server as unhealthy
        """
        self._check_interval = check_interval
        self._check_timeout = check_timeout
        self._failure_threshold = failure_threshold
        self._status = HealthStatus()
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._get_client_callback: Any | None = None  # Callback to get client from factory

    def set_session_callback(self, callback: Any) -> None:
        """Set callback to get client for health checking.

        Args:
            callback: Async callable that takes server_name and returns a new client or None
        """
        self._get_client_callback = callback

    async def check_server(self, server_name: str) -> bool:
        """Check health of a single server.

        Creates a temporary session using the client factory and closes it
        afterwards using async with pattern.

        Args:
            server_name: Name of the server to check

        Returns:
            True if server is healthy, False otherwise
        """
        if self._get_client_callback is None:
            logger.warning("Client callback not set, skipping health check")
            return False

        try:
            client = await self._get_client_callback(server_name)
            if client is None:
                self._status.update_server(server_name, False, "No client factory")
                return False

            # Use async with to ensure proper cleanup
            async with client:
                # Try to ping the server
                if hasattr(client, "ping"):
                    await asyncio.wait_for(client.ping(), timeout=self._check_timeout)
                else:
                    # Fallback: try to list tools (lightweight operation)
                    await asyncio.wait_for(client.list_tools(), timeout=self._check_timeout)

            self._status.update_server(server_name, True)
            logger.debug(f"Health check passed for '{server_name}'")
            return True

        except asyncio.TimeoutError:
            self._status.update_server(server_name, False, f"Timeout after {self._check_timeout}s")
            logger.warning(f"Health check timeout for '{server_name}'")
            return False
        except Exception as e:
            self._status.update_server(server_name, False, str(e))
            logger.warning(f"Health check failed for '{server_name}': {e}")
            return False

    async def check_all_servers(self, server_names: list[str]) -> None:
        """Check health of all servers.

        Args:
            server_names: List of server names to check
        """
        if not server_names:
            return

        # Check servers concurrently
        tasks = [self.check_server(name) for name in server_names]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _health_check_loop(self) -> None:
        """Background loop for periodic health checks."""
        logger.info(
            f"Health check loop started (interval: {self._check_interval}s, "
            f"timeout: {self._check_timeout}s)"
        )

        while self._running:
            try:
                # Get current server list
                server_names = list(self._status.servers.keys())

                if server_names:
                    logger.debug(f"Running health check for {len(server_names)} server(s)")
                    await self.check_all_servers(server_names)

                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self._check_interval)

    async def start(self, server_names: list[str]) -> None:
        """Start the health checker.

        Args:
            server_names: Initial list of servers to monitor
        """
        if self._running:
            logger.warning("Health checker already running")
            return

        self._running = True

        # Initialize server statuses
        for name in server_names:
            if name not in self._status.servers:
                self._status.servers[name] = ServerHealth(server_name=name, status="unknown")

        # Start background task
        self._task = asyncio.create_task(self._health_check_loop())

        # Do initial health check
        await self.check_all_servers(server_names)

        logger.info(f"Health checker started for {len(server_names)} server(s)")

    async def stop(self) -> None:
        """Stop the health checker."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Health checker stopped")

    @property
    def status(self) -> HealthStatus:
        """Get current health status."""
        return self._status

    @property
    def is_running(self) -> bool:
        """Check if health checker is running."""
        return self._running

    def get_server_health(self, server_name: str) -> ServerHealth | None:
        """Get health status for a specific server."""
        return self._status.servers.get(server_name)

    def is_server_healthy(self, server_name: str) -> bool:
        """Check if a specific server is healthy."""
        server = self.get_server_health(server_name)
        return server is not None and server.status == "healthy"
