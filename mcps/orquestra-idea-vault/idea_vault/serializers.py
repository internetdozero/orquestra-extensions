"""Convert SQLite rows into MCP-friendly dictionaries."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

_TAG_SPLIT = re.compile(r"[,\n]")

IDEA_FIELDS = (
    "id",
    "project",
    "title",
    "description",
    "category",
    "priority",
    "status",
    "created_at",
    "updated_at",
)


def parse_tags(tags: Iterable[str] | str | None) -> list[str]:
    """Normalize comma-separated or iterable tags into a deduplicated list."""
    if tags is None:
        return []
    parts = _TAG_SPLIT.split(tags) if isinstance(tags, str) else list(tags)
    seen: list[str] = []
    lowered: set[str] = set()
    for part in parts:
        tag = str(part).strip()
        if tag and tag.lower() not in lowered:
            seen.append(tag)
            lowered.add(tag.lower())
    return seen


def dump_tags(tags: Iterable[str] | str | None) -> str:
    """Serialize tags as a JSON array, the format stored in SQLite."""
    return json.dumps(parse_tags(tags), ensure_ascii=False)


def load_tags(raw: str | None) -> list[str]:
    """Read stored tags, tolerating legacy comma-separated values."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return parse_tags(raw)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return parse_tags(str(value))


def idea_dict(row: Any) -> dict[str, Any]:
    """Map an ideas row to a plain dictionary with real tag lists."""
    data = {field: row[field] for field in IDEA_FIELDS}
    data["description"] = data["description"] or ""
    data["tags"] = load_tags(row["tags"])
    return data


def note_dict(row: Any) -> dict[str, Any]:
    """Map a blackboard_notes row to a plain dictionary with a boolean flag."""
    return {
        "id": row["id"],
        "project": row["project"],
        "topic": row["topic"],
        "sender": row["sender"],
        "target": row["target"],
        "note": row["note"],
        "is_read": bool(row["is_read"]),
        "created_at": row["created_at"],
    }
