"""Grok adapter: search docs, prompt history, search and read-only access."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from builders import snapshot, write_jsonl
from session_relay.adapters.grok import GrokAdapter

SESSION = "01a1497c-d117-7a51-91b1-9a38a37b69d1"


def make_grok(home: Path, sessions: list[dict]) -> Path:
    root = home / ".grok" / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    db = root / "session_search.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE session_docs (session_id TEXT, cwd TEXT, updated_at INTEGER, "
        "title TEXT, content TEXT, content_hash TEXT)"
    )
    for session in sessions:
        conn.execute(
            "INSERT INTO session_docs VALUES (?, ?, ?, ?, ?, ?)",
            (
                session["id"],
                session.get("cwd", "/work/grok"),
                session["updated"],
                session.get("title", ""),
                session.get("content", ""),
                "hash",
            ),
        )
        if session.get("prompts"):
            encoded = str(session.get("cwd", "/work/grok")).replace("/", "%2F")
            write_jsonl(
                root / encoded / "prompt_history.jsonl",
                [
                    {
                        "timestamp": prompt["timestamp"],
                        "session_id": session["id"],
                        "prompt": prompt["text"],
                        "is_bash": False,
                    }
                    for prompt in session["prompts"]
                ],
            )
    conn.commit()
    conn.close()
    return db


def _sessions() -> list[dict]:
    return [
        {
            "id": SESSION,
            "cwd": "/work/grok",
            "updated": 1_790_004_512,
            "title": "Deploy pipeline review",
            "content": "review the deploy pipeline\n\nwhy did the build fail?",
            "prompts": [
                {"timestamp": "2026-10-17T10:00:00Z", "text": "review the deploy pipeline"},
                {"timestamp": "2026-10-17T10:05:00Z", "text": "why did the build fail?"},
            ],
        },
        {
            "id": "older-session-000000000000000000",
            "updated": 1_790_000_000,
            "content": "unrelated question",
        },
    ]


def test_lists_sessions_from_search_docs(relay_home):
    make_grok(relay_home, _sessions())
    sessions = GrokAdapter(relay_home).list_sessions()
    assert [session.title for session in sessions] == [
        "Deploy pipeline review",
        "Grok session older-se",
    ]
    assert sessions[0].turns_count == 2
    assert sessions[0].project == "/work/grok"
    assert sessions[0].harness == "grok"


def test_loads_prompts_and_limits_turns(relay_home):
    make_grok(relay_home, _sessions())
    adapter = GrokAdapter(relay_home)
    detail = adapter.load_session("latest")
    assert detail is not None
    assert [event.role for event in detail.events] == ["user", "user"]
    assert detail.events[0].text == "review the deploy pipeline"
    limited = adapter.load_session(SESSION, max_turns=1)
    assert limited is not None
    assert [event.text for event in limited.events] == ["why did the build fail?"]


def test_search_matches_content(relay_home):
    make_grok(relay_home, _sessions())
    adapter = GrokAdapter(relay_home)
    hits = adapter.search("deploy")
    assert hits and hits[0].session_id == SESSION
    assert adapter.search("unrelated")[0].session_id.startswith("older")
    assert adapter.search("nothing") == []


def test_store_is_never_modified(relay_home):
    make_grok(relay_home, _sessions())
    before = snapshot(relay_home)
    adapter = GrokAdapter(relay_home)
    adapter.list_sessions()
    adapter.load_session("latest")
    adapter.search("deploy")
    assert snapshot(relay_home) == before


def test_missing_store_is_friendly(relay_home):
    adapter = GrokAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
    assert adapter.search("x") == []
