"""Map OpenCode message/part rows into relay events."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..models import Event
from ..paths import clip, iso_from_epoch_ms


def parse(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def events_for_session(conn: sqlite3.Connection, session_id: str) -> list[Event]:
    """Walk messages and their parts in time order."""
    events: list[Event] = []
    messages = conn.execute(
        "SELECT id, data, time_created FROM message "
        "WHERE session_id = ? ORDER BY time_created ASC",
        (session_id,),
    ).fetchall()
    for message in messages:
        role = parse(message["data"]).get("role", "assistant")
        parts = conn.execute(
            "SELECT data, time_created FROM part WHERE message_id = ? "
            "ORDER BY time_created ASC",
            (message["id"],),
        ).fetchall()
        for part in parts:
            data = parse(part["data"])
            kind = data.get("type")
            stamp = iso_from_epoch_ms(part["time_created"] or message["time_created"])
            if kind == "text" and data.get("text"):
                events.append(
                    Event(
                        role if role in ("user", "assistant") else "assistant",
                        clip(data["text"], 900),
                        timestamp=stamp,
                    )
                )
            elif kind == "tool":
                state = data.get("state") or {}
                status = str(state.get("status") or "completed")
                args = json.dumps(state.get("input") or {}, ensure_ascii=False)
                output = state.get("output") or state.get("error") or ""
                events.append(
                    Event(
                        "tool",
                        clip(f"{args}\n{output}", 900),
                        tool=str(data.get("tool") or "tool"),
                        timestamp=stamp,
                        error=status == "error",
                    )
                )
            elif kind == "patch":
                files = data.get("files") or []
                events.append(
                    Event(
                        "tool",
                        clip("files: " + ", ".join(map(str, files)), 900),
                        tool="patch",
                        timestamp=stamp,
                    )
                )
    return events


def matching_parts(
    conn: sqlite3.Connection, needle: str, limit: int
) -> list[sqlite3.Row]:
    """Newest parts whose JSON payload contains the needle."""
    return conn.execute(
        "SELECT p.session_id, p.data, s.title, s.time_updated "
        "FROM part p JOIN session s ON s.id = p.session_id "
        "WHERE p.data LIKE ? ORDER BY p.time_created DESC LIMIT ?",
        (f"%{needle}%", limit),
    ).fetchall()
