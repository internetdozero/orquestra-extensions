"""Published search constraints and tool errors that name the cause."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from web_search import env_file, exa_search, server


def _schema() -> dict[str, Any]:
    tools = asyncio.run(server.server.list_tools())
    return next(tool.input_schema for tool in tools if tool.name == "web_search")


def _call(**arguments: Any) -> Any:
    return asyncio.run(server.server.call_tool("web_search", arguments))


def test_schema_publishes_the_result_bounds() -> None:
    num_results = _schema()["properties"]["num_results"]
    assert num_results["minimum"] == 1
    assert num_results["maximum"] == exa_search.MAX_NUM_RESULTS


def test_schema_publishes_the_date_pattern() -> None:
    published = _schema()["properties"]["start_published_date"]
    patterns = [branch.get("pattern") for branch in published["anyOf"]]
    assert r"^\d{4}-\d{2}-\d{2}$" in patterns


def test_schema_requires_a_non_empty_query() -> None:
    query = _schema()["properties"]["query"]
    assert query["minLength"] == 1
    assert _schema()["required"] == ["query"]


def test_too_many_results_is_rejected_before_exa() -> None:
    with pytest.raises(ToolError) as caught:
        _call(query="exa highlights", num_results=exa_search.MAX_NUM_RESULTS + 1)
    message = str(caught.value)
    assert "num_results" in message
    assert f"less than or equal to {exa_search.MAX_NUM_RESULTS}" in message


def test_malformed_date_is_rejected_with_the_expected_shape() -> None:
    with pytest.raises(ToolError) as caught:
        _call(query="exa highlights", start_published_date="last week")
    message = str(caught.value)
    assert "start_published_date" in message
    assert "YYYY-MM-DD" in message or "pattern" in message


def test_missing_key_is_a_tool_error_with_the_fix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(exa_search.ENV_VAR, raising=False)
    monkeypatch.setattr(env_file, "candidates", lambda: [])

    with pytest.raises(ToolError) as caught:
        _call(query="exa highlights")
    message = str(caught.value)
    assert f"{exa_search.ENV_VAR} is not set" in message
    assert ".env" in message


def test_search_failure_keeps_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken:
        def search(self, query: str, **options: Any) -> Any:
            raise ValueError("Request failed with status code 429: slow down")

    monkeypatch.setattr(exa_search, "client", lambda searcher=None: Broken())

    with pytest.raises(ToolError) as caught:
        _call(query="exa highlights")
    message = str(caught.value)
    assert "rate limit" in message
    assert "429" in message


def test_valid_search_through_the_tool_path(monkeypatch: pytest.MonkeyPatch) -> None:
    class Fake:
        def search(self, query: str, **options: Any) -> Any:
            row = SimpleNamespace(
                url="https://example.com/durable-objects",
                title="Durable Objects",
                published_date="2026-01-02",
                author="Cloudflare",
                highlights=["alarms wake the object"],
            )
            return SimpleNamespace(results=[row])

    monkeypatch.setattr(exa_search, "client", lambda searcher=None: Fake())

    result = _call(query="durable objects", num_results=3)
    assert result.is_error is False
    assert result.structured_content["count"] == 1
    assert result.structured_content["results"][0]["url"].startswith("https://")
