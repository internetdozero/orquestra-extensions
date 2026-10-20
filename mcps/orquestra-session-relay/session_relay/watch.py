"""Active observability and live tracking for coding agent sessions."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import discovery
from .adapters import canonical_harness
from .adapters.base import clamp_limit
from .handoff import extract_files
from .models import Event, session_is_live
from .paths import clip

_REL_PATH = re.compile(
    r"[\"']?([a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+\.[a-zA-Z0-9_-]+)[\"']?"
)


def _matches_project(candidate: str | None, target: str) -> bool:
    """True if candidate matches or resolves to the same path as target."""
    if not candidate:
        return False
    c_str, t_str = candidate.strip(), target.strip()
    if c_str == t_str:
        return True
    try:
        return Path(c_str).expanduser().resolve() == Path(t_str).expanduser().resolve()
    except Exception:
        return False


def _parse_iso(iso_raw: Any) -> datetime | None:
    if not iso_raw:
        return None
    if isinstance(iso_raw, datetime):
        return iso_raw if iso_raw.tzinfo else iso_raw.replace(tzinfo=timezone.utc)
    try:
        cleaned = str(iso_raw).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _is_running(updated_at_raw: Any, threshold_seconds: int = 120) -> bool:
    """Status is 'running' if updated_at was within threshold_seconds, else 'idle'."""
    dt = _parse_iso(updated_at_raw)
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    diff = (now - dt).total_seconds()
    return -30 <= diff <= threshold_seconds


def _iso_str(val: Any) -> str | None:
    if val is None:
        return None
    return val.isoformat() if isinstance(val, datetime) else str(val)


def extract_recent_files(
    events: list[Event], project: str | None = None, limit: int = 20
) -> list[str]:
    """Pull recently touched files out of events, including relative project files."""
    found = extract_files(events, limit=limit)
    if len(found) >= limit:
        return found
    seen = set(found)
    for event in events:
        text = event.text or ""
        for match in _REL_PATH.findall(text):
            p = match.strip(".,;:\"'")
            if p.startswith(("http://", "https://", "node_modules/")):
                continue
            full = str(Path(project) / p) if project else p
            if full not in seen:
                seen.add(full)
                found.append(full)
            if len(found) >= limit:
                return found
    return found


def _build_last_turn(events: list[Event]) -> tuple[dict[str, Any] | None, list[Event]]:
    if not events:
        return None, []
    last_user_idx = -1
    for i, ev in enumerate(events):
        if ev.role == "user":
            last_user_idx = i
    turn_events = events[last_user_idx:] if last_user_idx >= 0 else events[-5:]
    last_event = events[-1]
    tool_calls = [
        {
            "tool": ev.tool or "tool",
            "name": ev.tool or "tool",
            "args": clip(ev.text, 300),
            "text": clip(ev.text, 300),
            "timestamp": ev.timestamp,
            "error": ev.error,
        }
        for ev in turn_events
        if ev.role == "tool" or ev.tool is not None
    ]
    return {
        "role": last_event.role,
        "text": clip(last_event.text, 500),
        "preview": clip(last_event.text, 500),
        "timestamp": last_event.timestamp,
        "tool_calls": tool_calls,
    }, turn_events


def _idle_result(project_path: str | None, error: str | None = None) -> dict[str, Any]:
    """Inactive-watch payload, carrying an error note when filtering failed."""
    payload: dict[str, Any] = {
        "active": False, "harness": None, "session_id": None, "title": None,
        "project": project_path, "updated_at": None, "status": "idle",
        "last_turn": None, "files_touched": [],
    }
    if error is not None:
        payload["error"] = error
    return payload


def watch_active_agent(
    project_path: str | None = None,
    harness: str | None = None,
    exclude_harness: str | None = None,
) -> dict[str, Any]:
    """Observe active agent activity; `exclude_harness` hides own sessions."""
    wanted = canonical_harness(harness).strip() if harness else None
    skipped = canonical_harness(exclude_harness).strip() if exclude_harness else None
    try:
        sessions, _ = discovery.recent_sessions(harness=wanted, limit=50)
    except ValueError as error:
        return _idle_result(project_path, str(error))
    if skipped:
        sessions = [s for s in sessions if canonical_harness(s.harness) != skipped]
    if project_path:
        sessions = [s for s in sessions if _matches_project(s.project, project_path)]

    if not sessions:
        return _idle_result(project_path)

    session = sessions[0]
    detail = None
    try:
        adapter = discovery.get_adapter(session.harness)
        detail = adapter.load_session(session.session_id, max_turns=5)
    except Exception:
        pass

    last_turn, turn_events = _build_last_turn(detail.events if detail else [])
    files_touched = extract_recent_files(turn_events, project=session.project)
    if not files_touched and detail and detail.events:
        tool_evs = [ev for ev in detail.events if ev.role == "tool" or ev.tool]
        if tool_evs:
            files_touched = extract_recent_files(tool_evs, project=session.project)

    return {
        "active": True,
        "harness": session.harness,
        "session_id": session.session_id,
        "title": session.title,
        "project": session.project,
        "updated_at": _iso_str(session.updated_at),
        "status": "running"
        if session_is_live(session) or _is_running(session.updated_at)
        else "idle",
        "last_turn": last_turn,
        "files_touched": files_touched,
    }


def _resolve_target(
    harness: str | None, session_id: str | None
) -> tuple[str | None, str | None, str | None]:
    """Determine the harness and session_id, returning (harness, id, error)."""
    if harness and session_id and session_id != "latest":
        return harness, session_id, None
    if harness:
        sessions, _ = discovery.recent_sessions(harness=harness, limit=1)
        if not sessions:
            return None, None, f"no sessions found for harness '{harness}'"
        return harness, sessions[0].session_id, None
    if not session_id or session_id == "latest":
        sessions, _ = discovery.recent_sessions(limit=1)
        if not sessions:
            return None, None, "no sessions found across any harness"
        return sessions[0].harness, sessions[0].session_id, None

    # Prefixed ids (desktop:/claude:/codex:) resolve straight to their
    # harness when that store can load them, without depending on the
    # recency window below.
    for prefix, hinted in (
        ("desktop:", "freebuff"),
        ("claude:", "claude"),
        ("codex:", "codex"),
    ):
        if session_id.startswith(prefix):
            try:
                adapter = discovery.get_adapter(hinted)
                if adapter.available() and adapter.load_session(session_id, max_turns=1):
                    return hinted, session_id, None
            except Exception:
                pass
            break

    # Search for session_id across recent sessions or adapters
    sessions, _ = discovery.recent_sessions(limit=50)
    matches = [s for s in sessions if s.session_id == session_id]
    if matches:
        return matches[0].harness, session_id, None
    for adapter in discovery.adapters_for():
        if adapter.available() and adapter.load_session(session_id, max_turns=1):
            return adapter.id, session_id, None
    return None, session_id, f"session '{session_id}' not found across any harness"


def tail_agent_activity(
    harness: str | None = None, session_id: str | None = None, limit: int = 5
) -> dict[str, Any]:
    """Return the last `limit` turns/events of a target session with summary text."""
    bound_limit = clamp_limit(limit, 5, 50)
    target_harness, target_id, error = _resolve_target(harness, session_id)
    if error:
        return {
            "harness": target_harness,
            "session_id": target_id,
            "title": None,
            "project": None,
            "count": 0,
            "events": [],
            "error": error,
        }

    try:
        adapter = discovery.get_adapter(target_harness)  # type: ignore[arg-type]
    except ValueError as err:
        return {
            "harness": target_harness,
            "session_id": target_id,
            "title": None,
            "project": None,
            "count": 0,
            "events": [],
            "error": str(err),
        }

    if not adapter.available():
        return {
            "harness": adapter.id,
            "session_id": target_id,
            "title": None,
            "project": None,
            "count": 0,
            "events": [],
            "error": f"no {adapter.label} session store was found on this machine",
        }

    detail = adapter.load_session(target_id, max_turns=bound_limit * 2)  # type: ignore[arg-type]
    if detail is None:
        return {
            "harness": adapter.id,
            "session_id": target_id,
            "title": None,
            "project": None,
            "count": 0,
            "events": [],
            "error": f"session '{target_id}' was not found for {adapter.id}",
        }

    tail_events = [
        {
            "role": ev.role,
            "text": clip(ev.text, 500),
            "tool": ev.tool,
            "timestamp": ev.timestamp,
            "error": ev.error,
        }
        for ev in detail.events[-bound_limit:]
    ]

    return {
        "harness": detail.summary.harness,
        "session_id": detail.summary.session_id,
        "title": detail.summary.title,
        "project": detail.summary.project,
        "count": len(tail_events),
        "events": tail_events,
    }


__all__ = ["extract_recent_files", "tail_agent_activity", "watch_active_agent"]
