"""Map Codex thread item rows into relay events."""

from __future__ import annotations

import json
from typing import Any, Iterable

from ..models import Event
from ..paths import clip, iso_from_epoch_ms


def escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def message_text(item_json: str) -> str:
    """Pull readable text out of a Codex item payload."""
    try:
        data = json.loads(item_json)
    except (TypeError, ValueError):
        return ""
    if isinstance(data.get("text"), str):
        return data["text"]
    content = data.get("content")
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return ""


def item_events(rows: Iterable[Any]) -> list[Event]:
    """Convert thread_items rows (type, item_json, created_at_ms) to events."""
    events: list[Event] = []
    for row in rows:
        item_type = row["item_type"]
        try:
            data = json.loads(row["item_json"] or "{}")
        except (TypeError, ValueError):
            continue
        stamp = iso_from_epoch_ms(row["created_at_ms"])

        if item_type == "userMessage":
            text = message_text(row["item_json"])
            if text.strip():
                events.append(Event("user", clip(text, 900), timestamp=stamp))
        elif item_type == "agentMessage":
            text = data.get("text") or message_text(row["item_json"])
            if text.strip():
                events.append(Event("assistant", clip(text, 900), timestamp=stamp))
        elif item_type == "commandExecution":
            command = data.get("command", "")
            output = data.get("aggregatedOutput") or ""
            exit_code = data.get("exitCode")
            events.append(
                Event(
                    "tool",
                    clip(f"$ {command}\n{output}", 900),
                    tool="shell",
                    timestamp=stamp,
                    error=exit_code not in (0, None),
                )
            )
        elif item_type == "fileChange":
            paths = [
                change.get("path", "")
                for change in data.get("changes") or []
                if isinstance(change, dict)
            ]
            events.append(
                Event(
                    "tool",
                    clip("files: " + ", ".join(paths), 900),
                    tool="file_change",
                    timestamp=stamp,
                )
            )
        elif item_type == "mcpToolCall":
            args = clip(json.dumps(data.get("arguments") or {}, ensure_ascii=False), 300)
            result = data.get("result") or data.get("error") or ""
            events.append(
                Event(
                    "tool",
                    clip(f"{args}\n{result}", 900),
                    tool=f"{data.get('server', 'mcp')}.{data.get('tool', 'call')}",
                    timestamp=stamp,
                    error=bool(data.get("error")),
                )
            )
        elif item_type == "webSearch":
            events.append(
                Event(
                    "tool",
                    clip(str(data.get("query") or data.get("text") or ""), 500),
                    tool="web_search",
                    timestamp=stamp,
                )
            )
    return events
