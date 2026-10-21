"""Tool schemas publish closed vocabularies and failures stay actionable."""

from __future__ import annotations

import asyncio
from typing import Any, get_args

import pytest
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from idea_vault import server
from idea_vault.schema import Category, Priority, Status, StatusFilter
from idea_vault.store import CATEGORIES, PRIORITIES, STATUSES


def _schema(name: str) -> dict[str, Any]:
    tools = asyncio.run(server.server.list_tools())
    return next(tool.input_schema for tool in tools if tool.name == name)


def _enum(prop: dict[str, Any]) -> list[str]:
    """Read the enum of a property, whether direct or inside an ``anyOf``."""
    if "enum" in prop:
        return list(prop["enum"])
    for branch in prop.get("anyOf", []):
        if "enum" in branch:
            return list(branch["enum"])
    raise AssertionError(f"no enum in {prop}")


def _call(name: str, **arguments: Any) -> Any:
    """Invoke a tool through the public MCP path, as a client would."""
    return asyncio.run(server.server.call_tool(name, arguments))


def test_literals_mirror_the_storage_vocabularies() -> None:
    assert get_args(Category) == CATEGORIES
    assert get_args(Priority) == PRIORITIES
    assert get_args(Status) == STATUSES
    assert get_args(StatusFilter) == (*STATUSES, "all")


def test_record_idea_publishes_every_enum() -> None:
    properties = _schema("record_idea")["properties"]
    assert _enum(properties["category"]) == list(CATEGORIES)
    assert _enum(properties["priority"]) == list(PRIORITIES)


def test_update_idea_publishes_optional_enums() -> None:
    properties = _schema("update_idea")["properties"]
    assert _enum(properties["category"]) == list(CATEGORIES)
    assert _enum(properties["priority"]) == list(PRIORITIES)


def test_list_and_status_tools_publish_their_enums() -> None:
    assert _enum(_schema("list_ideas")["properties"]["status"]) == [*STATUSES, "all"]
    assert _enum(_schema("list_ideas")["properties"]["category"]) == list(CATEGORIES)
    assert _enum(_schema("update_idea_status")["properties"]["status"]) == list(STATUSES)


def test_batch_items_publish_the_same_enums() -> None:
    schema = _schema("record_ideas_batch")
    item = schema["$defs"]["IdeaInput"]["properties"]
    assert _enum(item["category"]) == list(CATEGORIES)
    assert _enum(item["priority"]) == list(PRIORITIES)
    assert _enum(item["status"]) == list(STATUSES)


def test_prompt_publishes_the_builder_dispatch_contract() -> None:
    expected = (
        "Compact English Builder dispatch prompt (Mission, Workspace, Targets, "
        "Scope, Idea Vault Lifecycle hooks, Verification). Avoid redundant guardrails."
    )
    for tool in ("record_idea", "update_idea"):
        assert _schema(tool)["properties"]["prompt"]["description"] == expected

    item = _schema("record_ideas_batch")["$defs"]["IdeaInput"]
    assert item["properties"]["prompt"]["description"] == expected


def test_invalid_category_names_the_accepted_values() -> None:
    with pytest.raises(ToolError) as caught:
        _call("record_idea", project="OrquestraAI", title="x", category="nope")
    message = str(caught.value)
    assert "category" in message
    assert "'architecture'" in message and "'idea'" in message


def test_invalid_priority_on_update_names_priority() -> None:
    with pytest.raises(ToolError) as caught:
        _call("update_idea", idea_id=1, priority="urgent")
    message = str(caught.value)
    assert "priority" in message
    assert "'medium'" in message and "'critical'" in message


def test_invalid_transition_names_every_status() -> None:
    with pytest.raises(ToolError) as caught:
        _call("update_idea_status", idea_id=1, status="done")
    message = str(caught.value)
    assert "'open'" in message and "'in_progress'" in message
    assert "'completed'" in message and "'archived'" in message


def test_invalid_batch_item_points_at_the_offending_index() -> None:
    with pytest.raises(ToolError) as caught:
        _call(
            "record_ideas_batch",
            project="OrquestraAI",
            items=[{"title": "ok"}, {"title": "bad", "status": "resolved"}],
        )
    message = str(caught.value)
    assert "items.1.status" in message
    assert "'archived'" in message


def test_empty_title_keeps_its_domain_message(db_path) -> None:
    with pytest.raises(ToolError) as caught:
        _call("record_idea", project="OrquestraAI", title="   ")
    assert "title must be a non-empty string" in str(caught.value)


def test_missing_idea_reports_the_id(db_path) -> None:
    with pytest.raises(ToolError) as caught:
        _call("update_idea_status", idea_id=999, status="completed")
    assert "idea #999 not found" in str(caught.value)


def test_unexpected_failure_is_still_a_crash(db_path, monkeypatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(server.ideas, "record_idea", boom)
    with pytest.raises(UnexpectedToolError) as caught:
        _call("record_idea", project="OrquestraAI", title="x")
    assert "disk on fire" not in str(caught.value)


def test_valid_call_through_the_tool_path_persists(db_path) -> None:
    created = _call(
        "record_idea",
        project="OrquestraAI",
        title="Cache vault reads",
        category="architecture",
        priority="high",
        prompt="Add a cache layer in front of the vault reader.",
    )
    assert created.structured_content is not None
    assert created.structured_content["category"] == "architecture"
    assert created.structured_content["priority"] == "high"

    listed = _call("list_ideas", project="OrquestraAI")
    assert listed.structured_content["count"] == 1
    assert listed.structured_content["ideas"][0]["prompt"].startswith("Add a cache")


def test_batch_items_accept_defaults_and_prompt(db_path) -> None:
    batch = _call(
        "record_ideas_batch",
        project="OrquestraAI",
        items=[
            {"title": "first"},
            {"title": "second", "status": "completed", "prompt": "ship it"},
        ],
    )
    ideas = batch.structured_content["ideas"]
    assert [idea["status"] for idea in ideas] == ["open", "completed"]
    assert ideas[1]["prompt"] == "ship it"
    assert ideas[1]["completed_at"] is not None
