"""Grok adapter: search docs, prompt history, search and read-only access."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from builders import snapshot, write_jsonl
from session_relay.adapters.grok import GrokAdapter

SESSION = "01a1497c-d117-7a51-91b1-9a38a37b69d1"
DISK_SESSION = "01a1575b-3bde-7100-9d9d-b28b6da6ab6c"


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


def make_disk_session(home: Path, project: str, session_id: str,
                      summary: dict, chat: list[dict], parent: str | None = None) -> Path:
    encoded = project.replace("/", "%2F")
    base = home / ".grok" / "sessions" / encoded
    directory = base / parent / "subagents" / session_id if parent else base / session_id
    directory.mkdir(parents=True, exist_ok=True)
    name = "meta.json" if parent else "summary.json"
    (directory / name).write_text(json.dumps(summary))
    write_jsonl(directory / "chat_history.jsonl", chat)
    return directory


def _summary(title: str, **extra) -> dict:
    return {"session_summary": title, **extra}


def _disk_chat() -> list[dict]:
    call = {"id": "call-1", "name": "read_file",
            "arguments": json.dumps({"target_file": "session_relay/grok.py"})}
    return [
        {"type": "system", "content": "system prompt"},
        {"type": "user", "content": [{"type": "text", "text": "audit the relay"}]},
        {"type": "assistant", "content": "Reading the adapter.", "tool_calls": [call]},
        {"type": "tool_result", "tool_call_id": "call-1", "content": "file body"},
        {"type": "assistant", "content": "Audit complete."},
    ]


def test_unindexed_session_folder_is_discovered(relay_home):
    make_grok(relay_home, _sessions())
    make_disk_session(
        relay_home,
        "/work/disk",
        DISK_SESSION,
        _summary("Disk-only audit", info={"cwd": "/work/disk"},
                 updated_at="2099-01-01T00:00:00Z", num_chat_messages=5,
                 session_kind="interactive"),
        _disk_chat(),
    )
    adapter = GrokAdapter(relay_home)
    detail = adapter.load_session(DISK_SESSION)
    assert detail is not None
    assert detail.summary.title == "Disk-only audit"
    assert detail.summary.project == "/work/disk"
    assert detail.summary.turns_count == 5
    assert detail.summary.session_kind == "interactive"
    assert [event.role for event in detail.events] == [
        "user", "assistant", "tool", "tool", "assistant",
    ]
    assert detail.events[2].tool == "read_file"
    assert "session_relay/grok.py" in detail.events[2].text
    assert detail.events[3].tool == "read_file" and "file body" in detail.events[3].text


def test_nested_subagent_folder_is_discovered(relay_home):
    sub_id = "01a1575b-3bde-7100-9d9d-b28b6da6ab6c-sub"
    directory = make_disk_session(
        relay_home,
        "/work/goal",
        sub_id,
        {"subagent_id": sub_id, "description": "goal achievement skeptic",
         "prompt": "Verify the objective.\nReturn a verdict.", "child_cwd": "/work/goal",
         "started_at": "2026-10-20T03:29:19Z", "completed_at": "2026-10-20T03:34:30Z", "turns": 1},
        [],
        parent="01a156bb-4935-7282-857f-9bdefa251fdd",
    )
    (directory / "output.json").write_text(json.dumps({"schema_version": 1, "output": "Refuted"}))
    adapter = GrokAdapter(relay_home)
    detail = adapter.load_session(sub_id)
    assert detail is not None
    assert detail.summary.title == "goal achievement skeptic"
    assert detail.summary.session_kind == "subagent"
    assert detail.summary.project == "/work/goal"
    assert detail.summary.updated_at == "2026-10-20T03:34:30Z"
    assert [(event.role, event.text) for event in detail.events] == [
        ("user", "Verify the objective. Return a verdict."),
        ("assistant", "Refuted"),
    ]


def test_list_merges_and_dedupes_disk_sessions(relay_home):
    make_grok(relay_home, _sessions())
    make_disk_session(
        relay_home, "/work/disk", DISK_SESSION,
        _summary("Disk audit", updated_at="2099-01-01T00:00:00Z"), _disk_chat(),
    )
    make_disk_session(relay_home, "/work/grok", SESSION, _summary("Disk duplicate"), [])
    sessions = GrokAdapter(relay_home).list_sessions(limit=10)
    assert [session.session_id for session in sessions] == [
        DISK_SESSION, SESSION, "older-session-000000000000000000",
    ]
    assert sessions[0].turns_count == 1  # counted from chat_history when summary omits it
    assert sessions[1].title == "Deploy pipeline review"


def test_disk_sessions_are_never_modified(relay_home):
    make_disk_session(
        relay_home, "/work/disk", DISK_SESSION, _summary("Read only"), _disk_chat()
    )
    before = snapshot(relay_home)
    adapter = GrokAdapter(relay_home)
    adapter.list_sessions()
    assert adapter.load_session(DISK_SESSION) is not None
    assert snapshot(relay_home) == before


def test_symlinked_session_outside_the_store_is_refused(relay_home):
    outside = relay_home.parent / "outside"
    outside.mkdir()
    (outside / "summary.json").write_text(json.dumps({"session_summary": "Escaped"}))
    project = relay_home / ".grok" / "sessions" / "%2Fwork%2Flink"
    project.mkdir(parents=True)
    try:
        os.symlink(outside, project / DISK_SESSION, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable on this filesystem")
    adapter = GrokAdapter(relay_home)
    assert adapter.load_session(DISK_SESSION) is None
    assert DISK_SESSION not in [session.session_id for session in adapter.list_sessions(10)]
