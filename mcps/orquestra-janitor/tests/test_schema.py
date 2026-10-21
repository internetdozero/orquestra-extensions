"""Published target vocabularies and failures that name the cause."""

from __future__ import annotations

import asyncio
from typing import Any, get_args

import pytest
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from janitor import caches, orphans, server, sweep
from janitor.schema import CacheTarget, SweepTarget


def _schema(name: str) -> dict[str, Any]:
    tools = asyncio.run(server.server.list_tools())
    return next(tool.input_schema for tool in tools if tool.name == name)


def _enum(prop: dict[str, Any]) -> list[str]:
    """Read the enum of a property, whether direct or inside an ``anyOf``."""
    for candidate in (prop, *prop.get("anyOf", [])):
        if "enum" in candidate:
            return list(candidate["enum"])
        items = candidate.get("items") or {}
        if "enum" in items:
            return list(items["enum"])
    raise AssertionError(f"no enum in {prop}")


def test_literals_mirror_the_module_vocabularies() -> None:
    assert get_args(SweepTarget) == sweep.TARGET_TYPES
    assert get_args(CacheTarget) == caches.DEFAULT_TARGETS


def test_sweep_schema_publishes_the_target_types() -> None:
    target = _schema("janitor_sweep_processes")["properties"]["target_type"]
    assert _enum(target) == list(sweep.TARGET_TYPES)


def test_clean_caches_schema_publishes_the_targets() -> None:
    targets = _schema("janitor_clean_caches")["properties"]["targets"]
    assert _enum(targets) == list(caches.DEFAULT_TARGETS)


def test_age_gate_minimum_is_published() -> None:
    age = _schema("janitor_clean_caches")["properties"]["older_than_hours"]
    assert age["minimum"] == 0


def test_invalid_target_type_names_the_options() -> None:
    with pytest.raises(ToolError) as caught:
        asyncio.run(
            server.server.call_tool(
                "janitor_sweep_processes", {"target_type": "zombies"}
            )
        )
    message = str(caught.value)
    assert "target_type" in message
    assert "'orphans'" in message and "'compilers'" in message


def test_invalid_cache_target_points_at_the_item() -> None:
    with pytest.raises(ToolError) as caught:
        asyncio.run(
            server.server.call_tool(
                "janitor_clean_caches", {"targets": ["sockets", "logs"]}
            )
        )
    message = str(caught.value)
    assert "targets.1" in message
    assert "'testing_scratch'" in message


def test_scan_failure_is_an_error_not_a_fake_row(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny() -> list[dict[str, Any]]:
        raise PermissionError("cannot read /proc")

    monkeypatch.setattr(orphans, "scan_orphans", deny)

    with pytest.raises(ToolError) as caught:
        asyncio.run(server.server.call_tool("janitor_scan_orphans", {}))
    assert "cannot read /proc" in str(caught.value)


def test_health_failure_keeps_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    from janitor import health

    def broken() -> dict[str, Any]:
        raise OSError("/proc/meminfo is unavailable")

    monkeypatch.setattr(health, "system_health", broken)

    with pytest.raises(ToolError) as caught:
        asyncio.run(server.server.call_tool("janitor_system_health", {}))
    assert "/proc/meminfo is unavailable" in str(caught.value)


def test_unexpected_runtime_error_is_still_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> dict[str, Any]:
        raise RuntimeError("programmer bug")

    monkeypatch.setattr(orphans, "scan_orphans", broken)

    with pytest.raises(UnexpectedToolError) as caught:
        asyncio.run(server.server.call_tool("janitor_scan_orphans", {}))
    assert "programmer bug" not in str(caught.value)


def test_sweep_dry_run_still_reports_through_the_tool() -> None:
    result = asyncio.run(
        server.server.call_tool(
            "janitor_sweep_processes", {"target_type": "orphans", "dry_run": True}
        )
    )
    assert result.is_error is False
    assert result.structured_content["dry_run"] is True
