"""Prompt field: persistence, querying, batch, update, export and migration."""

from __future__ import annotations

import sqlite3

from idea_vault import ideas
from idea_vault.store import connect, migrate_prompt


def test_record_idea_prompt_roundtrip(conn):
    created = ideas.record_idea(
        conn, "OrquestraAI", "Ship feature",
        description="Short summary",
        prompt="### Mission: Ship feature\n\nDo the thing.",
    )
    assert created["prompt"] == "### Mission: Ship feature\n\nDo the thing."
    assert created["description"] == "Short summary"

    listed = ideas.list_ideas(conn, project="OrquestraAI")
    assert listed["ideas"][0]["prompt"] == "### Mission: Ship feature\n\nDo the thing."

    found = ideas.search_ideas(conn, "Ship feature")
    assert found["count"] >= 1
    assert found["ideas"][0]["prompt"] == "### Mission: Ship feature\n\nDo the thing."


def test_record_idea_prompt_defaults_empty(conn):
    created = ideas.record_idea(conn, "OrquestraAI", "No prompt yet")
    assert created["prompt"] == ""


def test_search_matches_prompt_text(conn):
    ideas.record_idea(conn, "OrquestraAI", "Unrelated", prompt="zebracorn deploy token")
    found = ideas.search_ideas(conn, "zebracorn")
    assert found["count"] == 1
    assert found["ideas"][0]["prompt"] == "zebracorn deploy token"


def test_record_batch_supports_prompt(conn):
    result = ideas.record_ideas_batch(conn, "BatchProject", [
        {"title": "A", "prompt": "Prompt A"},
        {"title": "B"},
    ])
    assert result["ideas"][0]["prompt"] == "Prompt A"
    assert result["ideas"][1]["prompt"] == ""


def test_update_idea_prompt(conn):
    created = ideas.record_idea(conn, "OrquestraAI", "Evolving task")
    assert created["prompt"] == ""
    updated = ideas.update_idea(conn, created["id"], prompt="Revised builder dispatch")
    assert updated["prompt"] == "Revised builder dispatch"
    # None leaves prompt untouched
    untouched = ideas.update_idea(conn, created["id"], title="Evolving task v2")
    assert untouched["prompt"] == "Revised builder dispatch"


def test_export_markdown_includes_builder_prompt(conn):
    ideas.record_idea(
        conn, "OrquestraAI", "Prompted task",
        prompt="### Mission: Prompted task\n\nSteps here.",
    )
    ideas.record_idea(conn, "OrquestraAI", "Plain task")
    exported = ideas.export_ideas_markdown(conn, "OrquestraAI")
    assert "### Builder Prompt — Prompted task" in exported["markdown"]
    assert "Steps here." in exported["markdown"]
    # Plain task has no prompt block of its own
    assert "### Builder Prompt — Plain task" not in exported["markdown"]


def test_migration_adds_prompt_column(tmp_path):
    path = tmp_path / "legacy-prompt" / "ideas.sqlite3"
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
            " updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " completed_at TIMESTAMP)"
        )
        raw.execute("INSERT INTO ideas (project, title) VALUES ('P', 'legacy')")
        raw.commit()
    finally:
        raw.close()

    conn = connect(path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(ideas)")}
        assert "prompt" in columns
        row = conn.execute("SELECT * FROM ideas WHERE title = 'legacy'").fetchone()
        from idea_vault.serializers import idea_dict
        assert idea_dict(row)["prompt"] == ""
        assert migrate_prompt(conn) is False
    finally:
        conn.close()
