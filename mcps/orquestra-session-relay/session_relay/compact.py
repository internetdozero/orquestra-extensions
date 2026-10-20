"""Compact session payloads: lean inspection rows that stay small.

Full transcripts can exceed 30KB and exhaust agent context; the compact
shape keeps identifiers, the last instruction, the last tool invoked,
touched files and open todo items.
"""

from __future__ import annotations

import re
from typing import Any

from .handoff import extract_files
from .models import SessionDetail, SessionSummary, session_is_live
from .paths import clip
from .watch import _is_running

_TODO_RE = re.compile(r"^\s*-\s*\[\s\]\s+(.+)$", re.M)


def open_todos(events: list, limit: int = 20) -> list[str]:
    """Unchecked `- [ ]` items across event texts, first-seen order."""
    found: list[str] = []
    for event in events:
        for match in _TODO_RE.findall(event.text or ""):
            item = clip(match.strip(), 160)
            if item and item not in found:
                found.append(item)
            if len(found) >= limit:
                return found
    return found


def _last_instruction(events: list) -> str | None:
    for event in reversed(events):
        if event.role == "user" and (event.text or "").strip():
            return clip(event.text.strip(), 500)
    return None


def _last_tool(events: list) -> str | None:
    for event in reversed(events):
        if event.role == "tool" or event.tool is not None:
            return event.tool or "tool"
    return None


def compact_session(detail: SessionDetail) -> dict[str, Any]:
    """Lean inspection of one loaded session."""
    summary = detail.summary
    events = detail.events
    return {
        "session_id": summary.session_id,
        "harness": summary.harness,
        "title": summary.title,
        "project": summary.project,
        "updated_at": summary.updated_at,
        "status": "running"
        if session_is_live(summary) or _is_running(summary.updated_at)
        else "idle",
        "last_instruction": _last_instruction(events),
        "last_tool": _last_tool(events),
        "touched_files": extract_files(events),
        "open_todos": open_todos(events),
    }


def compact_row(summary: SessionSummary) -> dict[str, Any]:
    """One lean row for session listings."""
    return {
        "session_id": summary.session_id,
        "harness": summary.harness,
        "title": summary.title,
        "project": summary.project,
        "updated_at": summary.updated_at,
        "status": "running"
        if session_is_live(summary) or _is_running(summary.updated_at)
        else "idle",
    }


__all__ = ["compact_row", "compact_session", "open_todos"]
