"""Read-only adapter for the Hermes Agent session store.

Primary source is ``~/.hermes/state.db`` (``sessions`` plus ``messages``
with epoch-second timestamps). When the database is absent, per-session
log files under ``~/.hermes/sessions/<id>.json`` still yield a listing;
both sources are opened read-only and malformed rows are skipped.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..models import Event, SearchHit, SessionDetail, SessionSummary
from ..paths import clip, iso_from_epoch_seconds, read_json, snippet
from .base import SessionAdapter, clamp_limit, limit_turns

SESSION_COLS = "id, display_name, started_at, ended_at, message_count"


class HermesAdapter(SessionAdapter):
    id = "hermes"
    label = "Hermes Agent"

    @property
    def db_path(self) -> Path:
        return self.home / ".hermes" / "state.db"

    @property
    def logs_dir(self) -> Path:
        return self.home / ".hermes" / "sessions"

    def available(self) -> bool:
        if self.db_path.is_file():
            return True
        try:
            return self.logs_dir.is_dir() and any(self.logs_dir.glob("*.json"))
        except OSError:
            return False

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    def _summary(self, row: sqlite3.Row) -> SessionSummary:
        title = (row["display_name"] or "").strip()
        stamp = row["ended_at"] or row["started_at"]
        return SessionSummary(
            harness=self.id,
            session_id=row["id"],
            title=clip(title, 120) or f"Hermes session {row['id'][:8]}",
            updated_at=iso_from_epoch_seconds(stamp),
            turns_count=int(row["message_count"] or 0),
            project=None,
            source=str(self.db_path),
        )

    def _log_summary(self, path: Path) -> SessionSummary:
        data = read_json(path) or {}
        title = str(data.get("display_name") or data.get("title") or "").strip()
        return SessionSummary(
            harness=self.id,
            session_id=path.stem,
            title=clip(title, 120) or f"Hermes session {path.stem[:8]}",
            updated_at=str(data.get("ended_at") or data.get("started_at") or "") or None,
            turns_count=int(data.get("message_count") or 0),
            project=None,
            source=str(path),
        )

    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        bound = clamp_limit(limit, 5)
        if self.db_path.is_file():
            try:
                conn = self._connect()
                try:
                    rows = conn.execute(
                        f"SELECT {SESSION_COLS} FROM sessions "
                        "ORDER BY ended_at DESC, started_at DESC LIMIT ?",
                        (bound,),
                    ).fetchall()
                    return [self._summary(row) for row in rows]
                finally:
                    conn.close()
            except sqlite3.Error:
                return []
        try:
            files = sorted(
                self.logs_dir.glob("*.json"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return []
        return [self._log_summary(path) for path in files[:bound]]

    def _events(self, conn: sqlite3.Connection, session_id: str) -> list[Event]:
        try:
            rows = conn.execute(
                "SELECT role, content, tool_name, timestamp FROM messages "
                "WHERE session_id = ? ORDER BY timestamp ASC, id ASC",
                (session_id,),
            ).fetchall()
        except sqlite3.Error:
            return []
        events: list[Event] = []
        for row in rows:
            text = (row["content"] or "").strip()
            if not text:
                continue
            role = row["role"] if row["role"] in ("user", "assistant") else "assistant"
            if row["tool_name"]:
                events.append(
                    Event(
                        "tool",
                        clip(text, 900),
                        tool=str(row["tool_name"]),
                        timestamp=iso_from_epoch_seconds(row["timestamp"]),
                    )
                )
            else:
                events.append(
                    Event(
                        role,
                        clip(text, 900),
                        timestamp=iso_from_epoch_seconds(row["timestamp"]),
                    )
                )
        return events

    def _log_events(self, session_id: str) -> list[Event]:
        data = read_json(self.logs_dir / f"{session_id}.json") or {}
        messages = data.get("messages")
        if not isinstance(messages, list):
            return []
        events: list[Event] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            text = str(item.get("content") or item.get("text") or "").strip()
            if not text:
                continue
            role = item.get("role") if item.get("role") in ("user", "assistant") else "assistant"
            events.append(Event(role, clip(text, 900)))
        return events

    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        if self.db_path.is_file():
            try:
                conn = self._connect()
                try:
                    if session_id == "latest":
                        row = conn.execute(
                            f"SELECT {SESSION_COLS} FROM sessions "
                            "ORDER BY ended_at DESC, started_at DESC LIMIT 1"
                        ).fetchone()
                    else:
                        row = conn.execute(
                            f"SELECT {SESSION_COLS} FROM sessions WHERE id = ?",
                            (session_id,),
                        ).fetchone()
                    if row is None:
                        return None
                    events = self._events(conn, row["id"])
                    if not events:
                        events = self._log_events(row["id"])
                    return SessionDetail(
                        summary=self._summary(row),
                        events=limit_turns(events, max_turns),
                    )
                finally:
                    conn.close()
            except sqlite3.Error:
                return None
        if session_id == "latest":
            sessions = self.list_sessions(limit=1)
            if not sessions:
                return None
            session_id = sessions[0].session_id
        events = self._log_events(session_id)
        if not events:
            return None
        summaries = [item for item in self.list_sessions(limit=50) if item.session_id == session_id]
        if not summaries:
            return None
        return SessionDetail(summary=summaries[0], events=limit_turns(events, max_turns))

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        needle = query.strip()
        if not needle or not self.db_path.is_file():
            return []
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT m.session_id, m.content, s.display_name, s.ended_at "
                    "FROM messages m LEFT JOIN sessions s ON s.id = m.session_id "
                    "WHERE m.content LIKE ? ORDER BY m.timestamp DESC LIMIT ?",
                    (f"%{needle}%", clamp_limit(limit, 10) * 5),
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return []
        hits: list[SearchHit] = []
        seen: set[str] = set()
        for row in rows:
            if row["session_id"] in seen:
                continue
            text = str(row["content"] or "")
            if needle.lower() not in text.lower():
                continue
            seen.add(row["session_id"])
            hits.append(
                SearchHit(
                    harness=self.id,
                    session_id=row["session_id"],
                    title=clip(str(row["display_name"] or ""), 120)
                    or f"Hermes session {row['session_id'][:8]}",
                    snippet=snippet(text, needle),
                    updated_at=iso_from_epoch_seconds(row["ended_at"]),
                )
            )
            if len(hits) >= clamp_limit(limit, 10):
                break
        return hits


__all__ = ["HermesAdapter"]
