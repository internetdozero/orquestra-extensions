"""Skills, MCP catalog, master instructions and fleet state against a mock home."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from orquestra_core import catalog, fleet, instructions, paths, skills


def _link(home: Path, scope: str, skill: str) -> Path:
    return home / "active" / scope / skill


def test_list_skills_reports_metadata(mock_home: Path) -> None:
    rows = skills.list_skills("global")
    assert [row["id"] for row in rows] == ["alpha", "beta", "gamma"]

    alpha = rows[0]
    assert alpha["name"] == "Alpha Skill"
    assert alpha["description"] == "First fixture skill for projection tests."
    assert alpha["tokens"] > 1
    assert alpha["enabled"] is False
    assert alpha["is_inherited"] is False
    assert rows[2]["description"].startswith("Gamma has no frontmatter")


def test_enable_global_projects_every_scope(mock_home: Path) -> None:
    result = skills.enable_skill("alpha", "global")
    assert set(result["changed"]) == {"global", "codex", "claude"}
    assert result["enabled"] is True
    assert result["tokens"] == skills.list_skills("global")[0]["tokens"]

    for scope in ("global", "codex", "claude"):
        link = _link(mock_home, scope, "alpha")
        assert link.is_symlink()
        assert os.readlink(link) == str(mock_home / "skills-library" / "alpha")

    codex = {row["id"]: row for row in skills.list_skills("codex")}["alpha"]
    assert codex["enabled"] is True
    assert codex["is_inherited"] is True


def test_enable_is_idempotent(mock_home: Path) -> None:
    skills.enable_skill("beta", "global")
    again = skills.enable_skill("beta", "global")
    assert again["changed"] == []


def test_disable_global_removes_every_link(mock_home: Path) -> None:
    skills.enable_skill("alpha", "global")
    result = skills.disable_skill("alpha", "global")
    assert set(result["removed"]) == {"global", "codex", "claude"}
    assert result["tokens_saved"] > 0
    for scope in ("global", "codex", "claude"):
        assert not _link(mock_home, scope, "alpha").is_symlink()


def test_scope_enable_stays_scoped(mock_home: Path) -> None:
    result = skills.enable_skill("beta", "codex")
    assert result["changed"] == ["codex"]
    assert _link(mock_home, "codex", "beta").is_symlink()
    assert not _link(mock_home, "global", "beta").exists()
    assert not _link(mock_home, "claude", "beta").exists()

    scoped = {row["id"]: row for row in skills.list_skills("codex")}["beta"]
    assert scoped["enabled"] is True
    assert scoped["is_inherited"] is False
    assert skills.list_skills("global")[1]["enabled"] is False


def test_unknown_skill_and_scope_are_rejected(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="unknown scope"):
        skills.list_skills("nope")
    with pytest.raises(ValueError, match="not found"):
        skills.enable_skill("ghost", "global")
    with pytest.raises(ValueError, match="invalid skill id"):
        skills.enable_skill("../escape", "global")


def test_real_directory_is_never_clobbered(mock_home: Path) -> None:
    (mock_home / "active" / "claude" / "beta").mkdir()
    with pytest.raises(ValueError, match="real directory"):
        skills.enable_skill("beta", "claude")


def test_harness_ids_come_from_the_tree(mock_home: Path) -> None:
    assert paths.harness_ids() == ["claude", "codex"]
    assert paths.active_scope("global") == mock_home / "active" / "global"


def test_list_mcps_reads_catalog(mock_home: Path) -> None:
    rows = catalog.list_mcps()
    assert [row["id"] for row in rows] == ["alpha-mcp", "beta-mcp"]
    assert rows[0]["globalEnabled"] is True
    assert rows[1]["enabledHarnesses"] == ["codex"]
    assert rows[1]["args"] == ["--stdio"]


def test_toggle_mcp_sets_state_and_deploys(mock_home: Path) -> None:
    result = catalog.toggle_mcp("alpha-mcp", "global", False)
    assert result["changed"] == [str(mock_home / "codex" / "config.toml")]
    assert result["targets"] == 1
    assert catalog.find_mcp("alpha-mcp")["globalEnabled"] is False

    assert Path(result["backup"]).is_file()
    calls = (mock_home / "binary-calls.log").read_text().splitlines()
    assert calls == ["--mcp-deploy"]


def test_toggle_mcp_rejects_unknown_id(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="unknown MCP server"):
        catalog.toggle_mcp("ghost-mcp", "global", True)
    assert not (mock_home / "binary-calls.log").exists()


def test_harness_toggle_appends_and_removes(mock_home: Path) -> None:
    catalog.toggle_mcp("alpha-mcp", "global", False)
    catalog.toggle_mcp("alpha-mcp", "codex", True)
    assert catalog.find_mcp("alpha-mcp")["enabledHarnesses"] == ["codex"]
    catalog.toggle_mcp("alpha-mcp", "codex", False)
    assert catalog.find_mcp("alpha-mcp")["enabledHarnesses"] == []


def test_harness_cannot_opt_out_of_a_global_server(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="inherited from Global"):
        catalog.toggle_mcp("alpha-mcp", "codex", False)
    with pytest.raises(ValueError, match="unknown scope"):
        catalog.toggle_mcp("alpha-mcp", "nope", True)


def test_read_instructions(mock_home: Path) -> None:
    text = instructions.read_instructions()
    assert text.startswith("# Global Agent Instructions")
    assert "## Workflow" in text


def test_append_mission_rule_lands_in_section(mock_home: Path) -> None:
    before = instructions.read_instructions()
    result = instructions.append_mission_rule("Workflow", "Run rtk before the test suite")
    assert result["changed"] is True
    assert result["lines_added"] == 1
    assert Path(result["backup"]).read_text() == before

    after = instructions.read_instructions()
    workflow = after.split("## Workflow", 1)[1].split("## Tail", 1)[0]
    assert "- Inspect before editing." in workflow
    assert "- Run rtk before the test suite" in workflow
    assert "## Tail\n- Keep patches small." in after
    assert after.split("## Persona", 1)[1].split("## Workflow", 1)[0].strip() == (
        "- Address the operator as senhor."
    )


def test_append_mission_rule_creates_missing_section(mock_home: Path) -> None:
    instructions.append_mission_rule("Mission", "Ship the control plane")
    text = instructions.read_instructions()
    assert text.rstrip().endswith("## Mission\n- Ship the control plane")


def test_append_mission_rule_rejects_blank_input(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="section_title"):
        instructions.append_mission_rule("  ", "value")
    with pytest.raises(ValueError, match="rule_content"):
        instructions.append_mission_rule("Workflow", "  \n ")


def test_fleet_status_summarises_bridge(mock_home: Path) -> None:
    report = fleet.fleet_status()
    assert report["count"] == 2
    assert report["bridged"] == 1
    assert report["unbridged"] == ["claude"]
    assert set(report["harnesses"][0]) == set(fleet.FIELDS)


def test_catalog_missing_file_is_readable_error(mock_home: Path) -> None:
    (mock_home / "mcps.json").unlink()
    with pytest.raises(ValueError, match="catalog not found"):
        catalog.list_mcps()
    (mock_home / "mcps.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        catalog.list_mcps()
