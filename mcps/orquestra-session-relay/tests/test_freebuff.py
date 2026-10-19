"""Freebuff adapter: project chats, tool blocks and prompt-history fallback."""

from __future__ import annotations

import os

from builders import make_freebuff, make_freebuff_history, snapshot
from session_relay.adapters.freebuff import FreebuffAdapter

SESSION = "2026-10-17T10-00-00.000Z"


def _messages() -> list[dict]:
    return [
        {"id": "u1", "variant": "user", "content": "Make the deploy faster"},
        {
            "id": "a1",
            "variant": "ai",
            "content": "",
            "blocks": [
                {"type": "text", "text": "I will trim the build step."},
                {
                    "type": "tool",
                    "toolName": "write_file",
                    "input": {"path": "deploy.sh"},
                    "output": "updated deploy.sh",
                },
            ],
        },
    ]


def test_lists_chat_sessions(relay_home):
    path = make_freebuff(relay_home, "OrquestraAI", SESSION, _messages())
    os.utime(path, (1_700_000_100, 1_700_000_100))
    sessions = FreebuffAdapter(relay_home).list_sessions()
    assert len(sessions) == 1
    session = sessions[0]
    assert session.session_id == SESSION
    assert session.title == "Make the deploy faster"
    assert session.project == "OrquestraAI"
    assert session.turns_count == 1


def test_loads_tool_blocks_and_searches(relay_home):
    make_freebuff(relay_home, "OrquestraAI", SESSION, _messages())
    adapter = FreebuffAdapter(relay_home)
    detail = adapter.load_session("latest")
    assert detail is not None
    assert [event.role for event in detail.events] == ["user", "assistant", "tool"]
    assert detail.events[2].tool == "write_file"
    assert "deploy.sh" in detail.events[2].text
    hits = adapter.search("deploy")
    assert hits and hits[0].session_id == SESSION


def test_prompt_history_fallback(relay_home):
    make_freebuff_history(relay_home, ["first prompt", "second prompt about deploy"])
    adapter = FreebuffAdapter(relay_home)
    assert adapter.available() is True
    sessions = adapter.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == "prompt-history"
    assert sessions[0].title == "second prompt about deploy"
    assert sessions[0].turns_count == 2

    detail = adapter.load_session("latest")
    assert detail is not None
    assert [event.role for event in detail.events] == ["user", "user"]
    assert adapter.search("deploy")[0].session_id == "prompt-history"


def test_chats_are_never_modified(relay_home):
    make_freebuff(relay_home, "OrquestraAI", SESSION, _messages())
    before = snapshot(relay_home)
    adapter = FreebuffAdapter(relay_home)
    adapter.list_sessions()
    adapter.load_session("latest")
    adapter.search("deploy")
    assert snapshot(relay_home) == before


def test_missing_store_is_friendly(relay_home):
    adapter = FreebuffAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
