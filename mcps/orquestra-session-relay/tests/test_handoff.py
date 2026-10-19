"""Handoff brief: goal, files, blocker and next steps."""

from __future__ import annotations

from session_relay.handoff import extract_files, synthesize
from session_relay.models import Event, SessionDetail, SessionSummary


def _detail() -> SessionDetail:
    summary = SessionSummary(
        harness="codex",
        session_id="session-abc",
        title="Ship the vault",
        updated_at="2026-10-17T11:00:00Z",
        turns_count=1,
        project="/work/proj",
    )
    events = [
        Event("user", "Ship the vault"),
        Event(
            "tool",
            'files: "/work/proj/src/a.ts", file:///work/proj/src/b.ts',
            tool="file_change",
        ),
        Event("tool", "npm test\nFAIL src/a.test.ts", tool="shell", error=True),
        Event("assistant", "Need to fix the migration first."),
    ]
    return SessionDetail(summary=summary, events=events)


def test_brief_contains_every_required_section():
    brief = synthesize(_detail())
    assert brief.startswith("# Handoff — codex · session-abc")
    assert "## Goal" in brief and "Ship the vault" in brief
    assert "## Files touched" in brief
    assert "/work/proj/src/a.ts" in brief
    assert "/work/proj/src/b.ts" in brief
    assert "## Last observed state" in brief
    assert "## Blocker" in brief and "npm test" in brief
    assert "## Suggested next steps" in brief
    assert "inspect_session(harness='codex', session_id='session-abc')" in brief
    assert "Check `git status`" in brief


def test_extract_files_dedupes_and_skips_system_paths():
    events = [
        Event("tool", '"/work/proj/a.ts" then /work/proj/a.ts again'),
        Event("tool", "/usr/lib/python3.14/os.py /work/proj/b.ts"),
        Event("tool", "see file:///work/proj/c.ts"),
    ]
    files = extract_files(events)
    assert files == ["/work/proj/a.ts", "/work/proj/b.ts", "/work/proj/c.ts"]


def test_empty_session_stays_actionable():
    summary = SessionSummary("claude", "empty", "Empty session")
    brief = synthesize(SessionDetail(summary=summary, events=[]))
    assert "## Goal" in brief and "Empty session" in brief
    assert "None recorded" in brief
    assert "No events loaded." in brief
    assert "inspect_session(harness='claude', session_id='empty')" in brief
