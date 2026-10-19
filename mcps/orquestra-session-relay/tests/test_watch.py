"""Tests for watch_active_agent and tail_agent_activity."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from builders import make_claude
from session_relay.models import Event, SessionDetail, SessionSummary
from session_relay.server import server
from session_relay.watch import tail_agent_activity, watch_active_agent


def _now_iso(offset_seconds: int = 0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return dt.isoformat()


def test_watch_active_agent_empty_store():
    with patch("session_relay.discovery.recent_sessions", return_value=([], [])):
        res = watch_active_agent()
        assert res["active"] is False
        assert res["status"] == "idle"
        assert res["session_id"] is None
        assert res["last_turn"] is None
        assert res["files_touched"] == []


def test_watch_active_agent_running_vs_idle():
    recent_stamp = _now_iso(-10)  # 10s ago -> running
    idle_stamp = _now_iso(-300)  # 5m ago -> idle

    running_summary = SessionSummary(
        harness="claude",
        session_id="sess-run",
        title="Active fix",
        updated_at=recent_stamp,
        project="/work/alpha",
    )
    idle_summary = SessionSummary(
        harness="claude",
        session_id="sess-idle",
        title="Old task",
        updated_at=idle_stamp,
        project="/work/alpha",
    )

    with patch("session_relay.discovery.recent_sessions", return_value=([running_summary], [])):
        with patch("session_relay.discovery.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.load_session.return_value = SessionDetail(
                summary=running_summary,
                events=[Event("user", "go"), Event("assistant", "working on it")],
            )
            res = watch_active_agent()
            assert res["active"] is True
            assert res["status"] == "running"
            assert res["session_id"] == "sess-run"

    with patch("session_relay.discovery.recent_sessions", return_value=([idle_summary], [])):
        with patch("session_relay.discovery.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.load_session.return_value = SessionDetail(
                summary=idle_summary,
                events=[Event("user", "done"), Event("assistant", "finished")],
            )
            res = watch_active_agent()
            assert res["active"] is True
            assert res["status"] == "idle"
            assert res["session_id"] == "sess-idle"


def test_watch_active_agent_project_filtering():
    sess_a = SessionSummary(
        harness="codex",
        session_id="sess-a",
        title="Project A task",
        updated_at=_now_iso(-20),
        project="/work/project-a",
    )
    sess_b = SessionSummary(
        harness="antigravity",
        session_id="sess-b",
        title="Project B task",
        updated_at=_now_iso(-10),
        project="/work/project-b",
    )

    with patch("session_relay.discovery.recent_sessions", return_value=([sess_b, sess_a], [])):
        with patch("session_relay.discovery.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.load_session.return_value = SessionDetail(
                summary=sess_a,
                events=[Event("user", "fix a"), Event("assistant", "fixing a")],
            )

            # Filtering for project-a selects sess_a even if sess_b is newer
            res_a = watch_active_agent(project_path="/work/project-a")
            assert res_a["active"] is True
            assert res_a["session_id"] == "sess-a"
            assert res_a["harness"] == "codex"

            # Filtering with trailing slash resolves to same project
            res_a_slash = watch_active_agent(project_path="/work/project-a/")
            assert res_a_slash["active"] is True
            assert res_a_slash["session_id"] == "sess-a"

            # Filtering for non-existent project returns active=False
            res_c = watch_active_agent(project_path="/work/project-c")
            assert res_c["active"] is False
            assert res_c["session_id"] is None
            assert res_c["status"] == "idle"


def test_watch_active_agent_turn_extraction_and_files(relay_home):
    records = [
        {"type": "user", "message": {"content": "Inspect sidebar"}, "timestamp": _now_iso(-40)},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Editing component"},
                    {"type": "tool_use", "name": "edit_file", "input": {"file": "/app/src/sidebar.tsx"}},
                ]
            },
            "timestamp": _now_iso(-20),
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "content": 'Modified "/app/src/sidebar.tsx" successfully',
                    }
                ]
            },
            "timestamp": _now_iso(-10),
        },
    ]
    make_claude(relay_home, "-app", "sess-live", records)

    res = watch_active_agent()
    assert res["active"] is True
    assert res["harness"] == "claude"
    assert res["session_id"] == "sess-live"
    assert res["status"] == "running"
    assert res["last_turn"] is not None
    assert "Modified" in res["last_turn"]["text"]
    assert "/app/src/sidebar.tsx" in res["files_touched"]


def test_tail_agent_activity_defaults_to_recent(relay_home):
    records = [
        {"type": "user", "message": {"content": f"Turn {i}"}, "timestamp": _now_iso(-100 + i * 10)}
        for i in range(8)
    ]
    make_claude(relay_home, "-proj", "sess-tail", records)

    tail = tail_agent_activity(limit=3)
    assert tail["harness"] == "claude"
    assert tail["session_id"] == "sess-tail"
    assert tail["count"] == 3
    assert len(tail["events"]) == 3
    assert tail["events"][-1]["text"] == "Turn 7"


def test_tail_agent_activity_by_id_and_empty():
    summary = SessionSummary("grok", "s-123", "Grok search", _now_iso(-50))
    events = [Event("user", "search"), Event("assistant", "found")]

    with patch("session_relay.discovery.recent_sessions", return_value=([summary], [])):
        with patch("session_relay.discovery.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.load_session.return_value = SessionDetail(summary, events)

            # Tail with explicit session_id
            tail = tail_agent_activity(session_id="s-123")
            assert tail["session_id"] == "s-123"
            assert tail["count"] == 2

    # Unknown session returns error
    with patch("session_relay.discovery.recent_sessions", return_value=([], [])):
        with patch("session_relay.discovery.adapters_for", return_value=[]):
            tail_missing = tail_agent_activity(session_id="non-existent")
            assert tail_missing["count"] == 0
            assert "not found" in tail_missing["error"]


def test_server_tools_registered_and_callable(relay_home):
    records = [
        {"type": "user", "message": {"content": "Hello"}, "timestamp": _now_iso(-10)},
        {"type": "assistant", "message": {"content": "World"}, "timestamp": _now_iso(-5)},
    ]
    make_claude(relay_home, "-proj", "sess-srv", records)

    watch_res = asyncio.run(server.call_tool("watch_active_agent", {}))
    data = watch_res.structured_content
    assert data["active"] is True
    assert data["harness"] == "claude"
    assert data["session_id"] == "sess-srv"
    assert data["status"] == "running"

    tail_res = asyncio.run(server.call_tool("tail_agent_activity", {"limit": 2}))
    tail_data = tail_res.structured_content
    assert tail_data["count"] == 2
    assert tail_data["events"][-1]["text"] == "World"
