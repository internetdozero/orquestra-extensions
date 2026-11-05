"""Granular MCP server inspection, diagnostics, protocol testing, and dynamic invocation."""

from __future__ import annotations

from typing import Any

from . import bridge


def get_mcp_status() -> dict[str, Any]:
    """Return overall MCP catalog status, counts, and per-harness projection summary."""
    return bridge.mcp_status()


def inspect_mcp(mcp_id: str, reveal: bool = False) -> dict[str, Any]:
    """Inspect an MCP server configuration, env vars, headers, and scopes."""
    clean_id = (mcp_id or "").strip()
    if not clean_id:
        raise ValueError("mcp_id must not be empty")
    return bridge.mcp_inspect(clean_id, reveal=reveal)


def test_mcp_connection(mcp_id: str, timeout_ms: int = 5000) -> dict[str, Any]:
    """Ping an MCP server, verifying transport and protocol initialization handshake."""
    clean_id = (mcp_id or "").strip()
    if not clean_id:
        raise ValueError("mcp_id must not be empty")
    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be positive")
    return bridge.mcp_test_connection(clean_id, timeout_ms=timeout_ms)


def list_mcp_tools(mcp_id: str, timeout_ms: int = 5000) -> dict[str, Any]:
    """Query an MCP server for its exposed tool declarations and parameter schemas."""
    clean_id = (mcp_id or "").strip()
    if not clean_id:
        raise ValueError("mcp_id must not be empty")
    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be positive")
    return bridge.mcp_tools_list(clean_id, timeout_ms=timeout_ms)


def call_mcp_tool(
    mcp_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    timeout_ms: int = 15000,
) -> dict[str, Any]:
    """Dynamically execute a tool on an MCP server without mounting it to agent context."""
    clean_id = (mcp_id or "").strip()
    if not clean_id:
        raise ValueError("mcp_id must not be empty")
    clean_tool = (tool_name or "").strip()
    if not clean_tool:
        raise ValueError("tool_name must not be empty")
    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be positive")
    if arguments is not None and not isinstance(arguments, dict):
        raise ValueError("arguments must be a dictionary or null")
    return bridge.mcp_call_tool(clean_id, clean_tool, args=arguments, timeout_ms=timeout_ms)


def list_harness_targets() -> list[dict[str, Any]]:
    """List harness configuration targets (Claude, Codex, OpenCode, Cursor, etc.)."""
    return bridge.mcp_targets()
