"""Report anticipated vault failures as actionable MCP tool errors.

Anything that escapes a tool body is a crash as far as the MCP SDK is
concerned: the client receives only ``Error executing tool <name>`` and the
cause stays in the server log. A bad enum, an empty title, an id that does not
exist or a locked database are all failures the calling agent can fix, so they
are re-raised as ``ToolError`` and reach it with their own message.

Genuine bugs are deliberately left alone: they still log a traceback and still
surface as a crash, because "fix your input" is the wrong advice for them.
"""

from __future__ import annotations

import functools
import sqlite3
from typing import Any, Callable, TypeVar, cast

from mcp.server.mcpserver.exceptions import ToolError

from .store import MissingIdea

F = TypeVar("F", bound=Callable[..., Any])

# Failures the caller can act on: bad input, missing rows, storage trouble.
ANTICIPATED = (ValueError, MissingIdea, sqlite3.Error)


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
