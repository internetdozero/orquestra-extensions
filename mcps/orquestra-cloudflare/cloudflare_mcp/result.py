"""Structured tool results and the failure envelope shared by every tool.

Every tool answers with ``{"ok": true, "result": ...}`` or
``{"ok": false, "error": {...}}``. :class:`ToolResult` is the TypedDict the MCP
server publishes as the tools' output schema — a free-form ``dict`` annotation
would also work but would advertise an untyped schema, and a bare ``list``
annotation actively breaks the call (the SDK validates the envelope against an
array schema and rejects it).
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypedDict, TypeVar

from .client import CloudflareAPIError
from .wrangler import WranglerError
from .config import ConfigError


class ToolResult(TypedDict, total=False):
    """The MCP output envelope every tool returns."""

    ok: bool
    result: Any
    error: dict[str, Any]


F = TypeVar("F", bound=Callable[..., Any])


def ok(result: Any) -> ToolResult:
    """Success envelope."""
    return {"ok": True, "result": result}


def fail(kind: str, message: str, **extra: Any) -> ToolResult:
    """Failure envelope; ``kind`` groups the cause for the harness."""
    return {"ok": False, "error": {"type": kind, "message": message, **extra}}


def safe(fn: F) -> F:
    """Wrap a tool body so failures become a structured error envelope.

    ``functools.wraps`` keeps the original signature and return annotation, so
    the MCP server still publishes the correct input/output schemas.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> ToolResult:
        try:
            return ok(fn(*args, **kwargs))
        except ConfigError as exc:
            return fail("configuration", str(exc))
        except CloudflareAPIError as exc:
            payload = exc.to_dict()
            message = payload.pop("message", str(exc))
            return fail("cloudflare_api", message, **payload)
        except WranglerError as exc:
            return fail("wrangler", str(exc))
        except ValueError as exc:
            return fail("invalid_argument", str(exc))
        except Exception as exc:  # pragma: no cover - last resort for harness safety
            return fail("internal", f"{type(exc).__name__}: {exc}")

    return wrapper  # type: ignore[return-value]
