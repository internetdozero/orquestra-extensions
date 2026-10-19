"""Antigravity adapter: brain transcripts, session ids, errors and search."""

from __future__ import annotations

import os

from builders import make_antigravity, snapshot
from session_relay.adapters.antigravity import AntigravityAdapter

SESSION = "ca4dd338-f842-4c20-8b18-40674c2addd6"


def _records() -> list[dict]:
    return [
        {
            "step_index": 0,
            "type": "USER_INPUT",
            "source": "USER_EXPLICIT",
            "status": "DONE",
            "created_at": "2026-10-17T11:31:50Z",
            "content": "<USER_REQUEST>Fix the sidebar collapse</USER_REQUEST><ADDITIONAL_METADATA>noise",
        },
        {
            "step_index": 1,
            "type": "PLANNER_RESPONSE",
            "source": "MODEL",
            "status": "DONE",
            "created_at": "2026-10-17T11:31:57Z",
            "thinking": "I will inspect the sidebar component.",
            "tool_calls": [
                {
                    "name": "view_file",
                    "args": {"AbsolutePath": '"/work/orquestra/src/sidebar.tsx"'},
                }
            ],
        },
        {
            "step_index": 2,
            "type": "GENERIC",
            "status": "DONE",
            "created_at": "2026-10-17T11:32:01Z",
            "content": "File Path: `file:///work/orquestra/src/sidebar.tsx`",
        },
        {
            "step_index": 3,
            "type": "GENERIC",
            "status": "RUNNING",
            "created_at": "2026-10-17T11:32:02Z",
            "content": "background task still running",
        },
        {
            "step_index": 4,
            "type": "ERROR_MESSAGE",
            "status": "DONE",
            "created_at": "2026-10-17T11:32:05Z",
            "content": "Build failed: missing export",
        },
        {
            "step_index": 5,
            "type": "USER_INPUT",
            "status": "DONE",
            "created_at": "2026-10-17T11:33:00Z",
            "content": "<USER_REQUEST>Also check the footer</USER_REQUEST>",
        },
    ]


def _setup(home):
    newer = make_antigravity(home, SESSION, _records())
    older = make_antigravity(
        home,
        "11111111-2222-3333-4444-555555555555",
        [
            {
                "type": "USER_INPUT",
                "status": "DONE",
                "created_at": "2026-10-16T10:00:00Z",
                "content": "<USER_REQUEST>Old session</USER_REQUEST>",
            }
        ],
    )
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_700_000_100, 1_700_000_100))


def test_session_id_is_the_brain_uuid(relay_home):
    _setup(relay_home)
    sessions = AntigravityAdapter(relay_home).list_sessions()
    assert sessions[0].session_id == SESSION
    assert sessions[0].title == "Fix the sidebar collapse"
    assert sessions[0].turns_count == 2
    assert sessions[0].updated_at == "2026-10-17T11:33:00Z"


def test_events_mark_only_real_failures(relay_home):
    _setup(relay_home)
    detail = AntigravityAdapter(relay_home).load_session("latest", max_turns=10)
    assert detail is not None
    tools = [event.tool for event in detail.events if event.role == "tool"]
    assert "view_file" in tools
    errors = [event for event in detail.events if event.error]
    assert len(errors) == 1
    assert "Build failed" in errors[0].text
    assert any("background task still running" in event.text for event in detail.events)


def test_turn_limit_and_search(relay_home):
    _setup(relay_home)
    adapter = AntigravityAdapter(relay_home)
    limited = adapter.load_session(SESSION, max_turns=1)
    assert limited is not None
    assert limited.events[0].text == "Also check the footer"
    hits = adapter.search("sidebar")
    assert hits and hits[0].session_id == SESSION
    assert adapter.search("nothing") == []


def test_transcripts_are_never_modified(relay_home):
    _setup(relay_home)
    before = snapshot(relay_home)
    adapter = AntigravityAdapter(relay_home)
    adapter.list_sessions()
    adapter.load_session("latest")
    adapter.search("sidebar")
    assert snapshot(relay_home) == before


def test_missing_store_is_friendly(relay_home):
    adapter = AntigravityAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
