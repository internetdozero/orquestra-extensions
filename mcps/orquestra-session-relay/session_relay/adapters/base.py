"""The read-only adapter contract every harness implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .. import paths
from ..models import Event, SearchHit, SessionDetail, SessionSummary


def clamp_limit(value: object, default: int, maximum: int | None = None) -> int:
    """Coerce a limit to a sane int: garbage falls back to `default`, floor 1."""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        number = default
    number = max(1, number)
    return min(number, maximum) if maximum is not None else number


class SessionAdapter(ABC):
    """One harness's session store, read without ever writing to it."""

    id: str
    label: str

    def __init__(self, home: Path | None = None) -> None:
        self.home = home or paths.home()

    @abstractmethod
    def available(self) -> bool:
        """True when the harness store exists on this machine."""

    @abstractmethod
    def list_sessions(self, limit: int = 5) -> list[SessionSummary]:
        """Most recent sessions first; empty when nothing is readable."""

    @abstractmethod
    def load_session(
        self, session_id: str = "latest", max_turns: int = 10
    ) -> SessionDetail | None:
        """Load one session or return None when the id is unknown."""

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        """Case-insensitive message search across this harness's sessions."""


def limit_turns(events: list[Event], max_turns: int) -> list[Event]:
    """Keep the most recent `max_turns` user turns with their tool activity."""
    if max_turns <= 0:
        return events
    user_positions = [index for index, event in enumerate(events) if event.role == "user"]
    if len(user_positions) <= max_turns:
        return events
    return events[user_positions[-max_turns] :]


def sort_events(events: list[Event]) -> list[Event]:
    """Order events by their ISO timestamp, keeping original order on ties."""
    return sorted(events, key=lambda event: event.timestamp or "")
