"""Read-only adapter for Kilo Code's SQLite session store.

Kilo persists the OpenCode schema (``session``, ``message``, ``part`` with
millisecond epoch times) under its own data directory, so the shared
``opencode_parts`` readers do the event mapping here too.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..models import SearchHit, SessionDetail, SessionSummary
from ..paths import iso_from_epoch_ms, snippet
from .base import SessionAdapter, limit_turns
from .opencode_parts import events_for_session, matching_parts, parse


class KiloAdapter(SessionAdapter):
    id = "kilo"
    label = "Kilo Code"

    @property
    def db_path(self) -> Path:
        return self.home / ".local/share/kilo/kilo.db"

    def available(self) -> bool:
        return self.db_path.is_file()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    def _summary(self, conn: sqlite3.Connection, row: sqlite3.Row) -> SessionSummary:
        turns = conn.execute(
            "SELECT COUNT(*) FROM message WHERE session_id = ?", (row["id"],)
        ).fetchone()[0]
        return SessionSummary(
            harness=self.id,
            session_id=row["id"],
            title=row["title"] or f"Kilo session {row['id'][-6:]}",
            updated_at=iso_from_epoch_ms(row["time_updated"]),
            turns_count=turns,
            project=row["directory"],
            source=str(self.db_path),
        )

    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        if not self.available():
            return []
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, title, directory, time_updated FROM session "
                    "WHERE parent_id IS NULL ORDER BY time_updated DESC LIMIT ?",
                    (max(1, int(limit)),),
                ).fetchall()
                return [self._summary(conn, row) for row in rows]
            finally:
                conn.close()
        except sqlite3.Error:
            return []

    def _row(self, conn: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
        columns = "SELECT id, title, directory, time_updated FROM session"
        if session_id != "latest":
            return conn.execute(f"{columns} WHERE id = ?", (session_id,)).fetchone()
        return conn.execute(
            f"{columns} WHERE parent_id IS NULL ORDER BY time_updated DESC LIMIT 1"
        ).fetchone()

    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        if not self.available():
            return None
        try:
            conn = self._connect()
            try:
                row = self._row(conn, session_id)
                if row is None:
                    return None
                summary = self._summary(conn, row)
                events = limit_turns(events_for_session(conn, row["id"]), max_turns)
                return SessionDetail(summary=summary, events=events)
            finally:
                conn.close()
        except sqlite3.Error:
            return None

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        needle = query.strip()
        if not self.available() or not needle:
            return []
        try:
            conn = self._connect()
            try:
                hits: list[SearchHit] = []
                seen: set[str] = set()
                for row in matching_parts(conn, needle, max(1, int(limit)) * 5):
                    if row["session_id"] in seen:
                        continue
                    data = parse(row["data"])
                    text = data.get("text") or json.dumps(
                        (data.get("state") or {}).get("input") or {}
                    )
                    if needle.lower() not in text.lower():
                        continue
                    seen.add(row["session_id"])
                    hits.append(
                        SearchHit(
                            harness=self.id,
                            session_id=row["session_id"],
                            title=row["title"] or row["session_id"],
                            snippet=snippet(text, needle),
                            updated_at=iso_from_epoch_ms(row["time_updated"]),
                        )
                    )
                    if len(hits) >= max(1, int(limit)):
                        break
                return hits
            finally:
                conn.close()
        except sqlite3.Error:
            return []
