"""Published harness vocabularies and failures that name the cause."""

from __future__ import annotations

import asyncio
from typing import Any, get_args

import pytest
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from session_relay import discovery, policy, server
from session_relay.adapters import ALIASES
from session_relay.schema import Harness


def _schema(name: str) -> dict[str, Any]:
    tools = asyncio.run(server.server.list_tools())
    return next(tool.input_schema for tool in tools if tool.name == name)


def _enum(prop: dict[str, Any]) -> list[str]:
    if "enum" in prop:
        return list(prop["enum"])
    for branch in prop.get("anyOf", []):
        if "enum" in branch:
            return list(branch["enum"])
    raise AssertionError(f"no enum in {prop}")


def _call(name: str, **arguments: Any) -> Any:
    return asyncio.run(server.server.call_tool(name, arguments))


def test_harness_literal_mirrors_registered_ids_and_aliases() -> None:
    accepted = set(discovery.KNOWN) | set(ALIASES)
    assert set(get_args(Harness)) == accepted


def test_every_harness_parameter_publishes_enum() -> None:
    for name in (
        "list_recent_sessions",
        "pin_session",
        "unpin_session",
        "inspect_session",
        "handoff_context",
        "search_sessions_history",
        "watch_active_agent",
        "tail_agent_activity",
        "audit_agent",
    ):
        schema = _schema(name)
        for parameter in ("harness", "source_harness", "exclude_harness"):
            if parameter in schema["properties"]:
                assert set(_enum(schema["properties"][parameter])) == set(get_args(Harness)), (name, parameter)


def test_invalid_harness_names_the_accepted_ids(relay_home) -> None:
    with pytest.raises(ToolError) as caught:
        _call("list_recent_sessions", harness="nope")
    message = str(caught.value)
    assert "harness" in message
    assert "'antigravity'" in message and "'opencode'" in message


def test_empty_pin_id_is_a_descriptive_tool_error(relay_home) -> None:
    with pytest.raises(ToolError) as caught:
        _call("pin_session", harness="codex", session_id=" ")
    assert "harness and session_id must be non-empty strings" in str(caught.value)


def test_pin_write_failure_is_actionable(monkeypatch: pytest.MonkeyPatch, relay_home) -> None:
    def denied(*args: Any, **kwargs: Any) -> None:
        raise PermissionError("policy path is read-only")

    monkeypatch.setattr(policy, "_write_doc", denied)
    with pytest.raises(ToolError) as caught:
        _call("pin_session", harness="codex", session_id="thread-1")
    assert "policy path is read-only" in str(caught.value)


def test_unexpected_runtime_error_is_still_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("programmer bug")

    monkeypatch.setattr(discovery, "recent_sessions", broken)
    with pytest.raises(UnexpectedToolError) as caught:
        _call("list_recent_sessions")
    assert "programmer bug" not in str(caught.value)


def test_unavailable_store_stays_a_friendly_result(relay_home) -> None:
    result = _call("inspect_session", harness="codex", session_id="missing")
    assert result.is_error is False
    assert "no OpenAI Codex session store" in result.structured_content["error"]
    assert result.structured_content["events"] == []
