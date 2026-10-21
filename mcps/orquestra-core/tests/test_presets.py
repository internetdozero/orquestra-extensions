"""Preset listing, apply and bridge-deploy tests against the mock ORQUESTRA_HOME."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orquestra_core import fleet, paths, presets


# ---------------------------------------------------------------------------
# list_presets — built-ins
# ---------------------------------------------------------------------------


def test_list_presets_returns_four_builtins(mock_home: Path) -> None:
    rows = presets.list_presets()
    ids = [r["id"] for r in rows]
    assert "stealth" in ids
    assert "rust-dev" in ids
    assert "web-fullstack" in ids
    assert "full-power" in ids


def test_list_presets_builtin_flag(mock_home: Path) -> None:
    rows = presets.list_presets()
    builtin_ids = {r["id"] for r in rows if r.get("builtin")}
    assert builtin_ids == {"stealth", "rust-dev", "web-fullstack", "full-power"}


def test_list_presets_no_active_when_file_absent(mock_home: Path) -> None:
    # presets.json does not exist in the fixture; no preset should be active.
    rows = presets.list_presets()
    assert all(r["active"] is False for r in rows)


# ---------------------------------------------------------------------------
# list_presets — custom presets.json
# ---------------------------------------------------------------------------


def test_list_presets_merges_custom_entry(mock_home: Path) -> None:
    payload = {
        "active": None,
        "presets": [
            {
                "id": "my-preset",
                "name": "My Preset",
                "description": "Operator custom",
                "skills": ["rtk"],
                "mcps": ["orquestra-core"],
            }
        ],
    }
    paths.presets_path().write_text(json.dumps(payload), encoding="utf-8")

    rows = presets.list_presets()
    custom = next((r for r in rows if r["id"] == "my-preset"), None)
    assert custom is not None
    assert custom["builtin"] is False
    assert custom["active"] is False


def test_list_presets_marks_active_preset(mock_home: Path) -> None:
    payload = {"active": "stealth", "presets": []}
    paths.presets_path().write_text(json.dumps(payload), encoding="utf-8")

    rows = presets.list_presets()
    by_id = {r["id"]: r for r in rows}
    assert by_id["stealth"]["active"] is True
    assert by_id["rust-dev"]["active"] is False
    assert by_id["full-power"]["active"] is False


def test_list_presets_custom_does_not_shadow_builtin(mock_home: Path) -> None:
    """A custom entry with a built-in id must NOT appear as a second custom row."""
    payload = {
        "active": None,
        "presets": [{"id": "stealth", "name": "Shadowed"}],
    }
    paths.presets_path().write_text(json.dumps(payload), encoding="utf-8")

    rows = presets.list_presets()
    stealth_rows = [r for r in rows if r["id"] == "stealth"]
    assert len(stealth_rows) == 1
    assert stealth_rows[0]["builtin"] is True  # built-in wins


# ---------------------------------------------------------------------------
# apply_preset — happy path
# ---------------------------------------------------------------------------


def test_apply_known_preset_returns_report(mock_home: Path) -> None:
    report = presets.apply_preset("stealth")
    assert report["preset"] == "stealth"
    assert report["applied"] is True


def test_apply_all_builtin_presets(mock_home: Path) -> None:
    for pid in ("stealth", "rust-dev", "web-fullstack", "full-power"):
        report = presets.apply_preset(pid)
        assert report["applied"] is True, f"preset {pid!r} did not report applied=True"


# ---------------------------------------------------------------------------
# apply_preset — validation errors (no subprocess spawned)
# ---------------------------------------------------------------------------


def test_apply_empty_id_raises(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        presets.apply_preset("")


def test_apply_whitespace_id_raises(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        presets.apply_preset("   ")


def test_apply_path_traversal_raises(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="invalid preset_id"):
        presets.apply_preset("../etc/passwd")


def test_apply_uppercase_id_raises(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="invalid preset_id"):
        presets.apply_preset("Stealth")


def test_apply_too_long_id_raises(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="too long"):
        presets.apply_preset("a" * 65)


# ---------------------------------------------------------------------------
# apply_preset — unknown id propagates native binary error
# ---------------------------------------------------------------------------


def test_apply_unknown_preset_raises_runtime_error(mock_home: Path) -> None:
    with pytest.raises(RuntimeError, match="unknown preset"):
        presets.apply_preset("ghost-preset")


# ---------------------------------------------------------------------------
# deploy_bridge
# ---------------------------------------------------------------------------


def test_deploy_bridge_returns_deployed_true(mock_home: Path) -> None:
    report = fleet.deploy_bridge()
    assert report["deployed"] is True
    assert "harnesses" in report


# ---------------------------------------------------------------------------
# save_preset — create
# ---------------------------------------------------------------------------


def test_save_preset_creates_entry(mock_home: Path) -> None:
    saved = presets.save_preset(
        "My Preset", "Operator custom", skills=["rtk"], mcps=["orquestra-core"]
    )
    assert saved["id"] == "my-preset"
    assert saved["name"] == "My Preset"
    assert saved["description"] == "Operator custom"
    assert saved["skills"] == ["rtk"]
    assert saved["mcps"] == ["orquestra-core"]
    assert saved["icon"] == "custom"
    assert saved["builtin"] is False
    assert saved["harnessSkills"] == {} and saved["harnessMcps"] == {}

    stored = json.loads(paths.presets_path().read_text(encoding="utf-8"))
    assert [entry["id"] for entry in stored["custom"]] == ["my-preset"]

    rows = presets.list_presets()
    custom = next(r for r in rows if r["id"] == "my-preset")
    assert custom["builtin"] is False


def test_save_preset_captures_live_state_when_omitted(mock_home: Path) -> None:
    from orquestra_core import skills as skills_mod

    skills_mod.enable_skill("alpha", "global")
    saved = presets.save_preset("Live Capture")
    assert "alpha" in saved["skills"]
    assert "alpha-mcp" in saved["mcps"]  # globally enabled fixture server


def test_save_preset_updates_existing_entry(mock_home: Path) -> None:
    presets.save_preset("My Preset", skills=["rtk"])
    updated = presets.save_preset("My Preset", "New blurb", skills=["beta"])
    assert updated["id"] == "my-preset"
    assert updated["description"] == "New blurb"
    rows = presets.list_presets()
    assert len([r for r in rows if r["id"] == "my-preset"]) == 1


def test_save_preset_rejects_builtin_collision(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="built-in"):
        presets.save_preset("Stealth", skills=["rtk"])


def test_save_preset_needs_a_name(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="needs a name"):
        presets.save_preset("   ")


# ---------------------------------------------------------------------------
# delete_preset
# ---------------------------------------------------------------------------


def test_delete_preset_success(mock_home: Path) -> None:
    presets.save_preset("My Preset", skills=["rtk"])
    result = presets.delete_preset("my-preset")
    assert result == {
        "id": "my-preset",
        "deleted": True,
        "message": "Preset 'my-preset' deleted.",
    }
    assert "my-preset" not in [r["id"] for r in presets.list_presets()]


def test_delete_preset_resets_active(mock_home: Path) -> None:
    presets.save_preset("My Preset")
    stored = json.loads(paths.presets_path().read_text(encoding="utf-8"))
    stored["active"] = "my-preset"
    paths.presets_path().write_text(json.dumps(stored), encoding="utf-8")
    presets.delete_preset("my-preset")
    rest = json.loads(paths.presets_path().read_text(encoding="utf-8"))
    assert rest["active"] is None


def test_delete_preset_rejects_builtin(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="Cannot delete built-in"):
        presets.delete_preset("rust-dev")


def test_delete_preset_not_found(mock_home: Path) -> None:
    with pytest.raises(LookupError, match="not found"):
        presets.delete_preset("ghost-preset")


# ---------------------------------------------------------------------------
# server tools
# ---------------------------------------------------------------------------


def test_save_delete_tools_roundtrip(mock_home: Path) -> None:
    import asyncio

    from mcp.server.mcpserver.exceptions import ToolError

    from orquestra_core.server import server

    saved = asyncio.run(
        server.call_tool("orquestra_save_preset", {"name": "Tool Preset"})
    )
    assert saved.structured_content["id"] == "tool-preset"
    removed = asyncio.run(
        server.call_tool("orquestra_delete_preset", {"preset_id": "tool-preset"})
    )
    assert removed.structured_content["deleted"] is True
    with pytest.raises(ToolError) as refused:
        asyncio.run(
            server.call_tool("orquestra_delete_preset", {"preset_id": "stealth"})
        )
    assert "Cannot delete built-in" in str(refused.value)
