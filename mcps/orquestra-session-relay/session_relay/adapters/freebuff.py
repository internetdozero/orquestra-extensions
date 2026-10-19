"""Read-only adapter for Freebuff/Manicode project chats and prompt history."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import Event, SearchHit, SessionDetail, SessionSummary
from ..paths import clip, read_json, snippet
from .base import SessionAdapter, limit_turns
from .freebuff_desktop import (
    desktop_databases,
    desktop_events,
    find_desktop_thread,
    list_desktop_threads,
    load_desktop_messages,
    search_desktop_threads,
    split_desktop_id,
    summarize_desktop_thread,
)
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

    def _has_desktop(self) -> bool:
        return bool(desktop_databases(self.home))

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
        return (
            bool(self._chat_files())
            or bool(self._history())
            or self._has_desktop()
        )

    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        bound = max(1, int(limit))
        sessions = [summarize_chat(path, self.id) for path in self._chat_files()]
        sessions.extend(list_desktop_threads(self.home, self.id, limit=bound))
        sessions.sort(key=lambda item: item.updated_at or "", reverse=True)
        sessions = sessions[:bound]
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

    def _load_desktop(
        self, session_id: str, max_turns: int
    ) -> SessionDetail | None:
        """Load a desktop thread by full id, raw UUID, or newest-first."""
        if session_id == "latest":
            newest = list_desktop_threads(self.home, self.id, limit=1)
            if not newest:
                return None
            session_id = newest[0].session_id
        parsed = split_desktop_id(session_id)
        if parsed is None:
            return None
        slug, thread_id = parsed
        if not thread_id:
            return None
        found = find_desktop_thread(self.home, slug, thread_id)
        if found is None:
            return None
        slug, db, row = found
        with_desktop_counts = summarize_desktop_thread(slug, db, row, self.id)
        rows = load_desktop_messages(db, thread_id)
        if not rows and not str(row.get("title") or ""):
            return None
        users = sum(1 for item in rows if item.get("role") == "user")
        summary = SessionSummary(
            harness=self.id,
            session_id=with_desktop_counts.session_id,
            title=with_desktop_counts.title,
            updated_at=with_desktop_counts.updated_at,
            turns_count=users,
            project=with_desktop_counts.project,
            source=with_desktop_counts.source,
        )
        return SessionDetail(
            summary=summary,
            events=limit_turns(desktop_events(rows), max_turns),
        )

    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        if split_desktop_id(session_id) is not None or (
            session_id == "latest"
            and not self._chat_files()
            and self._has_desktop()
        ):
            detail = self._load_desktop(session_id, max_turns)
            # An explicit desktop id that misses is final; a corrupt store
            # under "latest" falls through to legacy chats and history.
            if detail is not None or split_desktop_id(session_id) is not None:
                return detail
        if session_id == "latest" and self._has_desktop():
            newest = self.list_sessions(limit=1)
            if newest:
                return self.load_session(newest[0].session_id, max_turns)
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
        hits.extend(
            search_desktop_threads(self.home, self.id, needle, limit)[: max(1, int(limit))]
        )
        hits.sort(key=lambda hit: hit.updated_at or "", reverse=True)
        if hits:
            return hits[: max(1, int(limit))]
        return search_prompts(self.history_path, self._history(), needle, limit)
