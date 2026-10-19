"""Home resolution and tolerant, read-only file helpers."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

HOME_ENV = "SESSION_RELAY_HOME"


def home() -> Path:
    """Resolve the home root, overridable for tests and fixtures."""
    override = os.environ.get(HOME_ENV, "").strip()
    return Path(override).expanduser() if override else Path.home()


def iso_from_epoch_seconds(value: Any) -> str | None:
    try:
        return _iso(float(value))
    except (TypeError, ValueError):
        return None


def iso_from_epoch_ms(value: Any) -> str | None:
    try:
        return _iso(float(value) / 1000.0)
    except (TypeError, ValueError):
        return None


def iso_from_mtime(path: Path) -> str | None:
    try:
        return _iso(path.stat().st_mtime)
    except OSError:
        return None


def _iso(seconds: float) -> str:
    return (
        datetime.fromtimestamp(seconds, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def clip(text: str, limit: int = 600) -> str:
    """Trim long text on a word boundary with an explicit ellipsis."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_jsonl(path: Path, tail_bytes: int | None = None) -> Iterator[dict[str, Any]]:
    """Yield parsed JSON objects; unreadable lines are skipped, never raised."""
    try:
        if tail_bytes:
            with path.open("rb") as handle:
                handle.seek(max(0, path.stat().st_size - tail_bytes))
                raw = handle.read().decode("utf-8", errors="replace")
            lines = raw.splitlines()
            if lines and not raw.startswith("{"):
                lines = lines[1:]
        else:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            yield value


def snippet(text: str, query: str, radius: int = 90) -> str:
    """Return a one-line excerpt around the first case-insensitive match."""
    flat = " ".join(str(text or "").split())
    index = flat.lower().find(query.lower())
    if index < 0:
        return clip(flat, radius * 2)
    start = max(0, index - radius)
    end = min(len(flat), index + len(query) + radius)
    prefix = "…" if start else ""
    suffix = "…" if end < len(flat) else ""
    return f"{prefix}{flat[start:end]}{suffix}"
