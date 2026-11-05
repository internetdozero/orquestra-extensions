"""Unit tests for granular MCP management and dynamic tool invocation."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from orquestra_core import bridge, mcp_control, server


def _call(name: str, **arguments: Any) -> Any:
    return asyncio.run(server.server.call_tool(name, arguments))


def test_mcp_control_validation_errors() -> None:
    with pytest.raises(ValueError, match="mcp_id must not be empty"):
        mcp_control.inspect_mcp("")

    with pytest.raises(ValueError, match="timeout_ms must be positive"):
        mcp_control.test_mcp_connection("svc", timeout_ms=0)

    with pytest.raises(ValueError, match="tool_name must not be empty"):
        mcp_control.call_mcp_tool("svc", "")

    with pytest.raises(ValueError, match="arguments must be a dictionary"):
        mcp_control.call_mcp_tool("svc", "do_thing", arguments="not-a-dict")  # type: ignore


@patch("orquestra_core.bridge.run")
def test_mcp_status(mock_run: MagicMock) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        '{"totalServers": 3, "officialServers": 2, "customServers": 1, '
        '"globallyActive": 2, "installedTargets": 4, "recognizedTargets": 6, '
        '"syncStatus": "All configs in sync", "perHarnessActive": {"claude": 2}}'
    )

    result = _call("orquestra_mcp_status")
    assert result.is_error is False
    assert result.structured_content["totalServers"] == 3
    assert result.structured_content["installedTargets"] == 4
    mock_run.assert_called_once_with("mcp", "status", "--json")


@patch("orquestra_core.bridge.run")
def test_mcp_inspect(mock_run: MagicMock) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        '{"id": "github", "name": "GitHub MCP", "official": true, '
        '"command": "node", "globalEnabled": true, "env": {"TOKEN": "****"}}'
    )

    result = _call("orquestra_inspect_mcp", mcp_id="github", reveal=False)
    assert result.is_error is False
    assert result.structured_content["id"] == "github"
    mock_run.assert_called_once_with("mcp", "inspect", "github", "--json")

    mock_run.reset_mock()
    _call("orquestra_inspect_mcp", mcp_id="github", reveal=True)
    mock_run.assert_called_once_with("mcp", "inspect", "github", "--json", "--reveal")


@patch("orquestra_core.bridge.run")
def test_mcp_test_connection(mock_run: MagicMock) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        '{"id": "cloudflare", "protocolVersion": "2024-11-05", '
        '"serverImplementation": "cloudflare-mcp v1.0", "roundtripLatencyMs": 42}'
    )

    result = _call("orquestra_test_mcp_connection", mcp_id="cloudflare", timeout_ms=3000)
    assert result.is_error is False
    assert result.structured_content["roundtripLatencyMs"] == 42
    mock_run.assert_called_once_with(
        "mcp", "test-connection", "cloudflare", "--timeout", "3000", "--json"
    )


@patch("orquestra_core.bridge.run")
def test_mcp_tools_list(mock_run: MagicMock) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        '{"id": "cloudflare", "tools": [{"name": "cf_dns_list", "description": "List DNS records"}]}'
    )

    result = _call("orquestra_list_mcp_tools", mcp_id="cloudflare")
    assert result.is_error is False
    assert len(result.structured_content["tools"]) == 1
    assert result.structured_content["tools"][0]["name"] == "cf_dns_list"
    mock_run.assert_called_once_with(
        "mcp", "tools-list", "cloudflare", "--timeout", "5000", "--json"
    )


@patch("orquestra_core.bridge.run")
def test_mcp_call_tool(mock_run: MagicMock) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        '{"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "ok"}]}}'
    )

    result = _call(
        "orquestra_call_mcp_tool",
        mcp_id="cloudflare",
        tool_name="cf_dns_list",
        arguments={"zone_id": "xyz"},
        timeout_ms=10000,
    )
    assert result.is_error is False
    assert result.structured_content["result"]["content"][0]["text"] == "ok"
    mock_run.assert_called_once_with(
        "mcp",
        "call-tool",
        "cloudflare",
        "cf_dns_list",
        "--timeout",
        "10000",
        "--json",
        "--args",
        '{"zone_id": "xyz"}',
    )


@patch("orquestra_core.bridge.run")
def test_mcp_targets(mock_run: MagicMock) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        '[{"id": "claude", "installed": true, "configPath": "/home/system/.claude/config.json"}]'
    )

    result = _call("orquestra_list_harness_targets")
    assert result.is_error is False
    rows = result.structured_content
    if isinstance(rows, dict) and "result" in rows:
        rows = rows["result"]
    assert rows[0]["id"] == "claude"
    assert rows[0]["installed"] is True
    mock_run.assert_called_once_with("mcp", "targets", "--json")


def test_tool_error_mapping_on_empty_id() -> None:
    with pytest.raises(ToolError) as exc_info:
        _call("orquestra_inspect_mcp", mcp_id="")
    assert "ValueError: mcp_id must not be empty" in str(exc_info.value)
