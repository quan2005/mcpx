"""Port utilities for mcpx-toolkit."""

from __future__ import annotations

import socket

__all__ = ["find_available_port"]


def _is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a port is currently in use.

    Args:
        port: The port to check
        host: The host to check (default: 0.0.0.0)

    Returns:
        True if the port is in use, False otherwise
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Don't use SO_REUSEADDR - we want to detect if the port is truly in use
    try:
        sock.bind((host, port))
        sock.close()
        return False
    except OSError:
        sock.close()
        return True


def find_available_port(
    start_port: int,
    host: str = "0.0.0.0",
    max_attempts: int = 100,
) -> int:
    """Find an available port starting from the specified port.

    Args:
        start_port: The port to start checking from
        host: The host to bind to (default: 0.0.0.0)
        max_attempts: Maximum number of ports to try (default: 100)

    Returns:
        An available port number

    Raises:
        OSError: If no available port is found within max_attempts
    """
    for offset in range(max_attempts):
        port = start_port + offset
        if not _is_port_in_use(port, host):
            return port

    raise OSError(
        f"No available port found starting from {start_port} (tried {max_attempts} ports)"
    )
