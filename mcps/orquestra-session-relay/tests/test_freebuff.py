"""Freebuff adapter: project chats, tool blocks and prompt-history fallback."""

from __future__ import annotations

import os

from builders import (
    make_freebuff,
    make_freebuff_desktop,
    make_freebuff_history,
    snapshot,
)
from session_relay.adapters.freebuff import FreebuffAdapter

SESSION = "2026-10-17T10-00-00.000Z"
SLUG = "OrquestraAI-708e6d53"
THREAD = "d89c29ca-be1c-4fe8-be92-f4de238d0286"
DESKTOP_ID = f"desktop:{SLUG}:{THREAD}"


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


def _desktop_threads(**overrides):
    thread = {
        "id": THREAD,
        "title": "Community Skills Hub",
        "project_path": "/work/OrquestraAI",
        "created": 1_790_000_100_000,
        "updated": 1_790_000_400_000,
        "messages": [
            {
                "role": "user",
                "ts": 1_790_000_100_000,
                "parts": [{"kind": "text", "text": "Make the deploy faster"}],
            },
            {
                "role": "assistant",
                "ts": 1_790_000_400_000,
                "parts": [
                    {"kind": "text", "text": "Trimming the build step."},
                    {"kind": "reasoning", "text": "secret chain of thought"},
                    {
                        "kind": "tool",
                        "toolName": "write_file",
                        "input": {"path": "deploy.sh"},
                        "status": "success",
                        "output": "updated deploy.sh",
                    },
                ],
            },
        ],
    }
    thread.update(overrides)
    return [thread]


def test_lists_desktop_threads_with_prefixed_ids(relay_home):
    make_freebuff_desktop(relay_home, SLUG, _desktop_threads())
    sessions = FreebuffAdapter(relay_home).list_sessions()
    assert len(sessions) == 1
    session = sessions[0]
    assert session.session_id == DESKTOP_ID
    assert session.title == "Community Skills Hub"
    assert session.project == "/work/OrquestraAI"
    assert session.turns_count == 1


def test_merges_legacy_and_desktop_newest_first(relay_home):
    make_freebuff(relay_home, "OrquestraAI", SESSION, _messages())
    make_freebuff_desktop(relay_home, SLUG, _desktop_threads())
    sessions = FreebuffAdapter(relay_home).list_sessions(limit=5)
    assert [session.session_id for session in sessions] == [DESKTOP_ID, SESSION]


def test_loads_desktop_by_full_id_and_raw_uuid(relay_home):
    make_freebuff_desktop(relay_home, SLUG, _desktop_threads())
    adapter = FreebuffAdapter(relay_home)
    for session_id in (DESKTOP_ID, THREAD):
        detail = adapter.load_session(session_id)
        assert detail is not None
        assert [event.role for event in detail.events] == [
            "user",
            "assistant",
            "tool",
        ]
        assert detail.events[0].text == "Make the deploy faster"
        assert detail.events[1].text == "Trimming the build step."
        assert "secret chain" not in " ".join(e.text for e in detail.events)
        tool = detail.events[2]
        assert tool.tool == "write_file"
        assert "deploy.sh" in tool.text
        assert "updated deploy.sh" in tool.text
        assert tool.error is False


def test_desktop_slug_mismatch_still_finds_thread(relay_home):
    make_freebuff_desktop(relay_home, SLUG, _desktop_threads())
    detail = FreebuffAdapter(relay_home).load_session(f"desktop:renamed:{THREAD}")
    assert detail is not None
    assert detail.summary.session_id == DESKTOP_ID


def test_unknown_desktop_id_is_none(relay_home):
    make_freebuff_desktop(relay_home, SLUG, _desktop_threads())
    adapter = FreebuffAdapter(relay_home)
    assert adapter.load_session("desktop:missing:00000000-0000-4000-8000-000000000000") is None
    assert adapter.load_session("desktop:broken") is None


def test_searches_desktop_threads(relay_home):
    make_freebuff_desktop(relay_home, SLUG, _desktop_threads())
    hits = FreebuffAdapter(relay_home).search("deploy")
    assert hits and hits[0].session_id == DESKTOP_ID


def test_chats_are_never_modified(relay_home):
    make_freebuff(relay_home, "OrquestraAI", SESSION, _messages())
    before = snapshot(relay_home)
    adapter = FreebuffAdapter(relay_home)
    adapter.list_sessions()
    adapter.load_session("latest")
    adapter.search("deploy")
    assert snapshot(relay_home) == before


def test_desktop_databases_are_never_modified(relay_home):
    make_freebuff_desktop(relay_home, SLUG, _desktop_threads())
    before = snapshot(relay_home)
    adapter = FreebuffAdapter(relay_home)
    adapter.list_sessions()
    adapter.load_session(DESKTOP_ID)
    adapter.load_session(THREAD)
    adapter.search("deploy")
    assert snapshot(relay_home) == before


def test_missing_store_is_friendly(relay_home):
    adapter = FreebuffAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
