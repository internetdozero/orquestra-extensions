"""Codex adapter: discovery, event extraction, search and read-only access."""

from __future__ import annotations

from builders import make_codex, snapshot
from session_relay.adapters.codex import CodexAdapter


def _threads() -> list[dict]:
    base = 1_790_000_000_000
    return [
        {
            "id": "01a149b1-184d-7172-a7b5-3f0f00000001",
            "cwd": "/work/orquestra",
            "turns": [
                {
                    "turn_id": "turn-1",
                    "status": "failed",
                    "error": {"message": "npm test failed"},
                    "started_at": 1_790_000_201,
                    "completed_at": 1_790_000_210,
                }
            ],
            "items": [
                {
                    "type": "userMessage",
                    "ms": base,
                    "json": {
                        "type": "userMessage",
                        "content": [{"type": "text", "text": "Optimize the deploy pipeline"}],
                    },
                },
                {
                    "type": "commandExecution",
                    "ms": base + 1_000,
                    "json": {
                        "type": "commandExecution",
                        "command": "npm test",
                        "aggregatedOutput": "FAIL deploy.test.ts",
                        "exitCode": 1,
                    },
                },
                {
                    "type": "fileChange",
                    "ms": base + 2_000,
                    "json": {"changes": [{"path": "/work/orquestra/deploy.ts"}]},
                },
                {
                    "type": "mcpToolCall",
                    "ms": base + 3_000,
                    "json": {
                        "server": "playwright",
                        "tool": "click",
                        "arguments": {},
                        "error": "timeout",
                    },
                },
                {
                    "type": "agentMessage",
                    "ms": base + 4_000,
                    "json": {"type": "agentMessage", "text": "Deploy timing fixed"},
                },
            ],
        },
        {
            "id": "01a14981-7d16-77d2-93d1-382eed000002",
            "turns": [
                {
                    "turn_id": "turn-2",
                    "started_at": 1_790_000_000,
                    "completed_at": 1_790_000_005,
                }
            ],
            "items": [
                {
                    "type": "userMessage",
                    "ms": base - 60_000,
                    "json": {
                        "type": "userMessage",
                        "content": [{"type": "text", "text": "Tray icon alignment"}],
                    },
                }
            ],
        },
    ]


def test_lists_sessions_with_metadata(relay_home):
    make_codex(relay_home, _threads())
    sessions = CodexAdapter(relay_home).list_sessions(limit=5)
    assert [session.session_id[:13] for session in sessions] == [
        "01a149b1-184d",
        "01a14981-7d16",
    ]
    newest = sessions[0]
    assert newest.title == "Optimize the deploy pipeline"
    assert newest.turns_count == 1
    assert newest.project == "/work/orquestra"
    assert newest.harness == "codex"


def test_load_latest_session_and_turn_limit(relay_home):
    make_codex(relay_home, _threads())
    adapter = CodexAdapter(relay_home)
    detail = adapter.load_session("latest", max_turns=10)
    assert detail is not None
    roles = [event.role for event in detail.events]
    assert roles[:2] == ["user", "tool"]
    assert "assistant" in roles and "system" in roles
    shell = next(event for event in detail.events if event.tool == "shell")
    assert shell.error is True
    assert "FAIL deploy.test.ts" in shell.text
    assert any(event.error and "npm test failed" in event.text for event in detail.events)

    older = adapter.load_session(_threads()[1]["id"], max_turns=1)
    assert older is not None
    assert [event.role for event in older.events] == ["user"]


def test_search_matches_messages(relay_home):
    make_codex(relay_home, _threads())
    adapter = CodexAdapter(relay_home)
    hits = adapter.search("deploy")
    assert len(hits) == 1
    assert hits[0].session_id.startswith("01a149b1")
    assert "deploy" in hits[0].snippet.lower()
    assert adapter.search("nothing-here") == []


def test_store_is_never_modified(relay_home):
    make_codex(relay_home, _threads())
    before = snapshot(relay_home)
    adapter = CodexAdapter(relay_home)
    adapter.list_sessions()
    adapter.load_session("latest")
    adapter.search("deploy")
    assert snapshot(relay_home) == before


def test_missing_store_is_friendly(relay_home):
    adapter = CodexAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
    assert adapter.search("anything") == []
