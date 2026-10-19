"""Kilo, Copilot and Hermes adapters: sessions, events and read-only access."""

from __future__ import annotations

from builders import snapshot
from store_builders import make_copilot, make_hermes, make_kilo
from session_relay.adapters import (
    ADAPTERS,
    CopilotAdapter,
    HermesAdapter,
    KiloAdapter,
)


def _kilo_sessions() -> list[dict]:
    return [
        {
            "id": "kilo_new000000000000001",
            "title": "Kilo deploy fix",
            "directory": "/work/kilo",
            "created": 1_790_000_200_000,
            "updated": 1_790_000_300_000,
            "messages": [
                {
                    "role": "user",
                    "parts": [{"type": "text", "text": "Fix the kilo deploy"}],
                },
                {
                    "role": "assistant",
                    "parts": [{"type": "text", "text": "On it, patching now."}],
                },
            ],
        },
        {
            "id": "kilo_old000000000000002",
            "title": "Old kilo note",
            "created": 1_790_000_000_000,
            "updated": 1_790_000_010_000,
            "messages": [
                {"role": "user", "parts": [{"type": "text", "text": "Old question"}]},
            ],
        },
    ]


def test_registry_holds_nine_adapters():
    ids = [adapter.id for adapter in ADAPTERS]
    assert ids == [
        "antigravity", "claude", "codex", "copilot", "freebuff", "grok",
        "hermes", "kilo", "opencode",
    ]


def test_kilo_lists_loads_and_searches(relay_home):
    make_kilo(relay_home, _kilo_sessions())
    adapter = KiloAdapter(relay_home)
    assert adapter.available() is True

    sessions = adapter.list_sessions()
    assert [item.title for item in sessions] == ["Kilo deploy fix", "Old kilo note"]
    assert sessions[0].turns_count == 2
    assert sessions[0].project == "/work/kilo"

    detail = adapter.load_session("latest")
    assert detail is not None
    assert detail.summary.title == "Kilo deploy fix"
    assert any("kilo deploy" in event.text for event in detail.events)

    hits = adapter.search("deploy")
    assert hits and hits[0].session_id.startswith("kilo_new")
    assert adapter.load_session("missing") is None


def test_kilo_store_is_never_modified(relay_home):
    make_kilo(relay_home, _kilo_sessions())
    before = snapshot(relay_home)
    adapter = KiloAdapter(relay_home)
    adapter.list_sessions()
    adapter.load_session("latest")
    adapter.search("deploy")
    assert snapshot(relay_home) == before


def test_kilo_missing_store_is_friendly(relay_home):
    adapter = KiloAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
    assert adapter.search("x") == []


def test_copilot_lists_turns_and_searches(relay_home):
    make_copilot(
        relay_home,
        [
            {
                "id": "copilot-aaa",
                "cwd": "/work/copilot",
                "summary": "Check recent pushes",
                "updated": "2026-10-19T10:00:00Z",
                "turns": [
                    {"user": "Oi, check pushes", "assistant": "All green."},
                    {"user": "Ship it", "assistant": "Shipped."},
                ],
            }
        ],
    )
    adapter = CopilotAdapter(relay_home)
    assert adapter.available() is True

    sessions = adapter.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].title == "Check recent pushes"
    assert sessions[0].turns_count == 2
    assert sessions[0].project == "/work/copilot"

    detail = adapter.load_session("latest")
    assert detail is not None
    assert [event.role for event in detail.events] == ["user", "assistant"] * 2
    assert "check pushes" in detail.events[0].text

    hits = adapter.search("pushes")
    assert len(hits) == 1 and hits[0].session_id == "copilot-aaa"
    assert adapter.load_session("missing") is None


def test_copilot_lock_files_do_not_break_reads(relay_home):
    make_copilot(relay_home, [{"id": "copilot-live", "summary": "Live work"}])
    locks = relay_home / ".copilot" / "session-state" / ".session-operation-locks"
    locks.mkdir(parents=True, exist_ok=True)
    (locks / "copilot-live.lock").write_text("")
    adapter = CopilotAdapter(relay_home)
    assert adapter.active_locks() == {"copilot-live"}
    assert [item.session_id for item in adapter.list_sessions()] == ["copilot-live"]
    assert adapter.load_session("copilot-live") is not None


def test_copilot_missing_store_is_friendly(relay_home):
    adapter = CopilotAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
    assert adapter.search("x") == []


def test_hermes_lists_messages_and_tools(relay_home):
    make_hermes(
        relay_home,
        [
            {
                "id": "hermes-aaa",
                "title": "Hermes deploy review",
                "started": 1_790_000_000.0,
                "ended": 1_790_000_200.0,
                "messages": [
                    {"role": "user", "content": "Review the deploy"},
                    {"role": "assistant", "content": "Looks good"},
                    {"role": "assistant", "content": "ls output", "tool": "shell"},
                ],
            }
        ],
    )
    adapter = HermesAdapter(relay_home)
    assert adapter.available() is True

    sessions = adapter.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].title == "Hermes deploy review"
    assert sessions[0].updated_at is not None

    detail = adapter.load_session("latest")
    assert detail is not None
    tools = [event.tool for event in detail.events if event.role == "tool"]
    assert tools == ["shell"]
    assert any("deploy" in event.text for event in detail.events)

    hits = adapter.search("deploy")
    assert len(hits) == 1 and hits[0].session_id == "hermes-aaa"
    assert adapter.load_session("missing") is None


def test_hermes_log_files_cover_missing_db(relay_home):
    logs = relay_home / ".hermes" / "sessions"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "hermes-log-1.json").write_text(
        '{"display_name": "Logged work", "ended_at": "2026-10-19T10:00:00Z",'
        ' "messages": [{"role": "user", "content": "Hello from logs"}]}'
    )
    adapter = HermesAdapter(relay_home)
    assert adapter.available() is True
    sessions = adapter.list_sessions()
    assert [item.session_id for item in sessions] == ["hermes-log-1"]
    detail = adapter.load_session("latest")
    assert detail is not None and "Hello from logs" in detail.events[0].text


def test_hermes_missing_store_is_friendly(relay_home):
    adapter = HermesAdapter(relay_home)
    assert adapter.available() is False
    assert adapter.list_sessions() == []
    assert adapter.load_session("latest") is None
    assert adapter.search("x") == []
