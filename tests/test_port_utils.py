"""Tests for port utilities."""

from __future__ import annotations

import socket

import pytest

from mcpx.port_utils import find_available_port


def test_find_available_port_with_free_port():
    """Test finding an available port when the requested port is free."""
    # Use a high port number that's unlikely to be in use
    port = find_available_port(45123)
    assert port == 45123


def test_find_available_port_with_occupied_port():
    """Test finding an available port when the requested port is occupied."""
    # Find a free port and occupy it
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    occupied_port = sock.getsockname()[1]

    try:
        # The function should find the next available port
        available_port = find_available_port(occupied_port)
        assert available_port > occupied_port
        assert available_port <= occupied_port + 100  # Reasonable upper bound
    finally:
        sock.close()


def test_find_available_port_with_multiple_occupied_ports():
    """Test finding an available port when multiple consecutive ports are occupied."""
    # Occupy two consecutive ports
    socks = []
    occupied_ports = []

    for _ in range(3):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        occupied_port = sock.getsockname()[1]
        socks.append(sock)
        occupied_ports.append(occupied_port)

    try:
        # Start from the first occupied port
        # The function should find a port beyond all occupied ones
        available_port = find_available_port(min(occupied_ports))
        assert available_port not in occupied_ports
        # Should be at or beyond the highest occupied port
        assert available_port >= min(occupied_ports)
    finally:
        for sock in socks:
            sock.close()


def test_find_available_port_with_max_attempts():
    """Test that the function raises an error when max_attempts is exceeded."""
    # Occupy 100 ports starting from a high number
    start_port = 45000
    socks = []

    for _ in range(110):  # More than the default max_attempts (100)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", start_port))
            socks.append(sock)
            start_port += 1
        except OSError:
            break

    try:
        # Should raise an error when no port is available
        with pytest.raises(OSError, match="No available port found"):
            find_available_port(socks[0].getsockname()[1], max_attempts=100)
    finally:
        for sock in socks:
            sock.close()


def test_find_available_port_specific_host():
    """Test finding a port on a specific host."""
    port = find_available_port(45124, host="127.0.0.1")
    assert port == 45124
