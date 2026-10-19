"""Read-only adapter for Antigravity brain transcripts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import Event, SearchHit, SessionDetail, SessionSummary
from ..paths import clip, iso_from_mtime, read_jsonl, snippet
from .base import SessionAdapter, limit_turns

_USER_REQUEST = re.compile(r"<USER_REQUEST>(.*?)(?:</USER_REQUEST>|<ADDITIONAL)", re.S)
_FAILED_STATUSES = {"ERROR", "FAILED", "CANCELLED", "ABORTED"}


def _failed(status: str) -> bool:
    return status.upper() in _FAILED_STATUSES


def _user_text(content: str) -> str:
    match = _USER_REQUEST.search(content)
    return (match.group(1) if match else content).strip()


class AntigravityAdapter(SessionAdapter):
    id = "antigravity"
    label = "Google Antigravity"

    @property
    def brain_root(self) -> Path:
        return self.home / ".gemini" / "antigravity" / "brain"

    def _transcripts(self) -> list[Path]:
        if not self.brain_root.is_dir():
            return []
        try:
            return sorted(
                self.brain_root.glob("*/.system_generated/logs/transcript.jsonl"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return []

    def available(self) -> bool:
        return bool(self._transcripts())

    def _summarize(self, path: Path) -> SessionSummary:
        title, users, last = "", 0, None
        for record in read_jsonl(path):
            last = record.get("created_at") or last
            if record.get("type") != "USER_INPUT":
                continue
            text = _user_text(str(record.get("content") or ""))
            if text:
                users += 1
                title = title or clip(text, 120)
        session_id = path.parents[2].name
        return SessionSummary(
            harness=self.id,
            session_id=session_id,
            title=title or f"Antigravity session {session_id[:8]}",
            updated_at=last or iso_from_mtime(path),
            turns_count=users,
            source=str(path),
        )

    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        return [self._summarize(path) for path in self._transcripts()[: max(1, int(limit))]]

    def _events(self, path: Path) -> list[Event]:
        events: list[Event] = []
        for record in read_jsonl(path):
            kind = record.get("type")
            stamp = record.get("created_at")
            status = str(record.get("status") or "DONE")
            if kind == "USER_INPUT":
                text = _user_text(str(record.get("content") or ""))
                if text:
                    events.append(Event("user", clip(text, 900), timestamp=stamp))
            elif kind == "PLANNER_RESPONSE":
                thinking = str(record.get("thinking") or "").strip()
                if thinking:
                    events.append(Event("assistant", clip(thinking, 700), timestamp=stamp))
                for call in record.get("tool_calls") or []:
                    if not isinstance(call, dict):
                        continue
                    args = json.dumps(call.get("args") or {}, ensure_ascii=False)
                    events.append(
                        Event(
                            "tool",
                            clip(args, 700),
                            tool=str(call.get("name") or "tool"),
                            timestamp=stamp,
                            error=_failed(status),
                        )
                    )
            elif kind == "GENERIC" and record.get("content"):
                events.append(
                    Event(
                        "tool",
                        clip(str(record["content"]), 900),
                        tool="result",
                        timestamp=stamp,
                        error=_failed(status),
                    )
                )
            elif kind == "ERROR_MESSAGE":
                events.append(
                    Event(
                        "system",
                        clip(str(record.get("content") or "Antigravity error"), 900),
                        timestamp=stamp,
                        error=True,
                    )
                )
        return events

    def _path_for(self, session_id: str) -> Path | None:
        transcripts = self._transcripts()
        if session_id == "latest":
            return transcripts[0] if transcripts else None
        return next(
            (path for path in transcripts if path.parents[2].name == session_id),
            None,
        )

    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        path = self._path_for(session_id)
        if path is None:
            return None
        return SessionDetail(
            summary=self._summarize(path),
            events=limit_turns(self._events(path), max_turns),
        )

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        needle = query.strip().lower()
        if not needle:
            return []
        hits: list[SearchHit] = []
        for path in self._transcripts():
            title, found = "", ""
            for record in read_jsonl(path):
                kind = record.get("type")
                if kind == "USER_INPUT":
                    text = _user_text(str(record.get("content") or ""))
                elif kind == "PLANNER_RESPONSE":
                    text = str(record.get("thinking") or "")
                else:
                    text = str(record.get("content") or "")
                if not text:
                    continue
                if kind == "USER_INPUT" and not title:
                    title = clip(text, 120)
                if needle in text.lower():
                    found = snippet(text, needle)
                    break
            if not found:
                continue
            summary = self._summarize(path)
            hits.append(
                SearchHit(
                    harness=self.id,
                    session_id=summary.session_id,
                    title=title or summary.title,
                    snippet=found,
                    updated_at=summary.updated_at,
                )
            )
            if len(hits) >= max(1, int(limit)):
                break
        return hits
