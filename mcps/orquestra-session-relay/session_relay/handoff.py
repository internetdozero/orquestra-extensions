"""Turn a session's events into an executive baton-pass brief."""

from __future__ import annotations

import re

from .models import Event, SessionDetail
from .paths import clip

_FILE_URL = re.compile(r"file://(/[^\s\"'`]+)")
_QUOTED_PATH = re.compile(r"[\"'](/(?:[^\"'\n]{2,240}))[\"']")
_TOKEN_PATH = re.compile(
    r"(?<![A-Za-z0-9_:/.-])(/[A-Za-z0-9._@+-][^\s\\\"'`,;:()\[\]{}<>]*)"
)
_STOPWORDS = ("/dev/", "/proc/", "/sys/", "/usr/", "/etc/", "/bin/", "/lib/")


def extract_files(events: list[Event], limit: int = 20) -> list[str]:
    """Pull candidate file paths out of tool output, preserving first-seen order."""
    seen: list[str] = []
    for event in events:
        text = event.text or ""
        candidates = (
            _FILE_URL.findall(text) + _QUOTED_PATH.findall(text) + _TOKEN_PATH.findall(text)
        )
        for candidate in candidates:
            path = candidate.rstrip(".,;:\\\"'").strip()
            if len(path) < 4 or path.startswith(_STOPWORDS) or path in seen:
                continue
            seen.append(path)
            if len(seen) >= limit:
                return seen
    return seen


def _first_user(events: list[Event]) -> str:
    for event in events:
        if event.role == "user" and event.text.strip():
            return clip(event.text, 600)
    return ""


def _blocker(events: list[Event]) -> Event | None:
    for event in reversed(events):
        if event.error:
            return event
    return None


def _describe(event: Event) -> str:
    label = f"{event.tool} ({event.role})" if event.tool else event.role
    marker = " (error)" if event.error else ""
    text = clip(event.text.replace("\n", " / "), 240)
    return f"- `{label}`{marker} — {text}"


def synthesize(detail: SessionDetail) -> str:
    """Render the Goal / Files / State / Blocker / Next-steps markdown brief."""
    summary = detail.summary
    events = detail.events
    files = extract_files(events)
    blocker = _blocker(events)
    goal = _first_user(events) or clip(summary.title, 600)
    last_events = events[-3:]
    last_assistant = next(
        (event for event in reversed(events) if event.role == "assistant" and event.text),
        None,
    )

    lines = [
        f"# Handoff — {summary.harness} · {summary.session_id}",
        "",
        f"**Session:** {summary.title}",
    ]
    if summary.project:
        lines.append(f"**Project:** `{summary.project}`")
    if summary.updated_at:
        lines.append(f"**Updated:** {summary.updated_at}")
    lines.append(f"**Recorded turns:** {summary.turns_count} · **Events loaded:** {len(events)}")
    lines.extend(["", "## Goal", "", goal or "_No user prompt recorded._", ""])

    lines.append("## Files touched")
    lines.append("")
    if files:
        lines.extend(f"- `{path}`" for path in files)
    else:
        lines.append("- None recorded in the loaded turns.")
    lines.append("")

    lines.append("## Last observed state")
    lines.append("")
    if last_events:
        lines.extend(_describe(event) for event in last_events)
    else:
        lines.append("- No events loaded.")
    lines.append("")

    lines.append("## Blocker")
    lines.append("")
    if blocker is not None:
        label = blocker.tool or blocker.role
        lines.append(f"{label}: {clip(blocker.text.replace(chr(10), ' / '), 400)}")
    else:
        lines.append("No explicit error was recorded; the session appears to have stopped mid-task.")

    lines.extend(["", "## Suggested next steps", ""])
    steps: list[str] = []
    if blocker is not None:
        steps.append("Resolve the blocker above, then re-run the command or test that produced it.")
    if files:
        steps.append(
            f"Review the current state of `{files[-1]}` and the surrounding diff before editing."
        )
    if summary.project:
        steps.append(f"Check `git status` and recent diffs in `{summary.project}`.")
    if last_assistant is not None:
        steps.append(f"Continue from the agent's last message: “{clip(last_assistant.text, 180)}”")
    steps.append(
        f"Call inspect_session(harness='{summary.harness}', session_id='{summary.session_id}') "
        "for the full transcript."
    )
    lines.extend(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    return "\n".join(lines) + "\n"


__all__ = ["extract_files", "synthesize"]
