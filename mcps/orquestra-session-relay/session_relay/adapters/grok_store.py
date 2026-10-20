"""Read-only discovery of Grok session folders, subagents and metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import SessionSummary
from ..paths import clip, iso_from_epoch_seconds, read_json, read_jsonl

META_NAMES = ("summary.json", "meta.json")
CHAT_NAMES = ("chat_history.jsonl", "events.jsonl", "prompt_history.jsonl", "output.json")


def _inside(path: Path, root: Path) -> Path | None:
    """Resolve a file or directory and refuse anything outside the store."""
    try:
        root = root.resolve(strict=True)
        candidate = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not candidate.is_relative_to(root):
        return None
    return candidate


def safe_dir(path: Path, root: Path) -> Path | None:
    candidate = _inside(path, root)
    return candidate if candidate is not None and candidate.is_dir() else None


def safe_file(path: Path, root: Path) -> Path | None:
    candidate = _inside(path, root)
    return candidate if candidate is not None and candidate.is_file() else None


def safe_session_id(session_id: str) -> bool:
    text = (session_id or "").strip()
    return bool(text) and text not in (".", "..") and not any(
        char in text for char in ("/", "\\", "\x00")
    )


def _subdirs(path: Path) -> list[Path]:
    try:
        return sorted(child for child in path.iterdir() if child.is_dir())
    except OSError:
        return []


def is_session(directory: Path) -> bool:
    return any((directory / name).is_file() for name in META_NAMES + CHAT_NAMES)


def session_dirs(root: Path) -> dict[str, Path]:
    """Map session id -> directory for project sessions and nested subagents."""
    found: dict[str, Path] = {}
    for project in _subdirs(root):
        for child in _subdirs(project):
            if child.name == "subagents":
                continue
            direct = safe_dir(child, root)
            if direct is None:
                continue
            if is_session(direct):
                found[child.name] = direct
            for nested in _subdirs(direct / "subagents"):
                subagent = safe_dir(nested, root)
                if subagent is not None and is_session(subagent):
                    found.setdefault(nested.name, subagent)
    return found


def meta(directory: Path, root: Path) -> dict[str, Any]:
    """Read summary.json (or the subagent meta.json) for one session."""
    for name in META_NAMES:
        path = safe_file(directory / name, root)
        data = read_json(path) if path is not None else None
        if isinstance(data, dict):
            return data
    return {}


def chat_path(directory: Path, root: Path) -> Path | None:
    return safe_file(directory / "chat_history.jsonl", root)


def _first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _updated_at(data: dict[str, Any]) -> str | None:
    for key in ("updated_at", "completed_at", "last_active_at", "started_at", "created_at"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return iso_from_epoch_seconds(value)
    return None


def _turns(data: dict[str, Any]) -> int:
    for key in ("num_chat_messages", "turns"):
        value = data.get(key)
        if isinstance(value, int) and value >= 0:
            return value
    return 0


def _user_turns(directory: Path, root: Path) -> int:
    chat = chat_path(directory, root)
    if chat is None:
        return 0
    return sum(1 for record in read_jsonl(chat) if record.get("type") == "user")


def summary(directory: Path, root: Path, session_id: str) -> SessionSummary:
    """Build a summary from summary.json or subagent meta.json."""
    data = meta(directory, root)
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    title = _first_text(data, ("session_summary", "generated_title", "description"))
    if not title:
        prompt = _first_text(data, ("prompt",))
        title = prompt.splitlines()[0] if prompt else ""
    return SessionSummary(
        harness="grok",
        session_id=session_id,
        title=clip(title, 120) or f"Grok session {session_id[:8]}",
        updated_at=_updated_at(data),
        turns_count=_turns(data) or _user_turns(directory, root),
        project=info.get("cwd") or data.get("child_cwd"),
        source=str(directory),
        session_kind=(
            data.get("session_kind")
            or ("subagent" if data.get("subagent_id") else None)
        ),
    )
