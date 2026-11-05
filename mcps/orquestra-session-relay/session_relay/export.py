"""Export complete session transcripts to structured Markdown or JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import discovery


def _to_markdown(detail: Any) -> str:
    summary = detail.summary
    events = detail.events
    started = (
        events[0].timestamp if events and events[0].timestamp else summary.updated_at
    )
    updated = summary.updated_at

    lines = [
        "---",
        f"harness: {summary.harness}",
        f"id: {summary.session_id}",
        f"title: {summary.title}",
        f"started_at: {started or 'unknown'}",
        f"updated_at: {updated or 'unknown'}",
        f"turns_count: {len(events)}",
        "---",
        "",
        f"# Session: {summary.title}",
        "",
        f"**Harness:** `{summary.harness}`  ",
        f"**Session ID:** `{summary.session_id}`  ",
        f"**Updated:** `{updated or 'unknown'}`",
        "",
    ]

    for event in events:
        role = event.role.capitalize()
        lines.append(f"### {role}")
        if event.timestamp:
            lines.append(f"_{event.timestamp}_  \n")
        if event.tool:
            lines.append(f"**Tool:** `{event.tool}`  \n")
        lines.append(event.text or "")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def export_session(
    harness: str,
    session_id: str = "latest",
    format: str = "markdown",
    output_path: str | None = None,
) -> dict[str, Any]:
    """Export complete unabridged session transcript to Markdown or JSON."""
    fmt = (format or "markdown").lower().strip()
    if fmt not in ("markdown", "json"):
        raise ValueError(f"unsupported format '{format}'; must be 'markdown' or 'json'")

    adapter = discovery.get_adapter(harness)
    if not adapter.available():
        raise ValueError(f"no {adapter.label} session store was found on this machine")

    # Load unabridged session (max_turns=0 loads all turns without limit)
    detail = adapter.load_session(session_id, max_turns=0)
    if detail is None:
        raise ValueError(f"session '{session_id}' was not found for {adapter.id}")

    if fmt == "markdown":
        rendered = _to_markdown(detail)
    else:
        rendered = json.dumps(detail.as_dict(max_text=None), indent=2) + "\n"

    byte_count = len(rendered.encode("utf-8"))

    if output_path is not None:
        clean_path = Path(output_path).expanduser().resolve()
        clean_path.parent.mkdir(parents=True, exist_ok=True)
        clean_path.write_text(rendered, encoding="utf-8")
        return {
            "written": True,
            "path": str(clean_path),
            "bytes": byte_count,
            "format": fmt,
            "session_id": detail.summary.session_id,
            "harness": adapter.id,
        }

    return {
        "written": False,
        "format": fmt,
        "session_id": detail.summary.session_id,
        "harness": adapter.id,
        "bytes": byte_count,
        "content": rendered,
    }


__all__ = ["export_session"]
