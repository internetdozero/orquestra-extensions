"""Tests for session export, retention policy, purge and safe deletion."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from builders import make_claude, make_codex
from session_relay import policy
from session_relay.server import server


def _call(name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(server.call_tool(name, arguments))


def test_retention_policy_roundtrip(relay_home: Path) -> None:
    pol = _call("get_retention_policy", {})
    assert pol.is_error is False
    assert pol.structured_content["defaultTtlDays"] == 30
    assert pol.structured_content["autoPurgeEnabled"] is False

    updated = _call(
        "set_retention_policy",
        {
            "default_ttl_days": 15,
            "auto_purge_enabled": True,
            "interval_hours": 12,
            "harness_overrides": {"claude": 7},
        },
    )
    assert updated.is_error is False
    data = updated.structured_content
    assert data["defaultTtlDays"] == 15
    assert data["autoPurgeEnabled"] is True
    assert data["intervalHours"] == 12
    assert data["harnessOverrides"]["claude"] == 7


def test_export_session_markdown_and_json(relay_home: Path) -> None:
    make_claude(
        relay_home,
        "my-proj",
        "sess-123",
        [
            {
                "type": "user",
                "timestamp": "2026-10-17T11:00:00.000Z",
                "message": {"role": "user", "content": "Fix tests"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-10-17T11:00:05.000Z",
                "message": {"role": "assistant", "content": "Running pytest"},
            },
        ],
    )

    # Markdown export
    md_res = _call("export_session", {"harness": "claude", "session_id": "sess-123", "format": "markdown"})
    assert md_res.is_error is False
    content = md_res.structured_content["content"]
    assert "---" in content
    assert "id: sess-123" in content
    assert "### User" in content
    assert "Fix tests" in content
    assert "### Assistant" in content

    # JSON export
    json_res = _call("export_session", {"harness": "claude", "session_id": "sess-123", "format": "json"})
    assert json_res.is_error is False
    assert json_res.structured_content["format"] == "json"

    # Export to output_path
    dest = relay_home / "exported_session.md"
    write_res = _call(
        "export_session",
        {"harness": "claude", "session_id": "sess-123", "format": "markdown", "output_path": str(dest)},
    )
    assert write_res.is_error is False
    assert write_res.structured_content["written"] is True
    assert dest.exists()
    assert "Fix tests" in dest.read_text()


def test_delete_and_purge_with_pin_guard(relay_home: Path) -> None:
    make_claude(
        relay_home,
        "my-proj",
        "sess-to-delete",
        [
            {
                "type": "user",
                "timestamp": "2026-10-17T11:00:00.000Z",
                "message": {"role": "user", "content": "Temporary session"},
            }
        ],
    )

    # Pin the session
    _call("pin_session", {"harness": "claude", "session_id": "sess-to-delete", "label": "Important"})

    # Delete without force should fail
    with pytest.raises(ToolError) as exc_info:
        _call("delete_session", {"harness": "claude", "session_id": "sess-to-delete", "force": False})
    assert "pinned" in str(exc_info.value)

    # Purge estimate should skip pinned session
    est = _call("estimate_purge", {"harness": "claude", "older_than_days": 0})
    assert est.is_error is False
    assert est.structured_content["skipped_pins_count"] == 1
    assert est.structured_content["candidates_count"] == 0

    # Delete with force should succeed
    deleted = _call("delete_session", {"harness": "claude", "session_id": "sess-to-delete", "force": True})
    assert deleted.is_error is False
    assert deleted.structured_content["deleted"] is True


def test_search_sessions_history_enhanced(relay_home: Path) -> None:
    make_claude(
        relay_home,
        "frontend-proj",
        "sess-search-1",
        [
            {
                "type": "user",
                "timestamp": "2026-10-17T11:00:00.000Z",
                "message": {"role": "user", "content": "Refactor navigation navbar"},
            }
        ],
    )

    # Title / metadata search (search_content=False)
    res_meta = _call("search_sessions_history", {"query": "sess-search-1", "search_content": False})
    assert res_meta.is_error is False
    assert res_meta.structured_content["count"] >= 1

    # Content search (search_content=True)
    res_content = _call("search_sessions_history", {"query": "navbar", "search_content": True})
    assert res_content.is_error is False
    assert res_content.structured_content["count"] >= 1
