"""Orchestrator telemetry: liveness, current turn and worktree state.

Read-only by construction: the only process ever spawned is
``git status --short`` inside the agent's project directory.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from typing import Any

from . import discovery
from .models import session_is_live
from .paths import clip
from .watch import _is_running, _parse_iso, _resolve_target

GIT_TIMEOUT = 10
GIT_FILE_CAP = 50


def git_dirty_files(project: str | None, limit: int = GIT_FILE_CAP) -> list[str]:
    """Short-status paths of a working tree; [] when unknown or not a repo."""
    if not project:
        return []
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()][:limit]


def _running_duration_s(timestamps: list) -> float | None:
    """Seconds since the earliest parseable event timestamp."""
    moments = [dt for raw in timestamps if (dt := _parse_iso(raw)) is not None]
    if not moments:
        return None
    return max(0.0, (datetime.now(timezone.utc) - min(moments)).total_seconds())


def audit_agent(harness: str, session_id: str | None = None) -> dict[str, Any]:
    """Lean telemetry for one agent thread: liveness, turn, worktree."""
    target_harness, target_id, error = _resolve_target(harness, session_id)
    if error:
        return {
            "harness": target_harness,
            "session_id": target_id,
            "status": "idle",
            "current_turn_preview": None,
            "git_dirty_files": [],
            "running_duration_s": None,
            "error": error,
        }
    try:
        adapter = discovery.get_adapter(target_harness)  # type: ignore[arg-type]
    except ValueError as err:
        return {
            "harness": target_harness,
            "session_id": target_id,
            "status": "idle",
            "current_turn_preview": None,
            "git_dirty_files": [],
            "running_duration_s": None,
            "error": str(err),
        }
    if not adapter.available():
        return {
            "harness": adapter.id,
            "session_id": target_id,
            "status": "idle",
            "current_turn_preview": None,
            "git_dirty_files": [],
            "running_duration_s": None,
            "error": f"no {adapter.label} session store was found on this machine",
        }
    detail = adapter.load_session(target_id, max_turns=5)  # type: ignore[arg-type]
    if detail is None:
        return {
            "harness": adapter.id,
            "session_id": target_id,
            "status": "idle",
            "current_turn_preview": None,
            "git_dirty_files": [],
            "running_duration_s": None,
            "error": f"session '{target_id}' was not found for {adapter.id}",
        }
    summary = detail.summary
    events = detail.events
    last = events[-1] if events else None
    return {
        "harness": summary.harness,
        "session_id": summary.session_id,
        "status": "running"
        if session_is_live(summary) or _is_running(summary.updated_at)
        else "idle",
        "current_turn_preview": clip(last.text, 300) if last and last.text else None,
        "git_dirty_files": git_dirty_files(summary.project),
        "running_duration_s": _running_duration_s([ev.timestamp for ev in events]),
    }


__all__ = ["audit_agent", "git_dirty_files"]
