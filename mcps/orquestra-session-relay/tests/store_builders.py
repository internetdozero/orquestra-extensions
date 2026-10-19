"""Builders for the kilo, copilot and hermes fixture stores."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def make_kilo(home: Path, sessions: list[dict[str, Any]]) -> Path:
    """Kilo shares the OpenCode session/message/part schema."""
    db = home / ".local/share/kilo/kilo.db"
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
                "proj-1",
                None,
                session["title"],
                session.get("directory", "/work/kilo"),
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


def make_copilot(home: Path, sessions: list[dict[str, Any]]) -> Path:
    db = home / ".copilot" / "session-store.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY, cwd TEXT, repository TEXT, host_type TEXT,
            branch TEXT, summary TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            turn_index INTEGER NOT NULL, user_message TEXT,
            assistant_response TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            UNIQUE(session_id, turn_index)
        );
        """
    )
    for session in sessions:
        conn.execute(
            "INSERT INTO sessions (id, cwd, repository, summary, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                session["id"],
                session.get("cwd", "/work/copilot"),
                session.get("repository", ""),
                session.get("summary", ""),
                session.get("created", "2026-10-18T10:00:00Z"),
                session.get("updated", "2026-10-19T10:00:00Z"),
            ),
        )
        for index, turn in enumerate(session.get("turns", [])):
            conn.execute(
                "INSERT INTO turns (session_id, turn_index, user_message,"
                " assistant_response, timestamp) VALUES (?, ?, ?, ?, ?)",
                (
                    session["id"],
                    index,
                    turn.get("user", ""),
                    turn.get("assistant", ""),
                    turn.get("timestamp", "2026-10-19T10:00:00Z"),
                ),
            )
    conn.commit()
    conn.close()
    return db


def make_hermes(home: Path, sessions: list[dict[str, Any]]) -> Path:
    db = home / ".hermes" / "state.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY, display_name TEXT,
            started_at REAL NOT NULL, ended_at REAL, message_count INTEGER DEFAULT 0
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT, tool_name TEXT,
            timestamp REAL NOT NULL
        );
        """
    )
    for session in sessions:
        conn.execute(
            "INSERT INTO sessions (id, display_name, started_at, ended_at, message_count)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                session["id"],
                session.get("title", ""),
                session.get("started", 1_790_000_000.0),
                session.get("ended", 1_790_000_100.0),
                len(session.get("messages", [])),
            ),
        )
        for message in session.get("messages", []):
            conn.execute(
                "INSERT INTO messages (session_id, role, content, tool_name, timestamp)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    session["id"],
                    message["role"],
                    message.get("content", ""),
                    message.get("tool"),
                    message.get("timestamp", 1_790_000_050.0),
                ),
            )
    conn.commit()
    conn.close()
    return db


