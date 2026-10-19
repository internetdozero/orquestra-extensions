"""Adapter registry: one read-only adapter per supported harness."""

from __future__ import annotations

from pathlib import Path

from .antigravity import AntigravityAdapter
from .base import SessionAdapter
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .freebuff import FreebuffAdapter
from .grok import GrokAdapter
from .opencode import OpenCodeAdapter

ADAPTERS: tuple[type[SessionAdapter], ...] = (
    AntigravityAdapter,
    ClaudeAdapter,
    CodexAdapter,
    FreebuffAdapter,
    GrokAdapter,
    OpenCodeAdapter,
)

ALIASES = {
    "claude-code": "claude",
    "manicode": "freebuff",
    "gemini": "antigravity",
    "open-code": "opencode",
    "xai": "grok",
}


def build_adapters(home: Path | None = None) -> list[SessionAdapter]:
    """Instantiate every adapter against one home root."""
    return [adapter(home) for adapter in ADAPTERS]


def canonical_harness(harness: str) -> str:
    key = harness.strip().lower()
    return ALIASES.get(key, key)


__all__ = [
    "ADAPTERS",
    "ALIASES",
    "AntigravityAdapter",
    "ClaudeAdapter",
    "CodexAdapter",
    "FreebuffAdapter",
    "GrokAdapter",
    "OpenCodeAdapter",
    "SessionAdapter",
    "build_adapters",
    "canonical_harness",
]
