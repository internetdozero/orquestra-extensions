"""Tests for new granular Idea Vault & Blackboard tools."""

from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from idea_vault import server, store

TEST_DIR = Path("/var/tmp/testing/idea-vault-tests")


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch: pytest.MonkeyPatch) -> None:
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    db_path = TEST_DIR / f"test-{uuid.uuid4().hex}.sqlite3"
    monkeypatch.setenv(store.ENV_DB_PATH, str(db_path))
    store.configure(str(db_path))
    try:
        yield
    finally:
        if db_path.exists():
            db_path.unlink()


def _call(name: str, **arguments: Any) -> Any:
    return asyncio.run(server.server.call_tool(name, arguments))


def test_get_idea_and_list_projects() -> None:
    _call("record_idea", project="ProjectAlpha", title="Task 1", category="feature")
    rec2 = _call("record_idea", project="ProjectBeta", title="Task 2", category="bug")
    idea_id = rec2.structured_content["id"]

    fetched = _call("get_idea", idea_id=idea_id)
    assert fetched.is_error is False
    assert fetched.structured_content["id"] == idea_id
    assert fetched.structured_content["title"] == "Task 2"
    assert fetched.structured_content["project"] == "ProjectBeta"

    projects = _call("list_projects")
    assert projects.is_error is False
    assert projects.structured_content["count"] == 2
    assert projects.structured_content["projects"] == ["ProjectAlpha", "ProjectBeta"]


def test_get_idea_not_found_raises_tool_error() -> None:
    with pytest.raises(ToolError) as exc_info:
        _call("get_idea", idea_id=9999)
    assert "MissingIdea: idea #9999 not found" in str(exc_info.value)


def test_get_metrics_calculations() -> None:
    _call("record_idea", project="Orquestra", title="Idea 1", category="feature", priority="high")
    rec2 = _call("record_idea", project="Orquestra", title="Idea 2", category="bug", priority="critical")
    rec3 = _call("record_idea", project="OtherProject", title="Idea 3", category="ux", priority="low")

    # Complete Idea 2
    _call("update_idea_status", idea_id=rec2.structured_content["id"], status="completed")

    metrics_all = _call("get_metrics")
    assert metrics_all.is_error is False
    data = metrics_all.structured_content
    assert data["total"] == 3
    assert data["status_breakdown"]["completed"] == 1
    assert data["status_breakdown"]["open"] == 2
    assert data["category_breakdown"]["feature"] == 1
    assert data["category_breakdown"]["bug"] == 1
    assert data["priority_breakdown"]["critical"] == 1
    assert data["completion_rate"] == 0.3333
    assert data["weekly_velocity"]["this_week"] == 1

    # Filter by project
    metrics_orq = _call("get_metrics", project="Orquestra")
    assert metrics_orq.is_error is False
    orq_data = metrics_orq.structured_content
    assert orq_data["total"] == 2
    assert orq_data["status_breakdown"]["completed"] == 1
    assert orq_data["status_breakdown"]["open"] == 1
    assert orq_data["completion_rate"] == 0.5


def test_granular_blackboard_operations() -> None:
    post_res = _call(
        "post_board_note",
        project="Orquestra",
        topic="sync",
        note="Meeting at 10",
        sender="planner",
    )
    note_id = post_res.structured_content["id"]

    # get_board_note
    note = _call("get_board_note", note_id=note_id)
    assert note.is_error is False
    assert note.structured_content["id"] == note_id
    assert note.structured_content["note"] == "Meeting at 10"
    assert note.structured_content["is_read"] is False

    # mark_board_note_read
    marked = _call("mark_board_note_read", note_id=note_id)
    assert marked.is_error is False
    assert marked.structured_content["is_read"] is True

    # delete_board_note
    deleted = _call("delete_board_note", note_id=note_id)
    assert deleted.is_error is False
    assert deleted.structured_content["deleted"] is True

    # get_board_note on deleted note should fail
    with pytest.raises(ToolError) as exc_info:
        _call("get_board_note", note_id=note_id)
    assert f"LookupError: blackboard note #{note_id} not found" in str(exc_info.value)
