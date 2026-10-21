"""Report anticipated janitor failures as actionable MCP tool errors.

Anything that escapes a tool body is a crash as far as the MCP SDK is
concerned: the client receives only ``Error executing tool <name>`` and the
cause stays in the server log. A bad target, a missing argument or a
`/proc` entry that vanished mid-scan are failures the calling agent can act
on, so they are re-raised as ``ToolError`` and reach it with their own text.

Genuine bugs are deliberately left alone: they still log a traceback and
still surface as a crash, because "fix your input" is the wrong advice for
them. Errors previously came back as a payload key (and, for the orphan scan,
as a fake process row); an ``is_error`` result cannot be mistaken for data.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar, cast

from mcp.server.mcpserver.exceptions import ToolError

F = TypeVar("F", bound=Callable[..., Any])

# Failures the caller can act on: bad input and unreadable system state.
ANTICIPATED = (ValueError, OSError)


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
