"""Value objects shared by every adapter, the handoff synthesizer and the server."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SessionSummary:
    """One discovered session, cheap to build and safe to serialize."""

    harness: str
    session_id: str
    title: str
    updated_at: str | None = None
    turns_count: int = 0
    project: str | None = None
    source: str | None = None
    is_pinned: bool = False
    pin_label: str | None = None

    @property
    def id(self) -> str:
        return self.session_id

    def with_pin(self, label: str | None) -> SessionSummary:
        """Copy decorated from the pins sidecar (never stored in a harness)."""
        return SessionSummary(
            harness=self.harness,
            session_id=self.session_id,
            title=self.title,
            updated_at=self.updated_at,
            turns_count=self.turns_count,
            project=self.project,
            source=self.source,
            is_pinned=True,
            pin_label=label,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "harness": self.harness,
            "session_id": self.session_id,
            "title": self.title,
            "updated_at": self.updated_at,
            "turns_count": self.turns_count,
            "project": self.project,
            "source": self.source,
            "is_pinned": self.is_pinned,
            "pin_label": self.pin_label,
        }


@dataclass(frozen=True)
class Event:
    """A single conversation or tool event extracted from a session."""

    role: str
    text: str
    tool: str | None = None
    timestamp: str | None = None
    error: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "tool": self.tool,
            "timestamp": self.timestamp,
            "error": self.error,
        }


@dataclass
class SessionDetail:
    """A session summary plus its ordered events."""

    summary: SessionSummary
    events: list[Event] = field(default_factory=list)

    def as_dict(self, max_text: int | None = None) -> dict[str, Any]:
        events = []
        for event in self.events:
            data = event.as_dict()
            if max_text and len(data["text"]) > max_text:
                data["text"] = data["text"][:max_text] + "…"
            events.append(data)
        return {
            "session": self.summary.as_dict(),
            "event_count": len(self.events),
            "events": events,
        }


@dataclass(frozen=True)
class SearchHit:
    """A matching session with the snippet that matched."""

    harness: str
    session_id: str
    title: str
    snippet: str
    updated_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "harness": self.harness,
            "session_id": self.session_id,
            "title": self.title,
            "updated_at": self.updated_at,
            "snippet": self.snippet,
        }
