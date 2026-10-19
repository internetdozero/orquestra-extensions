"""Builders that mimic each harness's on-disk session store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")


def make_codex(home: Path, threads: list[dict[str, Any]]) -> Path:
    db = home / ".codex" / "thread_history_1.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE thread_turns (
            thread_id TEXT, turn_id TEXT, status TEXT, error_json TEXT,
            started_at INTEGER, completed_at INTEGER, duration_ms INTEGER
        );
        CREATE TABLE thread_items (
            thread_id TEXT, turn_id TEXT, item_id TEXT, rollout_ordinal INTEGER,
            created_at_ms INTEGER, item_json TEXT, item_type TEXT
        );
        """
    )
    for thread in threads:
        for index, item in enumerate(thread["items"]):
            conn.execute(
                "INSERT INTO thread_items VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    thread["id"],
                    item.get("turn_id", "turn-1"),
                    f"item-{index}",
                    index,
                    item["ms"],
                    json.dumps(item["json"]),
                    item["type"],
                ),
            )
        for turn in thread.get("turns", []):
            conn.execute(
                "INSERT INTO thread_turns VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    thread["id"],
                    turn["turn_id"],
                    turn.get("status", "completed"),
                    json.dumps(turn["error"]) if turn.get("error") else None,
                    turn["started_at"],
                    turn.get("completed_at", turn["started_at"]),
                    turn.get("duration_ms", 0),
                ),
            )
        if thread.get("cwd"):
            rollout = home / ".codex/sessions/2026/10/17" / f"rollout-{thread['id']}.jsonl"
            write_jsonl(
                rollout,
                [{"type": "session_meta", "payload": {"id": thread["id"], "cwd": thread["cwd"]}}],
            )
    conn.commit()
    conn.close()
    return db


def make_claude(
    home: Path, project: str, session_id: str, records: list[dict[str, Any]]
) -> Path:
    path = home / ".claude" / "projects" / project / f"{session_id}.jsonl"
    write_jsonl(path, records)
    return path


def make_antigravity(home: Path, session_id: str, records: list[dict[str, Any]]) -> Path:
    path = (
        home
        / ".gemini/antigravity/brain"
        / session_id
        / ".system_generated/logs/transcript.jsonl"
    )
    write_jsonl(path, records)
    return path


def make_opencode(home: Path, sessions: list[dict[str, Any]]) -> Path:
    db = home / ".local/share/opencode/opencode.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE session (
            id TEXT PRIMARY KEY, project_id TEXT, parent_id TEXT, title TEXT,
            directory TEXT, time_created INTEGER, time_updated INTEGER
        );
        CREATE TABLE message (
            id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER,
            time_updated INTEGER, data TEXT
        );
        CREATE TABLE part (
            id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT,
            time_created INTEGER, time_updated INTEGER, data TEXT
        );
        """
    )
    for session in sessions:
        conn.execute(
            "INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session["id"],
                "global",
                None,
                session["title"],
                session.get("directory", "/work/proj"),
                session["created"],
                session["updated"],
            ),
        )
        for m_index, message in enumerate(session["messages"]):
            message_id = f"{session['id']}-m{m_index}"
            conn.execute(
                "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
                (
                    message_id,
                    session["id"],
                    session["created"] + m_index,
                    session["created"] + m_index,
                    json.dumps({"role": message["role"]}),
                ),
            )
            for p_index, part in enumerate(message.get("parts", [])):
                conn.execute(
                    "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        f"{message_id}-p{p_index}",
                        message_id,
                        session["id"],
                        session["created"] + m_index,
                        session["created"] + m_index,
                        json.dumps(part),
                    ),
                )
    conn.commit()
    conn.close()
    return db


def make_freebuff(
    home: Path, project: str, session_id: str, messages: list[dict[str, Any]]
) -> Path:
    chat = home / ".config/manicode/projects" / project / "chats" / session_id
    path = chat / "chat-messages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(messages))
    users = [message for message in messages if message.get("variant") == "user"]
    (chat / "chat-meta.json").write_text(
        json.dumps(
            {
                "messageCount": len(messages),
                "firstPrompt": users[0]["content"] if users else "",
                "messagesMtimeMs": 1790000300000,
            }
        )
    )
    return path


def make_freebuff_history(home: Path, prompts: list[str]) -> Path:
    path = home / ".config/manicode/message-history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prompts))
    return path


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Fingerprint every file under a fixture root."""
    return {
        str(path): (path.stat().st_mtime_ns, path.stat().st_size)
        for path in root.rglob("*")
        if path.is_file()
    }
