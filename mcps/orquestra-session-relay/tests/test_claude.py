"""Claude adapter: JSONL transcript parsing, search and read-only access."""

from __future__ import annotations

import os

from builders import make_claude, snapshot
from session_relay.adapters.claude import ClaudeAdapter


def _records() -> list[dict]:
    return [
        {
            "type": "user",
            "cwd": "/work/orquestra",
            "timestamp": "2026-10-17T11:00:00.000Z",
            "message": {"role": "user", "content": "Refactor the tray menu"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-10-17T11:00:05.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I will edit the tray component."},
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "/work/tray.tsx"}},
                ],
            },
        },
        {
            "type": "user",
            "timestamp": "2026-10-17T11:00:09.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "is_error": True,
                        "content": "patch failed: context mismatch",
                    }
                ],
            },
        },
        {
            "type": "assistant",
            "timestamp": "2026-10-17T11:00:12.000Z",
            "message": {"role": "assistant", "content": "Need to retry with fresh context."},
        },
    ]


def _setup(home):
    newer = make_claude(home, "-work-orquestra", "session-new", _records())
    older = make_claude(
        home,
        "-work-orquestra",
        "session-old",
        [
            {
                "type": "user",
                "timestamp": "2026-10-16T09:00:00.000Z",
                "message": {"role": "user", "content": "Unrelated build question"},
            }
        ],
    )
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_700_000_100, 1_700_000_100))
    return newer, older


def test_lists_newest_sessions(relay_home):
    _setup(relay_home)
    sessions = ClaudeAdapter(relay_home).list_sessions(limit=5)
    assert [session.session_id for session in sessions] == ["session-new", "session-old"]
    newest = sessions[0]
    assert newest.title == "Refactor the tray menu"
    assert newest.turns_count == 1
    assert newest.project == "/work/orquestra"
    assert newest.updated_at == "2026-10-17T11:00:12.000Z"


def test_loads_tool_events_and_errors(relay_home):
    _setup(relay_home)
    detail = ClaudeAdapter(relay_home).load_session("latest")
    assert detail is not None
    roles = [event.role for event in detail.events]
    assert roles == ["user", "assistant", "tool", "tool", "assistant"]
    editor = next(event for event in detail.events if event.tool == "Edit")
    assert "tray.tsx" in editor.text
    failure = next(event for event in detail.events if event.error)
    assert "patch failed" in failure.text

    limited = ClaudeAdapter(relay_home).load_session("session-new", max_turns=1)
    assert limited is not None
    assert [event.role for event in limited.events][0] == "user"


def test_search_and_missing_session(relay_home):
    _setup(relay_home)
    adapter = ClaudeAdapter(relay_home)
    hits = adapter.search("tray")
    assert hits and hits[0].session_id == "session-new"
    assert adapter.search("unrelated")[0].session_id == "session-old"
    assert adapter.load_session("does-not-exist") is None


def test_transcripts_are_never_modified(relay_home):
    _setup(relay_home)
    before = snapshot(relay_home)
    adapter = ClaudeAdapter(relay_home)
    adapter.list_sessions()
    adapter.load_session("latest")
    adapter.search("tray")
    assert snapshot(relay_home) == before


def test_missing_store_is_friendly(relay_home):
    adapter = ClaudeAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
