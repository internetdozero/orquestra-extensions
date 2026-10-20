"""Map Grok chat history and subagent output into relay events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import Event
from ..paths import clip, iso_from_epoch_seconds, read_json, read_jsonl
from .grok_store import safe_file

_TOOL_ARG_KEYS = ("command", "target_file", "path", "query", "pattern", "description")


def _stamp(record: dict[str, Any]) -> str | None:
    for key in ("timestamp", "ts", "created_at", "time"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return iso_from_epoch_seconds(value)
    return None


def _text(content: Any) -> str:
    """Flatten Grok string or content-block message payloads."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return _text(content.get("text") or content.get("content") or "")
    if isinstance(content, list):
        parts = [_text(block) for block in content]
        return "\n".join(part for part in parts if part.strip())
    return ""


def _tool_args(raw: Any) -> str:
    data: Any = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except ValueError:
            return raw
    if not isinstance(data, dict):
        return str(data or "")
    for key in _TOOL_ARG_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return json.dumps(data, ensure_ascii=False)


def _backend_tool(record: dict[str, Any], stamp: str | None) -> Event | None:
    kind = record.get("kind") if isinstance(record.get("kind"), dict) else {}
    action = kind.get("action") if isinstance(kind.get("action"), dict) else {}
    name = str(kind.get("tool_type") or "backend_tool")
    text = _tool_args(action) if action else ""
    if not text.strip():
        return None
    return Event("tool", clip(text, 900), tool=name, timestamp=stamp)


def chat_events(path: Path) -> list[Event]:
    """Convert one Grok chat_history.jsonl stream into ordered events."""
    events: list[Event] = []
    tools: dict[str, str] = {}
    for record in read_jsonl(path):
        kind = record.get("type")
        stamp = _stamp(record)
        if kind == "user":
            text = _text(record.get("content"))
            if text.strip():
                events.append(Event("user", clip(text, 900), timestamp=stamp))
        elif kind == "assistant":
            text = _text(record.get("content"))
            if text.strip():
                events.append(Event("assistant", clip(text, 900), timestamp=stamp))
            for call in record.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                name = str(call.get("name") or "tool")
                call_id = str(call.get("id") or "")
                if call_id:
                    tools[call_id] = name
                events.append(
                    Event(
                        "tool",
                        clip(_tool_args(call.get("arguments")), 900),
                        tool=name,
                        timestamp=stamp,
                    )
                )
        elif kind == "tool_result":
            name = tools.get(str(record.get("tool_call_id") or ""), "tool_result")
            text = _text(record.get("content"))
            events.append(Event("tool", clip(text, 900), tool=name, timestamp=stamp))
        elif kind == "backend_tool_call":
            event = _backend_tool(record, stamp)
            if event is not None:
                events.append(event)
    return events


def subagent_events(directory: Path, root: Path) -> list[Event]:
    """Render an unindexed subagent folder (meta.json + output.json) as events."""
    events: list[Event] = []
    meta_file = safe_file(directory / "meta.json", root)
    output_file = safe_file(directory / "output.json", root)
    meta = read_json(meta_file) if meta_file is not None else None
    output = read_json(output_file) if output_file is not None else None
    if isinstance(meta, dict):
        prompt = str(meta.get("prompt") or "").strip()
        if prompt:
            events.append(
                Event("user", clip(prompt, 900), timestamp=str(meta.get("started_at") or "") or None)
            )
    text = output.get("output") if isinstance(output, dict) else output
    if isinstance(text, str) and text.strip():
        stamp = None
        if isinstance(meta, dict):
            stamp = str(meta.get("completed_at") or meta.get("started_at") or "") or None
        events.append(Event("assistant", clip(text, 900), timestamp=stamp))
    return events
