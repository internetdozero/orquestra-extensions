"""Inter-agent blackboard: async notes between agents sharing one machine."""

from __future__ import annotations

import sqlite3
from typing import Any

from .serializers import note_dict
from .store import clamp_limit, require_text


def _filters(
    project: str, topic: str | None
) -> tuple[list[str], list[Any]]:
    clauses = ["project = ?"]
    params: list[Any] = [require_text(project, "project")]
    if topic:
        clauses.append("topic = ?")
        params.append(require_text(topic, "topic"))
    return clauses, params


def post_board_note(
    conn: sqlite3.Connection,
    project: str,
    topic: str,
    note: str,
    sender: str = "agent",
    target: str = "all",
) -> dict[str, Any]:
    """Append a collaboration note for other agents to pick up later."""
    cursor = conn.execute(
        "INSERT INTO blackboard_notes (project, topic, sender, target, note) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            require_text(project, "project"),
            require_text(topic, "topic").lower(),
            require_text(sender, "sender"),
            require_text(target, "target"),
            require_text(note, "note"),
        ),
    )
    row = conn.execute(
        "SELECT * FROM blackboard_notes WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    data = note_dict(row)
    data["message"] = f"Posted note #{data['id']} to {data['project']}/{data['topic']}."
    return data


def read_board_notes(
    conn: sqlite3.Connection,
    project: str,
    topic: str | None = None,
    unread_only: bool = True,
    mark_as_read: bool = False,
    target: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Read notes, optionally limited to one topic/target, and mark them read."""
    clauses, params = _filters(project, topic)
    if unread_only:
        clauses.append("is_read = 0")
    if target and target.strip().lower() != "all":
        clauses.append("(target = ? OR target = 'all')")
        params.append(require_text(target, "target"))
    rows = conn.execute(
        f"SELECT * FROM blackboard_notes WHERE {' AND '.join(clauses)} "
        "ORDER BY created_at ASC, id ASC LIMIT ?",
        (*params, clamp_limit(limit, 200)),
    ).fetchall()
    notes = [note_dict(row) for row in rows]
    if mark_as_read and notes:
        ids = [item["id"] for item in notes]
        placeholders = ", ".join("?" for _ in ids)
        conn.execute(
            f"UPDATE blackboard_notes SET is_read = 1 WHERE id IN ({placeholders})", ids
        )
        for item in notes:
            item["is_read"] = True
    return {"count": len(notes), "notes": notes}


def clear_board_notes(
    conn: sqlite3.Connection,
    project: str,
    topic: str | None = None,
    include_unread: bool = False,
) -> dict[str, Any]:
    """Delete handled notes (read ones only unless include_unread is set)."""
    clauses, params = _filters(project, topic)
    if not include_unread:
        clauses.append("is_read = 1")
    cursor = conn.execute(
        f"DELETE FROM blackboard_notes WHERE {' AND '.join(clauses)}", params
    )
    return {
        "deleted": cursor.rowcount,
        "scope": "all notes" if include_unread else "read notes",
        "message": f"Cleared {cursor.rowcount} note(s) from {project}"
        + (f"/{topic}" if topic else "")
        + ".",
    }


__all__ = ["post_board_note", "read_board_notes", "clear_board_notes"]
