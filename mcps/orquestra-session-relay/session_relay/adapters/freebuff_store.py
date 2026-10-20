"""Bounded readers and mappers for Freebuff chat JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import Event, SearchHit, SessionSummary
from .base import clamp_limit
from ..paths import clip, iso_from_epoch_ms, iso_from_mtime, read_json, snippet

LARGE_BYTES = 16 * 1024 * 1024
TAIL_BYTES = 12 * 1024 * 1024
COUNT_BYTES = 4 * 1024 * 1024


def _tail_objects(path: Path) -> list[dict[str, Any]]:
    """Decode complete objects from the tail of a JSON array."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(0, size - TAIL_BYTES))
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []

    start = text.find('{"id"')
    if start < 0:
        return []
    decoder = json.JSONDecoder()
    messages: list[dict[str, Any]] = []
    index = start
    while index < len(text):
        while index < len(text) and text[index] in " \t\r\n,":
            index += 1
        if index >= len(text) or text[index] != "{":
            break
        try:
            value, index = decoder.raw_decode(text, index)
        except ValueError:
            break
        if isinstance(value, dict):
            messages.append(value)
    return messages


def load_messages(path: Path) -> list[dict[str, Any]]:
    """Read a chat transcript, keeping memory bounded for giant files."""
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size <= LARGE_BYTES:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    return _tail_objects(path)


def count_user_messages(path: Path) -> int | None:
    """Count user turns when the file is small; None means 'too big to scan'."""
    try:
        if path.stat().st_size > COUNT_BYTES:
            return None
    except OSError:
        return None
    return sum(1 for message in load_messages(path) if message.get("variant") == "user")


def message_text(message: dict[str, Any]) -> str:
    if message.get("content"):
        return str(message["content"])
    parts = [
        str(block.get("text") or "")
        for block in message.get("blocks") or []
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "\n".join(part for part in parts if part)


def events_from_messages(messages: list[dict[str, Any]]) -> list[Event]:
    """Map user/ai chat messages and tool blocks to relay events."""
    events: list[Event] = []
    for message in messages:
        variant = message.get("variant")
        if variant == "user":
            text = message_text(message)
            if text.strip():
                events.append(Event("user", clip(text, 900)))
            continue
        if variant != "ai":
            continue
        text = message_text(message)
        if text.strip():
            events.append(Event("assistant", clip(text, 900)))
        for block in message.get("blocks") or []:
            if not isinstance(block, dict) or block.get("type") != "tool":
                continue
            args = json.dumps(block.get("input") or {}, ensure_ascii=False)
            output = str(block.get("output") or block.get("error") or "")
            events.append(
                Event(
                    "tool",
                    clip(f"{args}\n{output}", 900),
                    tool=str(block.get("toolName") or "tool"),
                    error=bool(block.get("error")),
                )
            )
    return events


def history_summary(history_path: Path, prompts: list[str], harness: str) -> SessionSummary:
    """Synthetic session for harnesses that only keep a flat prompt list."""
    return SessionSummary(
        harness=harness,
        session_id="prompt-history",
        title=clip(prompts[-1], 120),
        updated_at=iso_from_mtime(history_path),
        turns_count=len(prompts),
        project=None,
        source=str(history_path),
    )


def search_prompts(
    history_path: Path, prompts: list[str], needle: str, limit: int
) -> list[SearchHit]:
    """Keyword search over the flat prompt list, newest first."""
    hits: list[SearchHit] = []
    for prompt in reversed(prompts):
        if needle.lower() not in prompt.lower():
            continue
        hits.append(
            SearchHit(
                harness="freebuff",
                session_id="prompt-history",
                title=clip(prompt, 120),
                snippet=snippet(prompt, needle),
                updated_at=iso_from_mtime(history_path),
            )
        )
        if len(hits) >= clamp_limit(limit, 10):
            break
    return hits


def summarize_chat(path: Path, harness: str) -> SessionSummary:
    """Build a summary from chat-meta, falling back to the first message."""
    chat = path.parent
    meta = read_json(chat / "chat-meta.json") or {}
    title = str(meta.get("firstPrompt") or "")
    users = count_user_messages(path)
    if not title:
        messages = load_messages(path)[:1]
        title = message_text(messages[0]) if messages else ""
    return SessionSummary(
        harness=harness,
        session_id=chat.name,
        title=clip(title, 120) or f"Freebuff chat {chat.name}",
        updated_at=iso_from_epoch_ms(meta.get("messagesMtimeMs")) or iso_from_mtime(path),
        turns_count=users if users is not None else int(meta.get("messageCount") or 0),
        project=chat.parents[1].name,
        source=str(path),
    )
