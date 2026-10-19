"""OpenCode adapter: sessions, parts, patch footprints and read-only access."""

from __future__ import annotations

from builders import make_opencode, snapshot
from session_relay.adapters.opencode import OpenCodeAdapter


def _sessions() -> list[dict]:
    return [
        {
            "id": "ses_new000000000000000001",
            "title": "Purge sessions alias",
            "directory": "/work/opencode",
            "created": 1_790_000_200_000,
            "updated": 1_790_000_300_000,
            "messages": [
                {
                    "role": "user",
                    "parts": [{"type": "text", "text": "Add a purge alias to bash"}],
                },
                {
                    "role": "assistant",
                    "parts": [
                        {"type": "text", "text": "Editing the shell config now."},
                        {
                            "type": "tool",
                            "tool": "edit",
                            "state": {
                                "status": "error",
                                "input": {"filePath": "/home/.bashrc"},
                                "error": "permission denied",
                            },
                        },
                        {"type": "patch", "files": ["/home/.bashrc"]},
                    ],
                },
            ],
        },
        {
            "id": "ses_old000000000000000002",
            "title": "Old question",
            "created": 1_790_000_000_000,
            "updated": 1_790_000_010_000,
            "messages": [
                {
                    "role": "user",
                    "parts": [{"type": "text", "text": "Explain the build"}],
                }
            ],
        },
    ]


def test_lists_sessions(relay_home):
    make_opencode(relay_home, _sessions())
    sessions = OpenCodeAdapter(relay_home).list_sessions()
    assert [session.title for session in sessions] == ["Purge sessions alias", "Old question"]
    assert sessions[0].turns_count == 2
    assert sessions[0].project == "/work/opencode"


def test_loads_tool_errors_and_patch_files(relay_home):
    make_opencode(relay_home, _sessions())
    detail = OpenCodeAdapter(relay_home).load_session("latest")
    assert detail is not None
    assert detail.summary.title == "Purge sessions alias"
    tools = [event.tool for event in detail.events if event.role == "tool"]
    assert "edit" in tools and "patch" in tools
    edit = next(event for event in detail.events if event.tool == "edit")
    assert edit.error is True
    assert "permission denied" in edit.text
    patch = next(event for event in detail.events if event.tool == "patch")
    assert "/home/.bashrc" in patch.text


def test_search_and_missing_session(relay_home):
    make_opencode(relay_home, _sessions())
    adapter = OpenCodeAdapter(relay_home)
    hits = adapter.search("purge")
    assert hits and hits[0].session_id.startswith("ses_new")
    assert adapter.load_session("ses_missing") is None


def test_store_is_never_modified(relay_home):
    make_opencode(relay_home, _sessions())
    before = snapshot(relay_home)
    adapter = OpenCodeAdapter(relay_home)
    adapter.list_sessions()
    adapter.load_session("latest")
    adapter.search("purge")
    assert snapshot(relay_home) == before


def test_missing_store_is_friendly(relay_home):
    adapter = OpenCodeAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
    assert adapter.search("x") == []
