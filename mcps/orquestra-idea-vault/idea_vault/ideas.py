"""Idea capture: create, list, search, transition and export ideas."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

from .serializers import dump_tags, idea_dict, load_tags, parse_tags
from .store import (
    ACTIVE_STATUSES,
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    optional_choice,
    require_choice,
    require_text,
)

PRIORITY_RANK = (
    "CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
    "WHEN 'medium' THEN 2 ELSE 3 END"
)
CATEGORY_TITLES = {
    "feature": "Features", "architecture": "Architecture",
    "bug": "Bugs", "ux": "UX", "idea": "Ideas",
}
COMPACT_FIELDS = (
    "id", "project", "title", "priority", "category", "status", "updated_at"
)


def record_idea(
    conn: sqlite3.Connection,
    project: str,
    title: str,
    description: str = "",
    category: str = "feature",
    priority: str = "medium",
    tags: Iterable[str] | str | None = None,
) -> dict[str, Any]:
    """Insert one idea and return the stored row with a confirmation message."""
    project = require_text(project, "project")
    title = require_text(title, "title")
    category = require_choice(category, CATEGORIES, "category")
    priority = require_choice(priority, PRIORITIES, "priority")
    cursor = conn.execute(
        "INSERT INTO ideas (project, title, description, category, priority, tags) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (project, title, str(description or "").strip(), category, priority, dump_tags(tags)),
    )
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (cursor.lastrowid,)).fetchone()
    data = idea_dict(row)
    data["message"] = f"Recorded idea #{data['id']} in {project} ({category}/{priority})."
    return data


def record_ideas_batch(
    conn: sqlite3.Connection,
    project: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bulk insert multiple ideas for a project in an atomic transaction."""
    project = require_text(project, "project")
    if not isinstance(items, (list, tuple)):
        raise ValueError("items must be a list of dictionaries")
    savepoint_name = "sp_record_ideas_batch"
    conn.execute(f"SAVEPOINT {savepoint_name}")
    recorded: list[dict[str, Any]] = []
    try:
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each item in items must be a dictionary")
            title = item.get("title")
            description = item.get("description", "")
            category = item.get("category") or "feature"
            priority = item.get("priority") or "medium"
            tags = item.get("tags")
            data = record_idea(
                conn,
                project=project,
                title=title,
                description=description,
                category=category,
                priority=priority,
                tags=tags,
            )
            recorded.append(data)
        conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
        raise

    return {
        "count": len(recorded),
        "project": project,
        "ideas": recorded,
        "message": f"Recorded {len(recorded)} ideas in {project}.",
    }


def list_ideas(
    conn: sqlite3.Connection,
    project: str | None = None,
    status: str = "open",
    category: str | None = None,
    priority: str | None = None,
    limit: int = 200,
    compact: bool = False,
) -> dict[str, Any]:
    """List ideas by project, status, category and priority, highest priority first."""
    clauses: list[str] = []
    params: list[Any] = []
    if project:
        clauses.append("project = ?")
        params.append(require_text(project, "project"))
    status_filter = optional_choice(status, STATUSES, "status")
    if status_filter:
        clauses.append("status = ?")
        params.append(status_filter)
    category_filter = optional_choice(category, CATEGORIES, "category")
    if category_filter:
        clauses.append("category = ?")
        params.append(category_filter)
    priority_filter = optional_choice(priority, PRIORITIES, "priority")
    if priority_filter:
        clauses.append("priority = ?")
        params.append(priority_filter)

    where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM ideas {where}ORDER BY {PRIORITY_RANK}, created_at DESC, id DESC "
        "LIMIT ?",
        (*params, max(1, int(limit))),
    ).fetchall()
    if compact:
        compact_ideas = [{f: row[f] for f in COMPACT_FIELDS} for row in rows]
        return {
            "count": len(compact_ideas),
            "status": status_filter or "all",
            "ideas": compact_ideas,
            "compact": True,
        }
    ideas = [idea_dict(row) for row in rows]
    return {"count": len(ideas), "status": status_filter or "all", "ideas": ideas}


def search_ideas(
    conn: sqlite3.Connection,
    query: str,
    project: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Search title, description and tags with a case-insensitive LIKE match."""
    text = require_text(query, "query")
    pattern = "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    clauses = [
        "(title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\')"
    ]
    params: list[Any] = [pattern, pattern, pattern]
    if project:
        clauses.append("project = ?")
        params.append(require_text(project, "project"))
    rows = conn.execute(
        f"SELECT * FROM ideas WHERE {' AND '.join(clauses)} "
        f"ORDER BY {PRIORITY_RANK}, created_at DESC, id DESC LIMIT ?",
        (*params, max(1, int(limit))),
    ).fetchall()
    ideas = [idea_dict(row) for row in rows]
    return {"query": text, "count": len(ideas), "ideas": ideas}


def update_idea_status(
    conn: sqlite3.Connection, idea_id: int, status: str
) -> dict[str, Any]:
    """Move an idea to a new status and return the updated row."""
    new_status = require_choice(status, STATUSES, "status")
    cursor = conn.execute(
        "UPDATE ideas SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, int(idea_id)),
    )
    if cursor.rowcount == 0:
        raise LookupError(f"idea #{idea_id} not found")
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (int(idea_id),)).fetchone()
    data = idea_dict(row)
    data["message"] = f"Idea #{data['id']} is now {new_status}."
    return data


def update_idea(
    conn: sqlite3.Connection,
    idea_id: int,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    tags: Iterable[str] | str | None = None,
) -> dict[str, Any]:
    """Update an idea's fields and return the updated row."""
    clauses: list[str] = ["updated_at = CURRENT_TIMESTAMP"]
    params: list[Any] = []
    if title is not None:
        clauses.append("title = ?")
        params.append(require_text(title, "title"))
    if description is not None:
        clauses.append("description = ?")
        params.append(str(description).strip())
    if category is not None:
        clauses.append("category = ?")
        params.append(require_choice(category, CATEGORIES, "category"))
    if priority is not None:
        clauses.append("priority = ?")
        params.append(require_choice(priority, PRIORITIES, "priority"))
    if tags is not None:
        clauses.append("tags = ?")
        params.append(dump_tags(tags))

    params.append(int(idea_id))
    cursor = conn.execute(
        f"UPDATE ideas SET {', '.join(clauses)} WHERE id = ?",
        params,
    )
    if cursor.rowcount == 0:
        raise LookupError(f"idea #{idea_id} not found")
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (int(idea_id),)).fetchone()
    data = idea_dict(row)
    data["message"] = f"Idea #{data['id']} updated successfully."
    return data


def delete_idea(conn: sqlite3.Connection, idea_id: int) -> dict[str, Any]:
    """Permanently delete an idea from the vault by its ID."""
    idea_id = int(idea_id)
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    if row is None:
        raise LookupError(f"idea #{idea_id} not found")
    conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
    return {"id": idea_id, "deleted": True, "message": f"Idea #{idea_id} deleted."}


def _bullet(idea: dict[str, Any]) -> str:
    parts = [f"- [ ] **{idea['title']}**"]
    if idea["description"]:
        parts.append(f" — {idea['description']}")
    meta = [f"`#{idea['id']}`", f"priority **{idea['priority']}**"]
    if idea["status"] == "in_progress":
        meta.append("_in progress_")
    if idea["tags"]:
        meta.append("tags: " + ", ".join(f"`{tag}`" for tag in idea["tags"]))
    return "".join(parts) + "  \n  " + " · ".join(meta)


def export_ideas_markdown(conn: sqlite3.Connection, project: str) -> dict[str, Any]:
    """Render open and in-progress ideas as grouped GitHub-style markdown."""
    project = require_text(project, "project")
    placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
    rows = conn.execute(
        f"SELECT * FROM ideas WHERE project = ? AND status IN ({placeholders}) "
        f"ORDER BY {PRIORITY_RANK}, category, created_at DESC, id DESC",
        (project, *ACTIVE_STATUSES),
    ).fetchall()
    ideas = [idea_dict(row) for row in rows]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [f"# Ideas — {project}", "", f"_{len(ideas)} active ideas · exported {stamp}_", ""]
    for category in CATEGORIES:
        group = [idea for idea in ideas if idea["category"] == category]
        if not group:
            continue
        lines.extend([f"## {CATEGORY_TITLES[category]}", ""])
        lines.extend(_bullet(idea) for idea in group)
        lines.append("")
    if not ideas:
        lines.append("_No open or in-progress ideas._")

    return {
        "project": project,
        "count": len(ideas),
        "markdown": "\n".join(lines).rstrip() + "\n",
    }


__all__ = [
    "record_idea",
    "record_ideas_batch",
    "list_ideas",
    "search_ideas",
    "update_idea",
    "update_idea_status",
    "delete_idea",
    "export_ideas_markdown",
    "parse_tags",
    "load_tags",
]
