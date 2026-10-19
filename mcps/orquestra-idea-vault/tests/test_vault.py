"""Regression tests for the idea vault schema, idea CRUD, search and export."""

from __future__ import annotations

import pytest

from idea_vault import ideas
from idea_vault.serializers import load_tags, parse_tags
from idea_vault.store import ENV_DB_PATH, connect, default_db_path


def _record(conn, project="OrquestraAI", title="Speed up deploy", **kwargs):
    return ideas.record_idea(conn, project, title, **kwargs)


def test_connect_creates_directory_schema_and_indexes(tmp_path):
    path = tmp_path / "nested" / "dir" / "ideas.sqlite3"
    assert not path.parent.exists()
    conn = connect(path)
    try:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        indexes = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        }
    finally:
        conn.close()
    assert path.exists()
    assert {"ideas", "blackboard_notes"} <= tables
    assert {"idx_ideas_project_status", "idx_notes_project_topic"} <= indexes


def test_default_path_honors_env_and_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_DB_PATH, str(tmp_path / "custom.sqlite3"))
    assert default_db_path() == tmp_path / "custom.sqlite3"

    monkeypatch.delenv(ENV_DB_PATH)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert default_db_path() == tmp_path / "xdg" / "idea-vault" / "ideas.sqlite3"

    monkeypatch.delenv("XDG_DATA_HOME")
    assert default_db_path().parts[-4:] == (
        ".local",
        "share",
        "idea-vault",
        "ideas.sqlite3",
    )


def test_record_idea_roundtrip_and_tag_storage(conn):
    created = _record(
        conn,
        title="Local FTS",
        description="Add FTS5 search",
        category="architecture",
        priority="high",
        tags=["search", "Search", " sqlite "],
    )
    assert created["id"] == 1
    assert created["status"] == "open"
    assert created["tags"] == ["search", "sqlite"]
    assert "Recorded idea #1" in created["message"]

    raw = conn.execute("SELECT tags FROM ideas WHERE id = 1").fetchone()["tags"]
    assert raw == '["search", "sqlite"]'
    assert load_tags(raw) == ["search", "sqlite"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("category", "chore"),
        ("priority", "urgent"),
        ("title", "   "),
        ("project", ""),
    ],
)
def test_record_idea_rejects_invalid_input(conn, field, value):
    kwargs = {"project": "P", "title": "T"}
    kwargs[field] = value
    with pytest.raises(ValueError):
        ideas.record_idea(conn, **kwargs)


def test_list_ideas_filters_and_orders_by_priority(conn):
    _record(conn, title="low one", priority="low")
    _record(conn, title="critical one", priority="critical")
    _record(conn, project="PersonalSite", title="other project", priority="high")
    done = _record(conn, title="done one")
    ideas.update_idea_status(conn, done["id"], "completed")
    _record(conn, title="bug one", category="bug", priority="medium")

    open_ideas = ideas.list_ideas(conn, project="OrquestraAI")
    assert [item["title"] for item in open_ideas["ideas"]][:2] == [
        "critical one",
        "bug one",
    ]
    assert all(item["status"] == "open" for item in open_ideas["ideas"])
    assert open_ideas["count"] == 3

    all_status = ideas.list_ideas(conn, project="OrquestraAI", status="all")
    assert all_status["count"] == 4
    assert all_status["status"] == "all"

    bugs = ideas.list_ideas(conn, project="OrquestraAI", category="bug")
    assert [item["title"] for item in bugs["ideas"]] == ["bug one"]

    critical = ideas.list_ideas(conn, priority="critical")
    assert critical["count"] == 1

    with pytest.raises(ValueError):
        ideas.list_ideas(conn, status="blocked")


def test_search_matches_title_description_and_tags(conn):
    _record(conn, title="Deploy pipeline", description="stream logs to the tray")
    _record(conn, title="Tray icon", tags=["ui", "deploy"])
    _record(conn, project="Other", title="Deploy elsewhere")

    found = ideas.search_ideas(conn, "deploy", project="OrquestraAI")
    assert found["count"] == 2
    assert {item["title"] for item in found["ideas"]} == {"Deploy pipeline", "Tray icon"}

    description_hit = ideas.search_ideas(conn, "stream logs")
    assert [item["title"] for item in description_hit["ideas"]] == ["Deploy pipeline"]

    assert ideas.search_ideas(conn, "nomatch")["count"] == 0
    # LIKE wildcards are escaped, not interpreted.
    assert ideas.search_ideas(conn, "%")["count"] == 0


def test_update_status_and_missing_id(conn):
    created = _record(conn)
    updated = ideas.update_idea_status(conn, created["id"], "in_progress")
    assert updated["status"] == "in_progress"
    assert conn.execute("SELECT status FROM ideas WHERE id = 1").fetchone()[0] == "in_progress"

    with pytest.raises(LookupError):
        ideas.update_idea_status(conn, 999, "open")
    with pytest.raises(ValueError):
        ideas.update_idea_status(conn, created["id"], "someday")


def test_export_markdown_groups_active_ideas(conn):
    _record(conn, title="Faster index", category="architecture", priority="high")
    _record(conn, title="Tray toggle", category="ux")
    in_progress = _record(conn, title="Ship vault", category="feature")
    ideas.update_idea_status(conn, in_progress["id"], "in_progress")
    archived = _record(conn, title="Old dream", category="idea")
    ideas.update_idea_status(conn, archived["id"], "archived")

    exported = ideas.export_ideas_markdown(conn, "OrquestraAI")
    markdown = exported["markdown"]
    assert exported["count"] == 3
    assert markdown.startswith("# Ideas — OrquestraAI")
    assert "## Architecture" in markdown
    assert "## Features" in markdown
    assert "## UX" in markdown
    assert "Old dream" not in markdown
    assert "_in progress_" in markdown
    assert markdown.index("## Features") < markdown.index("## Architecture")
    assert "- [ ] **Ship vault**" in markdown

    empty = ideas.export_ideas_markdown(conn, "NothingHere")["markdown"]
    assert "_No open or in-progress ideas._" in empty


def test_tag_helpers_tolerate_legacy_and_iterables():
    assert parse_tags("a, b ,, a") == ["a", "b"]
    assert parse_tags(None) == []
    assert load_tags("legacy,comma") == ["legacy", "comma"]
    assert load_tags('["json", "array"]') == ["json", "array"]
    assert load_tags(None) == []
