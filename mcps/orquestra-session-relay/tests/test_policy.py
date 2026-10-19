"""Pinned sessions: sidecar persistence, retention safety and MCP tools."""

from __future__ import annotations

import asyncio
import json

from builders import make_codex
from session_relay import policy
from session_relay.policy import policy_path
from session_relay.server import server


def _call(name, arguments):
    return asyncio.run(server.call_tool(name, arguments))


def test_pin_unpin_roundtrip(relay_home):
    pinned = policy.pin_session("claude", "abc", label="Keep me")
    assert pinned == {"harness": "claude", "sessionId": "abc",
                      "pinned": True, "label": "Keep me"}
    assert policy.get_pins() == {("claude", "abc"): "Keep me"}

    repinned = policy.pin_session("claude", "abc", label="New label")
    assert repinned["label"] == "New label"
    assert len(policy.list_pins()) == 1

    unpinned = policy.unpin_session("claude", "abc")
    assert unpinned == {"harness": "claude", "sessionId": "abc", "pinned": False}
    assert policy.get_pins() == {}
    # Unpinning twice is friendly, not an error.
    assert policy.unpin_session("claude", "abc")["pinned"] is False


def test_empty_label_is_stored_as_none(relay_home):
    policy.pin_session("codex", "t1", label="   ")
    assert policy.get_pins() == {("codex", "t1"): None}
    assert policy.list_pins()[0]["label"] is None


def test_retention_half_survives_pin_writes(relay_home):
    path = policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "pinnedSessions": [],
        "retention": {"defaultTtlDays": 15, "custom": True},
    }))
    policy.pin_session("grok", "g1")
    doc = json.loads(path.read_text())
    assert doc["retention"] == {"defaultTtlDays": 15, "custom": True}
    assert [pin["sessionId"] for pin in doc["pinnedSessions"]] == ["g1"]


def test_corrupt_or_missing_policy_is_empty(relay_home):
    assert policy.get_pins() == {}
    assert policy.list_pins() == []
    path = policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json{{{")
    assert policy.get_pins() == {}
    assert policy.list_pins() == []


def test_pin_tools_and_decorated_listing(relay_home):
    make_codex(
        relay_home,
        [{
            "id": "thread-pin",
            "cwd": "/work/proj",
            "turns": [{"turn_id": "turn-1", "started_at": 1_790_000_010}],
            "items": [{
                "type": "userMessage",
                "ms": 1_790_000_000_000,
                "json": {"type": "userMessage",
                         "content": [{"type": "text", "text": "Pin this work"}]},
            }],
        }],
    )
    pinned = _call("pin_session", {
        "harness": "codex", "session_id": "thread-pin", "label": "Release",
    })
    assert pinned.structured_content["pinned"] is True

    listed = _call("list_recent_sessions", {"harness": "codex"})
    sessions = listed.structured_content["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["is_pinned"] is True
    assert sessions[0]["pin_label"] == "Release"

    pins = _call("list_pinned_sessions", {})
    assert pins.structured_content["count"] == 1
    assert pins.structured_content["pins"][0]["sessionId"] == "thread-pin"

    unpinned = _call("unpin_session", {
        "harness": "codex", "session_id": "thread-pin",
    })
    assert unpinned.structured_content["pinned"] is False
    relisted = _call("list_recent_sessions", {"harness": "codex"})
    assert relisted.structured_content["sessions"][0]["is_pinned"] is False


def test_pin_tools_reject_empty_ids(relay_home):
    bad = _call("pin_session", {"harness": "codex", "session_id": "  "})
    assert bad.structured_content["pinned"] is False
    assert "error" in bad.structured_content
