"""Regression tests for blackboard notes and MCP server wiring."""

from __future__ import annotations

import asyncio
import sqlite3

import pytest

from idea_vault import blackboard
from idea_vault.store import ENV_DB_PATH, configure, get_database, reset_databases

EXPECTED_TOOLS = [
    "record_idea",
    "record_ideas_batch",
    "list_ideas",
    "search_ideas",
    "update_idea",
    "update_idea_status",
    "delete_idea",
    "export_ideas_markdown",
    "post_board_note",
    "read_board_notes",
    "clear_board_notes",
]


def test_blackboard_post_read_mark_and_clear(conn):
    posted = blackboard.post_board_note(
        conn, "OrquestraAI", "backend", "IPC contract frozen", sender="claude-code"
    )
    assert posted["id"] == 1
    assert posted["is_read"] is False
    blackboard.post_board_note(conn, "OrquestraAI", "frontend", "Need types", sender="human")

    unread = blackboard.read_board_notes(conn, "OrquestraAI")
    assert unread["count"] == 2
    assert [note["note"] for note in unread["notes"]] == [
        "IPC contract frozen",
        "Need types",
    ]

    marked = blackboard.read_board_notes(
        conn, "OrquestraAI", topic="backend", mark_as_read=True
    )
    assert marked["count"] == 1
    assert marked["notes"][0]["is_read"] is True
    assert conn.execute("SELECT is_read FROM blackboard_notes WHERE id = 1").fetchone()[0] == 1

    remaining = blackboard.read_board_notes(conn, "OrquestraAI")
    assert [note["note"] for note in remaining["notes"]] == ["Need types"]

    cleared = blackboard.clear_board_notes(conn, "OrquestraAI")
    assert cleared["deleted"] == 1
    assert blackboard.read_board_notes(conn, "OrquestraAI", unread_only=False)["count"] == 1

    wiped = blackboard.clear_board_notes(conn, "OrquestraAI", include_unread=True)
    assert wiped["deleted"] == 1
    assert blackboard.read_board_notes(conn, "OrquestraAI", unread_only=False)["count"] == 0


def test_blackboard_filters_by_topic_and_target(conn):
    blackboard.post_board_note(conn, "P", "backend", "for all", sender="a")
    blackboard.post_board_note(conn, "P", "backend", "for backend", target="backend-agent")
    blackboard.post_board_note(conn, "Q", "backend", "other project")

    addressed = blackboard.read_board_notes(conn, "P", target="backend-agent")
    assert [note["note"] for note in addressed["notes"]] == ["for all", "for backend"]

    topic = blackboard.read_board_notes(conn, "P", topic="backend", unread_only=False)
    assert topic["count"] == 2

    with pytest.raises(ValueError):
        blackboard.post_board_note(conn, "P", "backend", "   ")


def test_server_registers_every_tool_and_uses_configured_database(db_path):
    from idea_vault.server import server

    async def exercise():
        tools = await server.list_tools()
        result = await server.call_tool(
            "record_idea", {"project": "MCP", "title": "via tool", "tags": ["x"]}
        )
        batch = await server.call_tool(
            "record_ideas_batch",
            {"project": "MCP", "items": [{"title": "batch 1"}, {"title": "batch 2"}]},
        )
        updated = await server.call_tool(
            "update_idea", {"idea_id": 1, "title": "via tool updated"}
        )
        compact = await server.call_tool("list_ideas", {"project": "MCP", "compact": True})
        deleted = await server.call_tool("delete_idea", {"idea_id": 1})
        listed = await server.call_tool("list_ideas", {"project": "MCP"})
        return tools, result, batch, updated, compact, deleted, listed

    tools, result, batch, updated, compact, deleted, listed = asyncio.run(exercise())
    assert [tool.name for tool in tools] == EXPECTED_TOOLS
    assert result.structured_content["id"] == 1
    assert batch.structured_content["count"] == 2
    assert updated.structured_content["title"] == "via tool updated"
    assert compact.structured_content["compact"] is True
    assert deleted.structured_content["deleted"] is True
    assert listed.structured_content["count"] == 2
    assert db_path.exists()

    with sqlite3.connect(db_path) as check:
        assert check.execute("SELECT COUNT(*) FROM ideas").fetchone()[0] == 2


def test_configure_pins_path_for_tools_without_env(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_DB_PATH, raising=False)
    reset_databases()
    pinned = tmp_path / "pinned" / "ideas.sqlite3"
    try:
        assert configure(pinned) == pinned

        from idea_vault.server import server

        asyncio.run(
            server.call_tool(
                "record_idea", {"project": "Pinned", "title": "explicit path"}
            )
        )
        assert pinned.exists()

        with sqlite3.connect(pinned) as check:
            assert check.execute("SELECT title FROM ideas").fetchone()[0] == "explicit path"
    finally:
        configure(None)
        reset_databases()


def test_main_pins_cli_db_argument(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_DB_PATH, raising=False)
    reset_databases()
    import idea_vault.server as server_module

    monkeypatch.setattr(server_module.server, "run", lambda transport: None)
    target = tmp_path / "cli" / "ideas.sqlite3"
    try:
        assert server_module.main(["--db", str(target), "--transport", "stdio"]) == 0
        assert target.exists()
        assert get_database().path == target
    finally:
        configure(None)
        reset_databases()
