"""Read-only adapter for Freebuff/Manicode project chats and prompt history."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import Event, SearchHit, SessionDetail, SessionSummary
from ..paths import clip, read_json, snippet
from .base import SessionAdapter, limit_turns
from .freebuff_store import (
    events_from_messages,
    history_summary,
    load_messages,
    message_text,
    search_prompts,
    summarize_chat,
)


class FreebuffAdapter(SessionAdapter):
    id = "freebuff"
    label = "Freebuff / Manicode"

    @property
    def projects(self) -> Path:
        return self.home / ".config" / "manicode" / "projects"

    @property
    def history_path(self) -> Path:
        return self.home / ".config" / "manicode" / "message-history.json"

    def _chat_files(self) -> list[Path]:
        if not self.projects.is_dir():
            return []
        try:
            return sorted(
                self.projects.glob("*/chats/*/chat-messages.json"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return []

    def _history(self) -> list[str]:
        value = read_json(self.history_path)
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return []

    def available(self) -> bool:
        return bool(self._chat_files()) or bool(self._history())

    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        sessions = [
            summarize_chat(path, self.id)
            for path in self._chat_files()[: max(1, int(limit))]
        ]
        if sessions:
            return sessions
        history = self._history()
        if not history:
            return []
        return [history_summary(self.history_path, history, self.id)]

    def _path_for(self, session_id: str) -> Path | None:
        files = self._chat_files()
        if session_id == "latest":
            return files[0] if files else None
        return next((path for path in files if path.parent.name == session_id), None)

    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        if session_id == "prompt-history" or (
            session_id == "latest" and not self._chat_files() and self._history()
        ):
            history = self._history()
            if not history:
                return None
            events = [Event("user", clip(prompt, 900)) for prompt in history]
            return SessionDetail(
                summary=self.list_sessions(limit=1)[0],
                events=limit_turns(events, max_turns),
            )

        path = self._path_for(session_id)
        if path is None:
            return None
        return SessionDetail(
            summary=summarize_chat(path, self.id),
            events=limit_turns(events_from_messages(load_messages(path)), max_turns),
        )

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        needle = query.strip()
        if not needle:
            return []
        hits: list[SearchHit] = []
        budget = 48 * 1024 * 1024
        for path in self._chat_files()[: max(1, int(limit)) * 4]:
            try:
                budget -= min(path.stat().st_size, 12 * 1024 * 1024)
            except OSError:
                continue
            if budget < 0:
                break
            summary = summarize_chat(path, self.id)
            found = ""
            for message in load_messages(path):
                text = message_text(message)
                for block in message.get("blocks") or []:
                    if isinstance(block, dict) and block.get("type") == "tool":
                        text += "\n" + str(block.get("output") or "")
                if needle.lower() in text.lower():
                    found = snippet(text, needle)
                    break
            if not found:
                continue
            hits.append(
                SearchHit(
                    harness=self.id,
                    session_id=summary.session_id,
                    title=summary.title,
                    snippet=found,
                    updated_at=summary.updated_at,
                )
            )
            if len(hits) >= max(1, int(limit)):
                break
        if hits:
            return hits
        return search_prompts(self.history_path, self._history(), needle, limit)
