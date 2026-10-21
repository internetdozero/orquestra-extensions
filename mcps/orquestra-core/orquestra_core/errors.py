"""Report anticipated control-plane failures as actionable MCP tool errors.

Anything that escapes a tool body is a crash as far as the MCP SDK is
concerned: the client receives only ``Error executing tool <name>`` and the
cause stays in the server log. Bad input, missing records, unreadable state,
expected native-binary refusals and failed vault requests are things the
calling agent can act on, so they are re-raised as ``ToolError`` with their
own text.

`ToolError` also means ``is_error: true``: returning ``{"error": ...}`` inside
a successful result can be mistaken for valid data. Genuine bugs remain
unwrapped and still log a traceback; in particular, arbitrary ``RuntimeError``
and ``KeyError``/``IndexError`` are not swallowed.
"""

from __future__ import annotations

import functools
import subprocess
from typing import Any, Callable, TypeVar, cast

from mcp.server.mcpserver.exceptions import ToolError

F = TypeVar("F", bound=Callable[..., Any])


class BridgeError(RuntimeError):
    """The native OrquestraAI binary failed, timed out or returned bad data."""


class MissingPreset(LookupError):
    """A requested custom preset id is not present."""


class UnknownVaultService(LookupError):
    """A requested credential service is not configured."""


class VaultRequestError(RuntimeError):
    """An HTTP or CLI operation using a stored vault credential failed."""


# Only failures with an actionable explanation; don't flatten arbitrary bugs.
ANTICIPATED = (
    ValueError,
    OSError,
    subprocess.TimeoutExpired,
    BridgeError,
    MissingPreset,
    UnknownVaultService,
    VaultRequestError,
)


def actionable(fn: F) -> F:
    """Re-raise anticipated failures as ``ToolError`` carrying their message."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ANTICIPATED as exc:
            raise ToolError(f"{type(exc).__name__}: {exc}") from exc

    return cast(F, wrapper)


__all__ = [
    "actionable",
    "ANTICIPATED",
    "BridgeError",
    "MissingPreset",
    "UnknownVaultService",
    "VaultRequestError",
]
