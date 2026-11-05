"""Surgical session deletion with active-session and pin protection guards."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from . import discovery, policy
from .models import session_is_live


def delete_session(
    harness: str, session_id: str, force: bool = False
) -> dict[str, Any]:
    """Delete a session from its harness store with active and pin protection."""
    adapter = discovery.get_adapter(harness)
    if not adapter.available():
        raise ValueError(f"no {adapter.label} session store was found on this machine")

    # Load summary to check active state and existence
    detail = adapter.load_session(session_id, max_turns=1)
    if detail is None:
        raise ValueError(f"session '{session_id}' was not found for {adapter.id}")

    actual_id = detail.summary.session_id

    # Check active state
    if session_is_live(detail.summary):
        raise ValueError(
            f"session '{actual_id}' in {adapter.label} is currently active and cannot be deleted"
        )

    # Check pin state
    pins = policy.get_pins()
    pin_key = (adapter.id, actual_id)
    if pin_key in pins:
        if not force:
            raise ValueError(
                f"session '{actual_id}' is pinned; unpin it first or pass force=True"
            )
        policy.unpin_session(adapter.id, actual_id)

    # Invoke adapter deletion or filesystem cleanup
    reclaimed = 0
    if hasattr(adapter, "delete_session"):
        reclaimed = adapter.delete_session(actual_id)
    if not reclaimed and hasattr(adapter, "_path_for"):
        p = adapter._path_for(actual_id)
        if p and p.exists():
            if p.is_file():
                reclaimed = p.stat().st_size
                p.unlink()
            elif p.is_dir():
                reclaimed = sum(
                    f.stat().st_size for f in p.glob("**/*") if f.is_file()
                )
                shutil.rmtree(p)

    return {
        "deleted": True,
        "harness": adapter.id,
        "session_id": actual_id,
        "reclaimed_bytes": reclaimed,
    }


__all__ = ["delete_session"]
