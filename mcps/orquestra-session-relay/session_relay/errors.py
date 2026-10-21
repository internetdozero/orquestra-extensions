"""Report anticipated relay failures as actionable MCP tool errors.

Anything that escapes a tool body is a crash as far as the MCP SDK is
concerned: the client receives only ``Error executing tool <name>`` and the
cause stays in the server log. A store that cannot be read, a broken SQLite
file or an unknown harness are failures worth showing with their own text, so
they are re-raised as ``ToolError``.

The friendly payloads are deliberately untouched: "no Claude Code store on
this machine" and "session not found" are answers, not crashes, and callers
already branch on them.
"""

from __future__ import annotations

import functools
import sqlite3
from typing import Any, Callable, TypeVar, cast

from mcp.server.mcpserver.exceptions import ToolError

F = TypeVar("F", bound=Callable[..., Any])

# Failures the caller can act on: bad ids, unreadable stores, corrupt databases.
# Avoid LookupError: it includes KeyError/IndexError that often indicate bugs.
ANTICIPATED = (ValueError, OSError, sqlite3.Error)


def actionable(fn: F) -> F:
    """Re-raise anticipated failures as ``ToolError`` carrying their message."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ANTICIPATED as exc:
            raise ToolError(f"{type(exc).__name__}: {exc}") from exc

    return cast(F, wrapper)


__all__ = ["actionable", "ANTICIPATED"]
