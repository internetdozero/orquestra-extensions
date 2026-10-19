"""completed_at lifecycle: timestamps, preservation, clearing and migration."""

from __future__ import annotations

import sqlite3

from idea_vault import ideas
from idea_vault.store import connect, migrate_completed_at


def _record(conn, title="Lifecycle probe", **kwargs):
    return ideas.record_idea(conn, "OrquestraAI", title, **kwargs)


def test_new_idea_has_no_completed_at(conn):
    created = _record(conn)
    assert created["completed_at"] is None
    assert created["status"] == "open"


def test_record_idea_completed_sets_timestamp(conn):
    created = _record(conn, status="completed")
    assert created["status"] == "completed"
    assert created["completed_at"] is not None


def test_in_progress_keeps_completed_at_none(conn):
    created = _record(conn)
    updated = ideas.update_idea_status(conn, created["id"], "in_progress")
    assert updated["status"] == "in_progress"
    assert updated["completed_at"] is None


def test_completed_stamps_completed_at(conn):
    created = _record(conn)
    updated = ideas.update_idea_status(conn, created["id"], "completed")
    assert updated["status"] == "completed"
    assert updated["completed_at"] is not None


def test_completed_is_sticky_on_repeat(conn):
    created = _record(conn)
    first = ideas.update_idea_status(conn, created["id"], "completed")
    second = ideas.update_idea_status(conn, created["id"], "completed")
    assert first["completed_at"] is not None
    assert second["completed_at"] == first["completed_at"]


def test_archived_preserves_completed_at(conn):
    created = _record(conn)
    done = ideas.update_idea_status(conn, created["id"], "completed")
    archived = ideas.update_idea_status(conn, created["id"], "archived")
    assert archived["status"] == "archived"
    assert archived["completed_at"] == done["completed_at"]


def test_reopen_clears_completed_at(conn):
    created = _record(conn)
    ideas.update_idea_status(conn, created["id"], "completed")
    reopened = ideas.update_idea_status(conn, created["id"], "open")
    assert reopened["status"] == "open"
    assert reopened["completed_at"] is None


def test_back_to_in_progress_clears_completed_at(conn):
    created = _record(conn)
    ideas.update_idea_status(conn, created["id"], "completed")
    moved = ideas.update_idea_status(conn, created["id"], "in_progress")
    assert moved["completed_at"] is None


def test_update_idea_preserves_completed_at(conn):
    created = _record(conn)
    done = ideas.update_idea_status(conn, created["id"], "completed")
    edited = ideas.update_idea(conn, created["id"], title="Renamed")
    assert edited["completed_at"] == done["completed_at"]


def test_compact_includes_completed_at(conn):
    _record(conn)
    compact = ideas.list_ideas(conn, project="OrquestraAI", compact=True)
    assert compact["count"] == 1
    assert compact["ideas"][0]["completed_at"] is None


def test_migration_backfills_legacy_completed(tmp_path):
    path = tmp_path / "legacy" / "ideas.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(path)
    try:
        raw.execute(
            "CREATE TABLE ideas (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " project TEXT NOT NULL, title TEXT NOT NULL, description TEXT,"
            " category TEXT NOT NULL DEFAULT 'feature',"
            " priority TEXT NOT NULL DEFAULT 'medium', tags TEXT,"
            " status TEXT NOT NULL DEFAULT 'open',"
            " created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        raw.execute(
            "INSERT INTO ideas (project, title, status, updated_at)"
            " VALUES ('P', 'legacy done', 'completed', '2026-01-02 03:04:05')"
        )
        raw.execute(
            "INSERT INTO ideas (project, title, status) VALUES ('P', 'legacy open', 'open')"
        )
        raw.commit()
    finally:
        raw.close()

    conn = connect(path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(ideas)")}
        assert "completed_at" in columns
        done = conn.execute(
            "SELECT completed_at FROM ideas WHERE title = 'legacy done'"
        ).fetchone()[0]
        assert done == "2026-01-02 03:04:05"
        open_row = conn.execute(
            "SELECT completed_at FROM ideas WHERE title = 'legacy open'"
        ).fetchone()[0]
        assert open_row is None
        # Second run is a no-op returning False.
        assert migrate_completed_at(conn) is False
    finally:
        conn.close()
