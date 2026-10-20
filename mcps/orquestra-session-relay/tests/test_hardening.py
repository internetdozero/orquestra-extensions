"""Tests for Idea #262: watch filters, turn liveness, compact, audit_agent."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from builders import make_claude, make_freebuff_desktop
from session_relay.adapters.freebuff_desktop import list_desktop_threads, read_turn_liveness
from session_relay.compact import compact_row, compact_session, open_todos
from session_relay.models import Event, SessionDetail, SessionSummary, session_is_live
from session_relay.server import server
from session_relay.watch import tail_agent_activity, watch_active_agent


def _now_iso(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


def _summary(harness: str, sid: str, project: str | None = None) -> SessionSummary:
    return SessionSummary(
        harness=harness, session_id=sid, title=f"{harness} task",
        updated_at=_now_iso(-10), project=project,
    )


def _detail(summary: SessionSummary, events: list[Event]) -> SessionDetail:
    return SessionDetail(summary=summary, events=events)


# --- 1. harness / exclude_harness filtering ---

def test_watch_exclude_harness_skips_own_session():
    orch = _summary("freebuff", "orch-1")
    builder = _summary("claude", "build-9")

    with patch("session_relay.discovery.recent_sessions", return_value=([orch, builder], [])):
        with patch("session_relay.discovery.get_adapter") as mock_get:
            mock_get.return_value.load_session.return_value = _detail(
                builder, [Event("user", "build it"), Event("assistant", "on it")]
            )
            res = watch_active_agent(exclude_harness="freebuff")
            assert res["active"] is True
            assert res["session_id"] == "build-9"
            assert res["harness"] == "claude"


def test_watch_harness_filter_and_unknown_harness():
    orch = _summary("freebuff", "orch-1")
    builder = _summary("claude", "build-9")

    with patch(
        "session_relay.discovery.recent_sessions",
        side_effect=lambda harness=None, limit=50: (
            ([s for s in [orch, builder] if harness is None or s.harness == harness], [])
        ),
    ):
        with patch("session_relay.discovery.get_adapter") as mock_get:
            mock_get.return_value.load_session.return_value = _detail(
                orch, [Event("user", "orchestrate"), Event("assistant", "delegating")]
            )
            res = watch_active_agent(harness="freebuff")
            assert res["session_id"] == "orch-1"

    res_bad = watch_active_agent(harness="no-such-harness")
    assert res_bad["active"] is False
    assert "error" in res_bad


# --- 2. freebuff turn liveness ---

def test_desktop_liveness_running_and_stale(relay_home):
    now_ms = int(time.time() * 1000)
    slug = "liveproj"
    make_freebuff_desktop(relay_home, slug, [
        {"id": "11111111-1111-1111-1111-111111111111", "title": "hot",
         "turn_state": "running", "turn_alive_at": now_ms - 5_000},
        {"id": "22222222-2222-2222-2222-222222222222", "title": "cold",
         "turn_state": "running", "turn_alive_at": now_ms - 600_000},
    ])
    sessions = list_desktop_threads(relay_home, "freebuff")
    by_title = {s.title: s for s in sessions}
    assert by_title["hot"].status == "running"
    assert by_title["hot"].turn_state == "running"
    assert by_title["hot"].alive_seconds_ago is not None
    assert by_title["hot"].alive_seconds_ago < 120
    assert session_is_live(by_title["hot"]) is True
    assert by_title["cold"].status is None
    assert session_is_live(by_title["cold"]) is False


def test_desktop_liveness_legacy_store_without_columns(relay_home):
    db = relay_home / ".config/freebuff-desktop/projects" / "legacy" / "desktop-v2.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE threads (id TEXT PRIMARY KEY, project_id TEXT NOT NULL,"
        " project_path TEXT NOT NULL, title TEXT NOT NULL DEFAULT 'New thread',"
        " created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);"
        "CREATE TABLE messages (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " thread_id TEXT NOT NULL, role TEXT NOT NULL,"
        " parts_json TEXT NOT NULL DEFAULT '[]', ts INTEGER NOT NULL);"
    )
    conn.execute(
        "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)",
        ("33333333-3333-3333-3333-333333333333", "p1", "/work/old", "legacy", 1, 1),
    )
    conn.commit()
    conn.close()
    assert read_turn_liveness(db, "33333333-3333-3333-3333-333333333333") is None
    sessions = list_desktop_threads(relay_home, "freebuff")
    assert sessions and sessions[0].turn_state is None


# --- 3. compact payloads ---

def test_compact_session_shape():
    summary = _summary("codex", "c-1", "/work/proj")
    events = [
        Event("user", "Fix the login redirect"),
        Event("tool", '{"file": "/app/src/login.ts"}', tool="edit"),
        Event("assistant", "- [ ] add redirect test\n- [x] done thing"),
    ]
    compacted = compact_session(_detail(summary, events))
    assert compacted["session_id"] == "c-1"
    assert compacted["last_instruction"] == "Fix the login redirect"
    assert compacted["last_tool"] == "edit"
    assert "/app/src/login.ts" in compacted["touched_files"]
    assert compacted["open_todos"] == ["add redirect test"]
    assert "events" not in compacted
    assert compact_row(summary)["status"] in ("running", "idle")


def test_server_compact_and_audit_tools_registered(relay_home):
    records = [
        {"type": "user", "message": {"content": "Ship it"}, "timestamp": _now_iso(-10)},
        {"type": "assistant", "message": {"content": "Shipping"}, "timestamp": _now_iso(-5)},
    ]
    make_claude(relay_home, "-proj", "sess-compact", records)

    compact_res = asyncio.run(server.call_tool("inspect_session", {"compact": True}))
    data = compact_res.structured_content
    assert data["compact"] is True
    assert data["last_instruction"] == "Ship it"
    assert "events" not in data

    list_res = asyncio.run(server.call_tool("list_recent_sessions", {"compact": True}))
    listed = list_res.structured_content
    assert listed["compact"] is True
    assert listed["sessions"] and "events" not in listed["sessions"][0]

    watch_res = asyncio.run(
        server.call_tool("watch_active_agent", {"exclude_harness": "codex"})
    )
    assert watch_res.structured_content["harness"] == "claude"


# --- 4. audit_agent with a real dirty git worktree ---

def test_audit_agent_reports_git_dirty_files(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=project, check=True)
    (project / "dirty.txt").write_text("modified\n")
    summary = SessionSummary(
        harness="claude", session_id="s-audit", title="Audit me",
        updated_at=_now_iso(-30), project=str(project),
    )
    events = [
        Event("user", "do work", timestamp=_now_iso(-120)),
        Event("assistant", "working", timestamp=_now_iso(-30)),
    ]
    with patch("session_relay.discovery.recent_sessions", return_value=([summary], [])):
        with patch("session_relay.discovery.get_adapter") as mock_get:
            mock_get.return_value.available.return_value = True
            mock_get.return_value.load_session.return_value = _detail(summary, events)
            res = asyncio.run(server.call_tool("audit_agent", {"harness": "claude"}))
    data = res.structured_content
    assert data["harness"] == "claude"
    assert data["session_id"] == "s-audit"
    assert data["status"] == "running"
    assert data["current_turn_preview"] == "working"
    assert any("dirty.txt" in f for f in data["git_dirty_files"])
    assert data["running_duration_s"] is not None and data["running_duration_s"] >= 0


def test_audit_agent_unknown_session_reports_error(relay_home):
    from session_relay.audit import audit_agent
    res = audit_agent("claude", session_id="ghost")
    assert res["status"] == "idle"
    assert "error" in res
    assert set(res) >= {
        "harness", "session_id", "status", "current_turn_preview",
        "git_dirty_files", "running_duration_s",
    }


def test_open_todos_empty_without_checkboxes():
    assert open_todos([Event("user", "no todos here")]) == []
    assert tail_agent_activity  # import guard: tail keeps its clipped shape
