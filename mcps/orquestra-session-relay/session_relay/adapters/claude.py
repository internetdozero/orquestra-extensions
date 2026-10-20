"""Read-only adapter for Claude Code project transcripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import Event, SearchHit, SessionDetail, SessionSummary
from ..paths import clip, iso_from_mtime, read_jsonl, snippet
from .base import SessionAdapter, clamp_limit, limit_turns


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(part for part in parts if part)
    return ""


def _blocks(message: Any) -> list[dict[str, Any]]:
    content = message.get("content") if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


class ClaudeAdapter(SessionAdapter):
    id = "claude"
    label = "Claude Code"

    @property
    def projects(self) -> Path:
        return self.home / ".claude" / "projects"

    def available(self) -> bool:
        return self.projects.is_dir() and any(self.projects.glob("*/*.jsonl"))

    def _files(self) -> list[Path]:
        try:
            return sorted(
                self.projects.glob("*/*.jsonl"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return []

    def _summarize(self, path: Path) -> SessionSummary:
        title, cwd, users, last_stamp = "", None, 0, None
        for record in read_jsonl(path):
            last_stamp = record.get("timestamp") or last_stamp
            cwd = record.get("cwd") or cwd
            if record.get("type") != "user":
                continue
            text = _content_text((record.get("message") or {}).get("content"))
            if not text or text.startswith("<command-"):
                continue
            users += 1
            title = title or clip(text, 120)
        return SessionSummary(
            harness=self.id,
            session_id=path.stem,
            title=title or f"Claude session {path.stem[:8]}",
            updated_at=last_stamp or iso_from_mtime(path),
            turns_count=users,
            project=cwd,
            source=str(path),
        )

    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        return [self._summarize(path) for path in self._files()[: clamp_limit(limit, 5)]]

    def _events(self, path: Path) -> list[Event]:
        events: list[Event] = []
        for record in read_jsonl(path):
            kind = record.get("type")
            stamp = record.get("timestamp")
            message = record.get("message") or {}
            if kind == "user":
                content = message.get("content")
                if isinstance(content, str):
                    events.append(Event("user", clip(content, 900), timestamp=stamp))
                    continue
                user_text = _content_text(content)
                if user_text:
                    events.append(Event("user", clip(user_text, 900), timestamp=stamp))
                for block in _blocks(message):
                    if block.get("type") != "tool_result":
                        continue
                    result = _content_text(block.get("content"))
                    events.append(
                        Event(
                            "tool",
                            clip(result or "(empty tool result)", 900),
                            tool="tool_result",
                            timestamp=stamp,
                            error=bool(block.get("is_error")),
                        )
                    )
            elif kind == "assistant":
                if isinstance(message.get("content"), str) and message["content"].strip():
                    events.append(
                        Event("assistant", clip(message["content"], 900), timestamp=stamp)
                    )
                for block in _blocks(message):
                    if block.get("type") == "text" and block.get("text"):
                        events.append(
                            Event("assistant", clip(block["text"], 900), timestamp=stamp)
                        )
                    elif block.get("type") == "tool_use":
                        args = json.dumps(block.get("input") or {}, ensure_ascii=False)
                        events.append(
                            Event(
                                "tool",
                                clip(args, 700),
                                tool=str(block.get("name") or "tool"),
                                timestamp=stamp,
                            )
                        )
        return events

    def _path_for(self, session_id: str) -> Path | None:
        files = self._files()
        if session_id == "latest":
            return files[0] if files else None
        return next((path for path in files if path.stem == session_id), None)

    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        path = self._path_for(session_id)
        if path is None:
            return None
        summary = self._summarize(path)
        events = limit_turns(self._events(path), max_turns)
        return SessionDetail(summary=summary, events=events)

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        needle = query.strip().lower()
        if not needle:
            return []
        hits: list[SearchHit] = []
        for path in self._files():
            title, found = "", ""
            for record in read_jsonl(path):
                if record.get("type") not in ("user", "assistant"):
                    continue
                message = record.get("message") or {}
                text = _content_text(message.get("content"))
                if not text:
                    continue
                if record.get("type") == "user" and not title:
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
                    session_id=path.stem,
                    title=title or summary.title,
                    snippet=found,
                    updated_at=summary.updated_at,
                )
            )
            if len(hits) >= clamp_limit(limit, 10):
                break
        return hits
