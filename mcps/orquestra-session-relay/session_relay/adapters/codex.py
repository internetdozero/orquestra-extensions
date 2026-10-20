"""Read-only adapter for Codex's thread history SQLite database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..models import Event, SearchHit, SessionDetail, SessionSummary
from ..paths import (
    clip,
    iso_from_epoch_seconds,
    read_jsonl,
    snippet,
)
from .base import SessionAdapter, clamp_limit, limit_turns, sort_events
from .codex_items import escape_like, item_events, message_text


class CodexAdapter(SessionAdapter):
    id = "codex"
    label = "OpenAI Codex"

    @property
    def db_path(self) -> Path:
        return self.home / ".codex" / "thread_history_1.sqlite"

    def available(self) -> bool:
        return self.db_path.is_file()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    def _first_user_text(self, conn: sqlite3.Connection, thread_id: str) -> str:
        row = conn.execute(
            "SELECT item_json FROM thread_items "
            "WHERE thread_id = ? AND item_type = 'userMessage' "
            "ORDER BY rollout_ordinal ASC LIMIT 1",
            (thread_id,),
        ).fetchone()
        return clip(message_text(row["item_json"]) if row else "", 120)

    def _meta(self, thread_id: str) -> dict[str, Any]:
        root = self.home / ".codex" / "sessions"
        if not root.is_dir():
            return {}
        for candidate in root.rglob(f"*{thread_id}*.jsonl"):
            for record in read_jsonl(candidate):
                if record.get("type") == "session_meta":
                    payload = record.get("payload")
                    return payload if isinstance(payload, dict) else {}
        return {}

    def _summary(self, conn: sqlite3.Connection, row: sqlite3.Row) -> SessionSummary:
        thread_id = row["thread_id"]
        title = self._first_user_text(conn, thread_id)
        return SessionSummary(
            harness=self.id,
            session_id=thread_id,
            title=title or f"Codex thread {thread_id[:8]}",
            updated_at=iso_from_epoch_seconds(row["last_at"]),
            turns_count=row["turns"],
            project=self._meta(thread_id).get("cwd"),
            source=str(self.db_path),
        )

    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        if not self.available():
            return []
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT thread_id, COUNT(*) AS turns, "
                    "MAX(COALESCE(completed_at, started_at)) AS last_at "
                    "FROM thread_turns GROUP BY thread_id "
                    "ORDER BY last_at DESC LIMIT ?",
                    (clamp_limit(limit, 5),),
                ).fetchall()
                return [self._summary(conn, row) for row in rows]
            finally:
                conn.close()
        except sqlite3.Error:
            return []

    def _turn_error_events(
        self, conn: sqlite3.Connection, thread_id: str
    ) -> list[Event]:
        events: list[Event] = []
        for row in conn.execute(
            "SELECT error_json, status, COALESCE(completed_at, started_at) AS at "
            "FROM thread_turns WHERE thread_id = ? AND error_json IS NOT NULL",
            (thread_id,),
        ):
            try:
                message = json.loads(row["error_json"]).get("message", "")
            except (TypeError, ValueError, AttributeError):
                message = str(row["error_json"] or "")
            events.append(
                Event(
                    "system",
                    clip(f"turn {row['status']}: {message}", 500),
                    timestamp=iso_from_epoch_seconds(row["at"]),
                    error=True,
                )
            )
        return events

    def _events(self, conn: sqlite3.Connection, thread_id: str) -> list[Event]:
        rows = conn.execute(
            "SELECT item_type, item_json, created_at_ms FROM thread_items "
            "WHERE thread_id = ? ORDER BY rollout_ordinal ASC",
            (thread_id,),
        ).fetchall()
        events = item_events(rows) + self._turn_error_events(conn, thread_id)
        return sort_events(events)

    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        if not self.available():
            return None
        sessions = self.list_sessions(limit=1 if session_id == "latest" else 200)
        summary = next((item for item in sessions if item.session_id == session_id), None)
        if summary is None and session_id == "latest" and sessions:
            summary = sessions[0]
        if summary is None:
            return None
        try:
            conn = self._connect()
            try:
                events = limit_turns(self._events(conn, summary.session_id), max_turns)
            finally:
                conn.close()
        except sqlite3.Error:
            return None
        return SessionDetail(summary=summary, events=events)

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        if not self.available() or not query.strip():
            return []
        pattern = f"%{escape_like(query.strip())}%"
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT thread_id, item_json FROM thread_items "
                    "WHERE item_type IN ('userMessage', 'agentMessage') "
                    "AND item_json LIKE ? ESCAPE '\\' "
                    "ORDER BY created_at_ms DESC LIMIT ?",
                    (pattern, clamp_limit(limit, 10) * 6),
                ).fetchall()
                hits: list[SearchHit] = []
                seen: set[str] = set()
                for row in rows:
                    thread_id = row["thread_id"]
                    if thread_id in seen:
                        continue
                    text = message_text(row["item_json"])
                    if query.lower() not in text.lower():
                        continue
                    seen.add(thread_id)
                    hits.append(
                        SearchHit(
                            harness=self.id,
                            session_id=thread_id,
                            title=self._first_user_text(conn, thread_id)
                            or f"Codex thread {thread_id[:8]}",
                            snippet=snippet(text, query),
                            updated_at=iso_from_epoch_seconds(
                                conn.execute(
                                    "SELECT MAX(COALESCE(completed_at, started_at)) "
                                    "FROM thread_turns WHERE thread_id = ?",
                                    (thread_id,),
                                ).fetchone()[0]
                            ),
                        )
                    )
                    if len(hits) >= clamp_limit(limit, 10):
                        break
                return hits
            finally:
                conn.close()
        except sqlite3.Error:
            return []
