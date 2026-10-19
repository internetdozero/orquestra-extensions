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
