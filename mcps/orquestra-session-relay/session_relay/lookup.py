"""Resolving which harness holds a session: prefixes, fallbacks and loading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import discovery
from .adapters.base import clamp_limit

PREFIX_HARNESS = {
    "desktop:": "freebuff",
    "claude:": "claude",
    "codex:": "codex",
}
DEFAULT_MAX_TURNS = 10
MAX_TURNS = 50


@dataclass
class Resolution:
    """The session that was found, or the reason it was not."""

    adapter: Any | None = None
    detail: Any | None = None
    error: str | None = None
    harness: str | None = None
    hint: str | None = None
    with_events: bool = False

    def as_error_payload(self) -> dict[str, Any]:
        """Render the failure in the shape the tools have always returned."""
        payload: dict[str, Any] = {"error": self.error}
        if self.harness:
            payload["harness"] = self.harness
        if self.hint:
            payload["hint"] = self.hint
        if self.with_events:
            payload["events"] = []
        return payload


def infer_harness(session_id: str) -> str | None:
    """Guess the harness from a session-id prefix, if it carries one."""
    text = (session_id or "").strip()
    for prefix, harness in PREFIX_HARNESS.items():
        if text.startswith(prefix):
            return harness
    return None


def find_harness_for(session_id: str, skip: str | None = None) -> str | None:
    """Return the first harness whose store can load the session id."""
    for adapter in discovery.adapters_for():
        if skip is not None and adapter.id == skip:
            continue
        try:
            if adapter.available() and adapter.load_session(session_id, 1):
                return adapter.id
        except Exception:
            continue
    return None


def _load(adapter: Any, session_id: str, max_turns: int) -> Any:
    return adapter.load_session(session_id, clamp_limit(max_turns, DEFAULT_MAX_TURNS, MAX_TURNS))


def resolve(harness: str | None, session_id: str, max_turns: int) -> Resolution:
    """Find the adapter and detail for one session, inferring the harness."""
    resolved = (harness or "").strip() or None
    if resolved is None:
        resolved = infer_harness(session_id)
    if resolved is None and session_id != "latest":
        resolved = find_harness_for(session_id)
    if resolved is None and session_id == "latest":
        newest, _ = discovery.recent_sessions(limit=1)
        if newest:
            resolved = newest[0].harness
            session_id = newest[0].session_id
    if resolved is None:
        return Resolution(
            error=f"session '{session_id}' was not found across any harness",
            with_events=True,
        )
    try:
        adapter = discovery.get_adapter(resolved)
    except ValueError as error:
        return Resolution(error=str(error))
    if not adapter.available():
        return Resolution(
            error=f"no {adapter.label} session store was found on this machine",
            harness=adapter.id,
            with_events=True,
        )
    detail = _load(adapter, session_id, max_turns)
    if detail is None and not harness:
        # A wrong prefix guess must not hide a session living elsewhere.
        fallback = find_harness_for(session_id, skip=adapter.id)
        if fallback is not None:
            try:
                adapter = discovery.get_adapter(fallback)
                detail = _load(adapter, session_id, max_turns)
            except ValueError:
                detail = None
    if detail is None:
        return Resolution(
            error=f"session '{session_id}' was not found for {adapter.id}",
            harness=adapter.id,
            hint=f"Call list_recent_sessions(harness='{adapter.id}') for valid ids.",
            with_events=True,
        )
    return Resolution(adapter=adapter, detail=detail)
