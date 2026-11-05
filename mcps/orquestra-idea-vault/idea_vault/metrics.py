"""Productivity and developer velocity metrics calculated from the SQLite store."""

from __future__ import annotations

import sqlite3
from typing import Any

from .store import CATEGORIES, PRIORITIES, STATUSES, require_text


def get_metrics(
    conn: sqlite3.Connection,
    project: str | None = None,
    weeks: int = 12,
) -> dict[str, Any]:
    """Compute overall completion metrics, velocity, and distribution across categories/priorities."""
    weeks = max(1, min(int(weeks or 12), 52))
    clauses: list[str] = []
    params: list[Any] = []
    if project:
        clauses.append("project = ?")
        params.append(require_text(project, "project"))

    where = f"WHERE {' AND '.join(clauses)} " if clauses else ""

    # Total counts and status breakdown
    status_counts = {s: 0 for s in STATUSES}
    for row in conn.execute(
        f"SELECT status, COUNT(*) as count FROM ideas {where}GROUP BY status", params
    ).fetchall():
        if row["status"] in status_counts:
            status_counts[row["status"]] = row["count"]

    total = sum(status_counts.values())
    completed = status_counts.get("completed", 0)
    completion_rate = round(completed / total, 4) if total > 0 else 0.0

    # Category breakdown
    category_counts = {c: 0 for c in CATEGORIES}
    for row in conn.execute(
        f"SELECT category, COUNT(*) as count FROM ideas {where}GROUP BY category", params
    ).fetchall():
        if row["category"] in category_counts:
            category_counts[row["category"]] = row["count"]

    # Priority breakdown
    priority_counts = {p: 0 for p in PRIORITIES}
    for row in conn.execute(
        f"SELECT priority, COUNT(*) as count FROM ideas {where}GROUP BY priority", params
    ).fetchall():
        if row["priority"] in priority_counts:
            priority_counts[row["priority"]] = row["count"]

    # Velocity: this week vs previous week
    this_week_clauses = list(clauses) + [
        "completed_at IS NOT NULL",
        "date(completed_at) >= date('now', '-7 days')",
    ]
    this_week_where = f"WHERE {' AND '.join(this_week_clauses)} "
    this_week_count = conn.execute(
        f"SELECT COUNT(*) FROM ideas {this_week_where}", params
    ).fetchone()[0]

    last_week_clauses = list(clauses) + [
        "completed_at IS NOT NULL",
        "date(completed_at) >= date('now', '-14 days')",
        "date(completed_at) < date('now', '-7 days')",
    ]
    last_week_where = f"WHERE {' AND '.join(last_week_clauses)} "
    last_week_count = conn.execute(
        f"SELECT COUNT(*) FROM ideas {last_week_where}", params
    ).fetchone()[0]

    return {
        "project": project,
        "total": total,
        "status_breakdown": status_counts,
        "category_breakdown": category_counts,
        "priority_breakdown": priority_counts,
        "completion_rate": completion_rate,
        "weekly_velocity": {
            "this_week": this_week_count,
            "last_week": last_week_count,
        },
        "weeks": weeks,
    }


__all__ = ["get_metrics"]
