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


def test_vault_http_publishes_optional_one_based_key_number() -> None:
    schema = _schema("orquestra_vault_http")
    prop = schema["properties"]["key_number"]
    type_names = (
        [prop.get("type")]
        if "type" in prop
        else [b.get("type") for b in prop.get("anyOf", [])]
    )
    assert "integer" in type_names
    assert "key_number" not in schema.get("required", [])


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
    assert rows[0]["activeKeyNumber"] == 1
    assert all("secret" not in json.dumps(row).lower() for row in rows)

    http = _call(
        "orquestra_vault_http",
        service_id="svc-a",
        endpoint="https://api.example.com/ping",
        method="GET",
        key_number=5,
    )
    assert http.is_error is False
    assert http.structured_content["status"] == 200
    assert http.structured_content["usedKeyNumber"] == 5

    executed = _call(
        "orquestra_vault_exec", service_id="svc-a", command=["true"], key_number=5
    )
    assert executed.is_error is False
    assert executed.structured_content["code"] == 0
    assert executed.structured_content["usedKeyNumber"] == 5

    # String form is shlex-split, never shelled: same argv shape reaches the binary.
    as_string = _call("orquestra_vault_exec", service_id="svc-a", command="true")
    assert as_string.is_error is False
    assert as_string.structured_content["code"] == 0
    assert as_string.structured_content["usedKeyNumber"] == 1


def test_vault_rejects_zero_or_non_integer_key_numbers() -> None:
    from orquestra_core import vault
    from orquestra_core.errors import VaultRequestError

    for value in (0, -1, True, "5"):
        with pytest.raises(VaultRequestError, match="key_number must be a positive 1-based integer"):
            vault._validate_key_number(value)  # type: ignore[arg-type]


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


def test_vault_set_enabled_rejects_non_bool(mock_home: Path) -> None:
    # The MCP framework coerces tool inputs to bool before the body runs,
    # so this guard only fires for direct library callers: exercise it there.
    from orquestra_core import vault
    from orquestra_core.errors import VaultRequestError

    with pytest.raises(VaultRequestError, match="must be true or false"):
        vault.set_service_enabled("svc-a", "yes")  # type: ignore[arg-type]


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


def test_granular_vault_tools_roundtrip(mock_home: Path) -> None:
    # inspect
    inspected = _call("orquestra_vault_inspect", service_id="svc-a")
    assert inspected.is_error is False
    assert inspected.structured_content["id"] == "svc-a"
    assert inspected.structured_content["activeKeyNumber"] == 1
    assert inspected.structured_content["tags"] == ["prod"]

    # rotate
    rotated = _call("orquestra_vault_rotate", service_id="svc-a", next_key=True, key_number=2)
    assert rotated.is_error is False
    assert rotated.structured_content["activeKeyNumber"] == 2

    # test
    tested = _call("orquestra_vault_test", service_id="svc-a", key_number=1)
    assert tested.is_error is False
    assert tested.structured_content["success"] is True
    assert tested.structured_content["health"] == "healthy"

    # presets
    presets = _call("orquestra_vault_presets")
    assert presets.is_error is False
    rows = presets.structured_content
    if isinstance(rows, dict) and "result" in rows:
        rows = rows["result"]
    assert any(p["id"] == "github" for p in rows)

    # audit
    audited = _call("orquestra_vault_audit")
    assert audited.is_error is False
    assert audited.structured_content["secure"] is True
    assert audited.structured_content["encrypted"] is True

    # http with key_tag
    http = _call(
        "orquestra_vault_http",
        service_id="svc-a",
        endpoint="https://api.example.com/ping",
        key_tag="prod",
    )
    assert http.is_error is False
    assert http.structured_content["status"] == 200
