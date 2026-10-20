"""Read-only adapter for the GitHub Copilot CLI session store.

Reads ``sessions`` plus ordered ``turns`` from
``~/.copilot/session-store.db``. Active lock files under
``session-state/.session-operation-locks/`` only ever guard Copilot's own
writes: this adapter opens the database read-only and never touches them,
so a locked (live) session stays listed and readable.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import Event, SearchHit, SessionDetail, SessionSummary
from ..paths import clip, snippet
from .base import SessionAdapter, clamp_limit, limit_turns

SESSION_COLS = "id, cwd, repository, summary, created_at, updated_at"


class CopilotAdapter(SessionAdapter):
    id = "copilot"
    label = "GitHub Copilot CLI"

    @property
    def db_path(self) -> Path:
        return self.home / ".copilot" / "session-store.db"

    @property
    def locks_dir(self) -> Path:
        return self.home / ".copilot" / "session-state" / ".session-operation-locks"

    def available(self) -> bool:
        return self.db_path.is_file()

    def active_locks(self) -> set[str]:
        """Session ids with an in-flight Copilot operation (stem of *.lock)."""
        try:
            if not self.locks_dir.is_dir():
                return set()
            return {path.stem for path in self.locks_dir.glob("*.lock")}
        except OSError:
            return set()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    def _summary(self, conn: sqlite3.Connection, row: sqlite3.Row) -> SessionSummary:
        turns = conn.execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = ?", (row["id"],)
        ).fetchone()[0]
        title = (row["summary"] or "").strip()
        return SessionSummary(
            harness=self.id,
            session_id=row["id"],
            title=clip(title, 120) or f"Copilot session {row['id'][:8]}",
            updated_at=row["updated_at"],
            turns_count=turns,
            project=row["cwd"] or row["repository"],
            source=str(self.db_path),
        )

    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        if not self.available():
            return []
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    f"SELECT {SESSION_COLS} FROM sessions "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (clamp_limit(limit, 5),),
                ).fetchall()
                return [self._summary(conn, row) for row in rows]
            finally:
                conn.close()
        except sqlite3.Error:
            return []

    def _events(self, conn: sqlite3.Connection, session_id: str) -> list[Event]:
        try:
            rows = conn.execute(
                "SELECT user_message, assistant_response, timestamp FROM turns "
                "WHERE session_id = ? ORDER BY turn_index ASC",
                (session_id,),
            ).fetchall()
        except sqlite3.Error:
            return []
        events: list[Event] = []
        for row in rows:
            stamp = row["timestamp"] or None
            if (row["user_message"] or "").strip():
                events.append(
                    Event("user", clip(row["user_message"], 900), timestamp=stamp)
                )
            if (row["assistant_response"] or "").strip():
                events.append(
                    Event(
                        "assistant",
                        clip(row["assistant_response"], 900),
                        timestamp=stamp,
                    )
                )
        return events

    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        if not self.available():
            return None
        try:
            conn = self._connect()
            try:
                if session_id == "latest":
                    row = conn.execute(
                        f"SELECT {SESSION_COLS} FROM sessions "
                        "ORDER BY updated_at DESC LIMIT 1"
                    ).fetchone()
                else:
                    row = conn.execute(
                        f"SELECT {SESSION_COLS} FROM sessions WHERE id = ?",
                        (session_id,),
                    ).fetchone()
                if row is None:
                    return None
                return SessionDetail(
                    summary=self._summary(conn, row),
                    events=limit_turns(self._events(conn, row["id"]), max_turns),
                )
            finally:
                conn.close()
        except sqlite3.Error:
            return None

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        needle = query.strip()
        if not self.available() or not needle:
            return []
        pattern = f"%{needle}%"
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT s.id, s.summary, s.updated_at, t.user_message, "
                    "t.assistant_response FROM turns t JOIN sessions s "
                    "ON s.id = t.session_id WHERE t.user_message LIKE ? "
                    "OR t.assistant_response LIKE ? OR s.summary LIKE ? "
                    "ORDER BY s.updated_at DESC LIMIT ?",
                    (pattern, pattern, pattern, clamp_limit(limit, 10) * 5),
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return []
        hits: list[SearchHit] = []
        seen: set[str] = set()
        for row in rows:
            if row["id"] in seen:
                continue
            text = "\n".join(
                part
                for part in (
                    row["user_message"] or "",
                    row["assistant_response"] or "",
                )
                if part.strip()
            )
            if needle.lower() not in text.lower():
                continue
            seen.add(row["id"])
            hits.append(
                SearchHit(
                    harness=self.id,
                    session_id=row["id"],
                    title=clip((row["summary"] or "").strip(), 120)
                    or f"Copilot session {row['id'][:8]}",
                    snippet=snippet(text, needle),
                    updated_at=row["updated_at"],
                )
            )
            if len(hits) >= clamp_limit(limit, 10):
                break
        return hits
