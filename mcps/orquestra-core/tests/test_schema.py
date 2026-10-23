"""Published enums and failures that name the cause, through the MCP tools."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, get_args

import pytest
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from orquestra_core.schema import HttpMethod
from orquestra_core.server import server


def _schema(name: str) -> dict[str, Any]:
    tools = asyncio.run(server.list_tools())
    return next(tool.input_schema for tool in tools if tool.name == name)


def _call(name: str, **arguments: Any) -> Any:
    return asyncio.run(server.call_tool(name, arguments))


def test_http_method_schema_publishes_the_enum() -> None:
    method = _schema("orquestra_vault_http")["properties"]["method"]
    assert method["enum"] == list(get_args(HttpMethod))


def test_invalid_http_method_names_the_options() -> None:
    with pytest.raises(ToolError) as caught:
        _call(
            "orquestra_vault_http",
            service_id="inception-labs",
            endpoint="https://api.example.com/ping",
            method="FETCH",
        )
    message = str(caught.value)
    assert "method" in message
    assert "'DELETE'" in message and "'OPTIONS'" in message


def test_missing_catalog_is_a_readable_tool_error(mock_home: Path) -> None:
    (mock_home / "mcps.json").unlink()

    with pytest.raises(ToolError) as caught:
        _call("orquestra_list_mcps")
    assert "catalog not found" in str(caught.value)


def test_unknown_scope_lists_the_projected_ones(mock_home: Path) -> None:
    with pytest.raises(ToolError) as caught:
        _call("orquestra_enable_skill", skill_id="alpha", scope="nope")
    message = str(caught.value)
    assert "unknown scope 'nope'" in message
    assert "global" in message and "codex" in message


def test_unknown_vault_service_keeps_the_binary_reason(mock_home: Path) -> None:
    with pytest.raises(ToolError) as caught:
        _call("orquestra_vault_exec", service_id="nope", command=["true"])
    assert "unknown vault service: nope" in str(caught.value)


def test_vault_tools_roundtrip_through_the_binary(mock_home: Path) -> None:
    import json

    services = _call("orquestra_vault_list")
    assert services.is_error is False
    rows = services.structured_content
    if isinstance(rows, dict):  # list results arrive wrapped in {"result": [...]}
        rows = rows["result"]
    assert [row["id"] for row in rows] == ["svc-a"]
    assert all("secret" not in json.dumps(row).lower() for row in rows)

    http = _call(
        "orquestra_vault_http",
        service_id="svc-a",
        endpoint="https://api.example.com/ping",
        method="GET",
    )
    assert http.is_error is False
    assert http.structured_content["status"] == 200

    executed = _call("orquestra_vault_exec", service_id="svc-a", command=["true"])
    assert executed.is_error is False
    assert executed.structured_content["code"] == 0


def test_vault_set_enabled_roundtrip(mock_home: Path) -> None:
    off = _call("orquestra_vault_set_enabled", service_id="svc-a", enabled=False)
    assert off.is_error is False
    assert off.structured_content["enabled"] is False

    on = _call("orquestra_vault_set_enabled", service_id="svc-a", enabled=True)
    assert on.is_error is False
    assert on.structured_content["enabled"] is True


def test_vault_set_enabled_rejects_unknown_service(mock_home: Path) -> None:
    with pytest.raises(ToolError) as caught:
        _call("orquestra_vault_set_enabled", service_id="nope", enabled=True)
    assert "unknown vault service: nope" in str(caught.value)


def test_vault_set_enabled_rejects_empty_id(mock_home: Path) -> None:
    with pytest.raises(ToolError) as caught:
        _call("orquestra_vault_set_enabled", service_id="  ", enabled=True)
    assert "must not be empty" in str(caught.value)


def test_bridge_refusal_keeps_its_reason(mock_home: Path) -> None:
    with pytest.raises(ToolError) as caught:
        _call("orquestra_apply_preset", preset_id="ghost")
    assert "ghost" in str(caught.value)


def test_unexpected_runtime_error_is_still_a_crash(mock_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from orquestra_core import skills

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("programmer bug")

    monkeypatch.setattr(skills, "enable_skill", broken)
    with pytest.raises(UnexpectedToolError) as caught:
        _call("orquestra_enable_skill", skill_id="alpha")
    assert "programmer bug" not in str(caught.value)


def test_list_tools_still_succeed_after_the_guard(mock_home: Path) -> None:
    presets = _call("orquestra_list_presets")
    assert presets.is_error is False
    rows = presets.structured_content
    if isinstance(rows, dict):  # list results arrive wrapped in {"result": [...]}
        rows = rows["result"]
    assert {"full-power"} <= {row["id"] for row in rows}
