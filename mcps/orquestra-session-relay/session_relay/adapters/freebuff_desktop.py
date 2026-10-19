"""Read-only readers for Freebuff Desktop v2 SQLite stores.

``threads`` holds thread metadata, ``messages`` holds turns as ``parts_json``
(``text`` / ``tool`` kinds; internal ``reasoning`` / ``ad`` blocks skipped).
Every database opens read-only; bad stores are skipped, never fatal.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..models import Event, SearchHit, SessionSummary
from ..paths import clip, iso_from_epoch_ms, snippet

DESKTOP_PREFIX = "desktop:"

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_INTERNAL_PARTS = frozenset({"reasoning", "ad", "changes"})

THREAD_COLS = "id, title, project_path, created_at, updated_at"


def split_desktop_id(session_id: str) -> tuple[str | None, str | None] | None:
    """Split ``desktop:<slug>:<thread-id>`` or a raw thread UUID."""
    text = (session_id or "").strip()
    if text.startswith(DESKTOP_PREFIX):
        slug, sep, thread = text[len(DESKTOP_PREFIX):].rpartition(":")
        if not sep or not slug:
            return (None, None)
        return (slug, thread if UUID_RE.match(thread) else None)
    if UUID_RE.match(text):
        return (None, text)
    return None


def desktop_databases(home: Path) -> list[tuple[str, Path]]:
    """List ``(slug, db_path)`` for every desktop project store."""
    root = Path(home) / ".config" / "freebuff-desktop" / "projects"
    try:
        entries = sorted(root.iterdir()) if root.is_dir() else []
    except OSError:
        return []
    found: list[tuple[str, Path]] = []
    for entry in entries:
        db = entry / "desktop-v2.db"
        try:
            if db.is_file():
                found.append((entry.name, db))
        except OSError:
            continue
    return found


@contextmanager
def _open_ro(db: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def summarize_desktop_thread(
    slug: str, db: Path, row: dict[str, Any], harness: str, turns: int = 0
) -> SessionSummary:
    title = str(row.get("title") or "").strip()
    return SessionSummary(
        harness=harness,
        session_id=f"{DESKTOP_PREFIX}{slug}:{row['id']}",
        title=clip(title, 120) or f"Freebuff thread {str(row['id'])[:8]}",
        updated_at=iso_from_epoch_ms(row.get("updated_at")),
        turns_count=turns,
        project=str(row.get("project_path") or "") or None,
        source=str(db),
    )


def list_desktop_threads(
    home: Path, harness: str, limit: int = 5
) -> list[SessionSummary]:
    """Newest desktop threads across project stores, newest first."""
    bound = max(1, int(limit))
    found: list[SessionSummary] = []
    for slug, db in desktop_databases(home):
        try:
            with _open_ro(db) as conn:
                rows = conn.execute(
                    "SELECT " + THREAD_COLS + ", (SELECT COUNT(*) FROM messages"
                    " WHERE thread_id = threads.id AND role = 'user') AS turns"
                    " FROM threads ORDER BY updated_at DESC LIMIT ?",
                    (bound,),
                ).fetchall()
        except (sqlite3.Error, OSError):
            continue
        found.extend(
            summarize_desktop_thread(slug, db, dict(row), harness, int(row["turns"]))
            for row in rows
        )
    found.sort(key=lambda item: item.updated_at or "", reverse=True)
    return found[:bound]


def find_desktop_thread(
    home: Path, slug: str | None, thread_id: str
) -> tuple[str, Path, dict[str, Any]] | None:
    """Locate one thread, preferring the slug-named store first."""
    candidates = desktop_databases(home)
    ordered = [item for item in candidates if not slug or item[0] == slug]
    ordered += [item for item in candidates if slug and item[0] != slug]
    for cand_slug, db in ordered:
        try:
            with _open_ro(db) as conn:
                row = conn.execute(
                    "SELECT " + THREAD_COLS + " FROM threads WHERE id = ?",
                    (thread_id,),
                ).fetchone()
        except (sqlite3.Error, OSError):
            continue
        if row is not None:
            return (cand_slug, db, dict(row))
    return None


def load_desktop_messages(db: Path, thread_id: str) -> list[dict[str, Any]]:
    """Load one thread's turns in order; empty when unreadable."""
    try:
        with _open_ro(db) as conn:
            return [
                dict(item)
                for item in conn.execute(
                    "SELECT seq, role, ts, parts_json FROM messages"
                    " WHERE thread_id = ? ORDER BY seq",
                    (thread_id,),
                ).fetchall()
            ]
    except (sqlite3.Error, OSError):
        return []


def desktop_text(parts: list[dict[str, Any]]) -> str:
    """Join visible text parts, skipping internal reasoning/ads."""
    return "\n".join(
        str(part.get("text") or "")
        for part in parts
        if isinstance(part, dict) and part.get("kind") == "text"
    )


def _tool_event(part: dict[str, Any], timestamp: str | None) -> Event:
    args = json.dumps(part.get("input") or {}, ensure_ascii=False)
    output = str(part.get("output") or "")
    exit_code = part.get("exitCode")
    if exit_code not in (None, 0):
        output += f"\nexit={exit_code}"
    error = str(part.get("status") or "") not in ("", "success")
    error = error or exit_code not in (None, 0)
    return Event(
        "tool",
        clip(f"{args}\n{output}".strip(), 900),
        tool=str(part.get("toolName") or "tool"),
        timestamp=timestamp,
        error=error,
    )


def desktop_events(rows: list[dict[str, Any]]) -> list[Event]:
    """Map desktop message rows to relay events."""
    events: list[Event] = []
    for row in rows:
        try:
            parts = json.loads(row.get("parts_json") or "[]")
        except ValueError:
            parts = []
        visible = [
            part
            for part in (parts if isinstance(parts, list) else [])
            if isinstance(part, dict) and part.get("kind") not in _INTERNAL_PARTS
        ]
        timestamp = iso_from_epoch_ms(row.get("ts"))
        text = desktop_text(visible)
        role = "user" if row.get("role") == "user" else "assistant"
        if text.strip():
            events.append(Event(role, clip(text, 900), timestamp=timestamp))
        if role != "user":
            events.extend(
                _tool_event(part, timestamp)
                for part in visible
                if part.get("kind") == "tool"
            )
    return events


def search_desktop_threads(
    home: Path, harness: str, needle: str, limit: int = 10
) -> list[SearchHit]:
    """Case-insensitive substring search over desktop message parts."""
    bound = max(1, int(limit))
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for slug, db in desktop_databases(home):
        try:
            with _open_ro(db) as conn:
                matches = conn.execute(
                    "SELECT m.thread_id, m.parts_json, t.title, t.updated_at"
                    " FROM messages m LEFT JOIN threads t"
                    " ON t.id = m.thread_id"
                    " WHERE m.parts_json LIKE ? ESCAPE '\\'"
                    " ORDER BY m.ts DESC LIMIT ?",
                    (f"%{escaped}%", bound * 3),
                ).fetchall()
        except (sqlite3.Error, OSError):
            continue
        for match in matches:
            thread_id = str(match["thread_id"])
            if thread_id in seen:
                continue
            seen.add(thread_id)
            try:
                parts = json.loads(match["parts_json"] or "[]")
            except ValueError:
                parts = []
            text = desktop_text(parts if isinstance(parts, list) else [])
            hits.append(
                SearchHit(
                    harness=harness,
                    session_id=f"{DESKTOP_PREFIX}{slug}:{thread_id}",
                    title=clip(str(match["title"] or ""), 120)
                    or f"Freebuff thread {thread_id[:8]}",
                    snippet=snippet(text or thread_id, needle),
                    updated_at=iso_from_epoch_ms(match["updated_at"]),
                )
            )
            if len(hits) >= bound:
                break
        if len(hits) >= bound:
            break
    hits.sort(key=lambda hit: hit.updated_at or "", reverse=True)
    return hits[:bound]
