"""Pinned sessions sidecar shared with the OrquestraAI desktop app.

Reads and writes ``~/.orquestra/sessions_policy.json`` without ever
touching a harness store. The ``retention`` half of the file belongs to
the desktop scheduler and is always preserved byte-for-byte in spirit:
pins are edited, everything else round-trips untouched.

Writes are atomic (sibling temp file + rename) so a crash never leaves
a half-written policy.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import paths
from .adapters import canonical_harness

POLICY_DIR = ".orquestra"
POLICY_FILE = "sessions_policy.json"


def policy_path(home: Path | None = None) -> Path:
    """Sidecar location; honors SESSION_RELAY_HOME in tests."""
    return (home or paths.home()) / POLICY_DIR / POLICY_FILE


def _read_doc(home: Path | None = None) -> dict[str, Any]:
    try:
        raw = policy_path(home).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return {}
    try:
        doc = json.loads(raw)
    except ValueError:
        return {}
    return doc if isinstance(doc, dict) else {}


def _pins_of(doc: dict[str, Any]) -> list[dict[str, Any]]:
    pins = doc.get("pinnedSessions")
    if not isinstance(pins, list):
        return []
    return [pin for pin in pins if isinstance(pin, dict)]


def _key(harness: str, session_id: str) -> tuple[str, str]:
    return (canonical_harness(harness), (session_id or "").strip())


def get_pins(home: Path | None = None) -> dict[tuple[str, str], str | None]:
    """Every pin as ``(harness, session_id) -> label`` (None when unlabeled)."""
    found: dict[tuple[str, str], str | None] = {}
    for pin in _pins_of(_read_doc(home)):
        harness = str(pin.get("harness") or "").strip()
        session_id = str(pin.get("sessionId") or "").strip()
        if not harness or not session_id:
            continue
        label = pin.get("label")
        label = str(label).strip() or None if label is not None else None
        found[_key(harness, session_id)] = label
    return found


def list_pins(home: Path | None = None) -> list[dict[str, Any]]:
    """Pins in file order, normalized to the desktop shape."""
    ordered: list[dict[str, Any]] = []
    for pin in _pins_of(_read_doc(home)):
        harness = str(pin.get("harness") or "").strip()
        session_id = str(pin.get("sessionId") or "").strip()
        if not harness or not session_id:
            continue
        label = pin.get("label")
        ordered.append(
            {
                "harness": canonical_harness(harness),
                "sessionId": session_id,
                "pinnedAt": pin.get("pinnedAt"),
                "label": str(label).strip() or None
                if label is not None
                else None,
            }
        )
    return ordered


def _write_doc(doc: dict[str, Any], home: Path | None = None) -> None:
    path = policy_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    tmp = path.parent / f".{POLICY_FILE}.tmp-{os.getpid()}"
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def pin_session(
    harness: str, session_id: str, label: str | None = None, home: Path | None = None
) -> dict[str, Any]:
    """Pin one session; re-pinning updates the label, never duplicates."""
    key_harness, key_id = _key(harness, session_id)
    if not key_harness or not key_id:
        raise ValueError("harness and session_id must be non-empty strings")
    clean = (label or "").strip() or None
    doc = _read_doc(home)
    pins = _pins_of(doc)
    for pin in pins:
        if _key(str(pin.get("harness") or ""), str(pin.get("sessionId") or "")) == (
            key_harness,
            key_id,
        ):
            pin["label"] = clean
            _write_doc({**doc, "pinnedSessions": pins}, home)
            return {"harness": key_harness, "sessionId": key_id, "pinned": True,
                    "label": clean}
    pins.append(
        {
            "harness": key_harness,
            "sessionId": key_id,
            "pinnedAt": _now(),
            "label": clean,
        }
    )
    _write_doc({**doc, "pinnedSessions": pins}, home)
    return {"harness": key_harness, "sessionId": key_id, "pinned": True, "label": clean}


def unpin_session(
    harness: str, session_id: str, home: Path | None = None
) -> dict[str, Any]:
    """Remove a pin; missing pins report ``pinned: False`` instead of failing."""
    key_harness, key_id = _key(harness, session_id)
    if not key_harness or not key_id:
        raise ValueError("harness and session_id must be non-empty strings")
    doc = _read_doc(home)
    pins = _pins_of(doc)
    kept = [
        pin
        for pin in pins
        if _key(str(pin.get("harness") or ""), str(pin.get("sessionId") or ""))
        != (key_harness, key_id)
    ]
    if len(kept) == len(pins):
        return {"harness": key_harness, "sessionId": key_id, "pinned": False}
    _write_doc({**doc, "pinnedSessions": kept}, home)
    return {"harness": key_harness, "sessionId": key_id, "pinned": False}


def decorate(sessions: list, home: Path | None = None) -> list:
    """Stamp ``is_pinned``/``pin_label`` onto summaries from the sidecar."""
    pins = get_pins(home)
    if not pins:
        return sessions
    decorated = []
    for session in sessions:
        key = _key(session.harness, session.session_id)
        if key not in pins:
            decorated.append(session)
            continue
        decorated.append(
            session.with_pin(pins[key]) if hasattr(session, "with_pin") else session
        )
    return decorated


__all__ = [
    "decorate",
    "get_pins",
    "list_pins",
    "pin_session",
    "policy_path",
    "unpin_session",
]
