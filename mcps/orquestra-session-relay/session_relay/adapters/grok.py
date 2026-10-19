"""Read-only adapter for xAI Grok session search and prompt history."""

from __future__ import annotations

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
from .base import SessionAdapter, limit_turns


class GrokAdapter(SessionAdapter):
    id = "grok"
    label = "xAI Grok"

    @property
    def sessions_root(self) -> Path:
        return self.home / ".grok" / "sessions"

    @property
    def search_db(self) -> Path:
        return self.sessions_root / "session_search.sqlite"

    def available(self) -> bool:
        return self.search_db.is_file() or any(self.sessions_root.glob("*/prompt_history.jsonl"))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.search_db}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    def _prompt_index(self) -> dict[str, list[dict[str, Any]]]:
        """session_id -> prompt records, built once per adapter instance."""
        if not hasattr(self, "_prompts"):
            prompts: dict[str, list[dict[str, Any]]] = {}
            for path in self.sessions_root.glob("*/prompt_history.jsonl"):
                for record in read_jsonl(path):
                    session_id = str(record.get("session_id") or "")
                    if session_id and record.get("prompt"):
                        prompts.setdefault(session_id, []).append(record)
            for records in prompts.values():
                records.sort(key=lambda item: str(item.get("timestamp") or ""))
            self._prompts = prompts
        return self._prompts

    def _docs(self) -> list[sqlite3.Row]:
        if not self.search_db.is_file():
            return []
        try:
            conn = self._connect()
            try:
                return conn.execute(
                    "SELECT session_id, cwd, updated_at, title, content "
                    "FROM session_docs ORDER BY updated_at DESC"
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return []

    def _summary(self, doc: sqlite3.Row | None, session_id: str) -> SessionSummary:
        prompts = self._prompt_index().get(session_id, [])
        title = str(doc["title"] or "") if doc is not None else ""
        if not title and prompts:
            title = str(prompts[0].get("prompt") or "")
        content = str(doc["content"] or "") if doc is not None else ""
        return SessionSummary(
            harness=self.id,
            session_id=session_id,
            title=clip(title, 120) or f"Grok session {session_id[:8]}",
            updated_at=(
                iso_from_epoch_seconds(doc["updated_at"])
                if doc is not None
                else str(prompts[-1].get("timestamp") or "") or None
            ),
            turns_count=len(prompts) or len([p for p in content.split("\n\n") if p.strip()]),
            project=str(doc["cwd"] or "") if doc is not None else None,
            source=str(self.search_db),
        )

    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        docs = self._docs()[: max(1, int(limit))]
        if docs:
            return [self._summary(doc, str(doc["session_id"])) for doc in docs]
        sessions = [
            (self._summary(None, session_id), session_id)
            for session_id in self._prompt_index()
        ]
        sessions.sort(key=lambda item: item[0].updated_at or "", reverse=True)
        return [summary for summary, _ in sessions[: max(1, int(limit))]]

    def _events(self, session_id: str) -> list[Event]:
        records = self._prompt_index().get(session_id, [])
        if records:
            return [
                Event(
                    "user",
                    clip(str(record.get("prompt") or ""), 900),
                    timestamp=str(record.get("timestamp") or "") or None,
                )
                for record in records
            ]
        doc = next((row for row in self._docs() if row["session_id"] == session_id), None)
        if doc is None:
            return []
        return [
            Event("user", clip(prompt, 900))
            for prompt in str(doc["content"] or "").split("\n\n")
            if prompt.strip()
        ]

    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        if session_id == "latest":
            sessions = self.list_sessions(limit=1)
            if not sessions:
                return None
            session_id = sessions[0].session_id
        doc = next((row for row in self._docs() if row["session_id"] == session_id), None)
        if doc is None and session_id not in self._prompt_index():
            return None
        return SessionDetail(
            summary=self._summary(doc, session_id),
            events=limit_turns(self._events(session_id), max_turns),
        )

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        needle = query.strip()
        if not needle or not self.search_db.is_file():
            return []
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT session_id, cwd, updated_at, title, content "
                    "FROM session_docs WHERE content LIKE ? OR title LIKE ? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (f"%{needle}%", f"%{needle}%", max(1, int(limit))),
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return []
        hits: list[SearchHit] = []
        for row in rows:
            content = str(row["content"] or "")
            if needle.lower() not in content.lower() and needle.lower() not in str(
                row["title"] or ""
            ).lower():
                continue
            hits.append(
                SearchHit(
                    harness=self.id,
                    session_id=str(row["session_id"]),
                    title=str(row["title"] or "") or f"Grok session {str(row['session_id'])[:8]}",
                    snippet=snippet(content or str(row["title"] or ""), needle),
                    updated_at=iso_from_epoch_seconds(row["updated_at"]),
                )
            )
        return hits
