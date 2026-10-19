"""Server wiring: tool registry and end-to-end calls over fixture stores."""

from __future__ import annotations

import asyncio

from builders import make_codex
from session_relay.server import server

TOOLS = [
    "list_recent_sessions",
    "inspect_session",
    "handoff_context",
    "search_sessions_history",
    "watch_active_agent",
    "tail_agent_activity",
]


def _call(name, arguments):
    return asyncio.run(server.call_tool(name, arguments))


def _seed(home):
    base = 1_790_000_000_000
    make_codex(
        home,
        [
            {
                "id": "thread-abc",
                "cwd": "/work/proj",
                "turns": [{"turn_id": "turn-1", "started_at": 1_790_000_010}],
                "items": [
                    {
                        "type": "userMessage",
                        "ms": base,
                        "json": {
                            "type": "userMessage",
                            "content": [{"type": "text", "text": "Ship the deploy fix"}],
                        },
                    },
                    {
                        "type": "commandExecution",
                        "ms": base + 500,
                        "json": {
                            "type": "commandExecution",
                            "command": "npm test",
                            "aggregatedOutput": "FAIL deploy.test.ts",
                            "exitCode": 1,
                        },
                    },
                    {
                        "type": "agentMessage",
                        "ms": base + 900,
                        "json": {"type": "agentMessage", "text": "Deploy fix is staged"},
                    },
                ],
            }
        ],
    )


def test_all_four_tools_are_registered():
    tools = asyncio.run(server.list_tools())
    assert [tool.name for tool in tools] == TOOLS


def test_list_inspect_search_and_handoff(relay_home):
    _seed(relay_home)

    listed = _call("list_recent_sessions", {"limit": 5})
    assert listed.structured_content["count"] == 1
    session = listed.structured_content["sessions"][0]
    assert session["harness"] == "codex"
    assert session["session_id"] == "thread-abc"
    assert session["project"] == "/work/proj"

    inspected = _call("inspect_session", {"harness": "codex", "max_turns": 3})
    assert inspected.structured_content["event_count"] >= 3
    assert inspected.structured_content["harness"] == "codex"

    brief = _call("handoff_context", {"source_harness": "codex"})
    markdown = brief.content[0].text
    assert markdown.startswith("# Handoff — codex · thread-abc")
    assert "Ship the deploy fix" in markdown
    assert "## Blocker" in markdown

    found = _call("search_sessions_history", {"query": "deploy"})
    assert found.structured_content["count"] >= 1
    assert found.structured_content["hits"][0]["harness"] == "codex"


def test_empty_and_invalid_states_are_friendly(relay_home):
    empty = _call("list_recent_sessions", {"harness": "claude"})
    assert empty.structured_content["count"] == 0
    assert any("no session store" in warning for warning in empty.structured_content["warnings"])

    unknown = _call("list_recent_sessions", {"harness": "nope"})
    assert "unknown harness" in unknown.structured_content["error"]

    missing = _call("inspect_session", {"harness": "codex"})
    assert "no OpenAI Codex session store" in missing.structured_content["error"]

    no_session = _call(
        "handoff_context", {"source_harness": "codex", "session_id": "missing"}
    )
    assert no_session.content[0].text.startswith("# Handoff unavailable")
