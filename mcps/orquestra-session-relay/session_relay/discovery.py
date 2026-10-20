"""Cross-harness discovery: adapters, recent sessions and lookup."""

from __future__ import annotations

from typing import Any

from .adapters import build_adapters, canonical_harness
from .adapters.base import clamp_limit
from .models import SessionSummary

KNOWN = (
    "antigravity", "claude", "codex", "copilot", "freebuff", "grok",
    "hermes", "kilo", "opencode",
)


def adapters_for(harness: str | None = None):
    """Build adapters, optionally narrowed to one canonical harness id."""
    adapters = build_adapters()
    if not harness:
        return adapters
    wanted = canonical_harness(harness)
    matches = [adapter for adapter in adapters if adapter.id == wanted]
    if not matches:
        raise ValueError(
            f"unknown harness '{harness}'; expected one of: {', '.join(KNOWN)}"
        )
    return matches


def get_adapter(harness: str):
    """Return the single adapter for a harness id, or raise ValueError."""
    return adapters_for(harness)[0]


def harness_status() -> list[dict[str, Any]]:
    """Report which harness stores exist on this machine."""
    return [
        {"harness": adapter.id, "label": adapter.label, "available": adapter.available()}
        for adapter in build_adapters()
    ]


def recent_sessions(
    harness: str | None = None, limit: int = 5
) -> tuple[list[SessionSummary], list[str]]:
    """Merge the newest sessions across harnesses, newest first."""
    limit = clamp_limit(limit, 5, 50)
    warnings: list[str] = []
    found: list[SessionSummary] = []
    for adapter in adapters_for(harness):
        try:
            if not adapter.available():
                warnings.append(f"{adapter.id}: no session store found")
                continue
            found.extend(adapter.list_sessions(limit=limit))
        except Exception as error:  # a broken store must not hide the others
            warnings.append(f"{adapter.id}: {type(error).__name__}: {error}")
    found.sort(key=lambda item: item.updated_at or "", reverse=True)
    return found[:limit], warnings
