"""Skill and MCP lifecycle: create, project, archive, remove."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from orquestra_core import catalog, catalog_admin, skill_admin, skills


def test_create_skill_writes_manifest_and_scripts(mock_home: Path) -> None:
    result = skill_admin.create_skill(
        "release-notes",
        "Release Notes",
        "Draft changelog entries: keep them scoped.",
        "# Release Notes\n\nSummarize the diff before writing.",
        {"draft.py": "print('draft')"},
    )
    assert result["created"] is True
    assert result["tokens"] > 0
    assert result["scripts"] == ["scripts/draft.py"]

    manifest = (mock_home / "skills-library" / "release-notes" / "SKILL.md").read_text()
    assert manifest.startswith("---\nname: Release Notes\n")
    assert 'description: "Draft changelog entries: keep them scoped."' in manifest
    assert manifest.endswith("Summarize the diff before writing.\n")
    assert (mock_home / "skills-library" / "release-notes" / "scripts" / "draft.py").read_text() == (
        "print('draft')\n"
    )

    listed = {row["id"]: row for row in skills.list_skills("global")}
    assert listed["release-notes"]["name"] == "Release Notes"
    assert listed["release-notes"]["enabled"] is False


def test_create_skill_rejects_duplicates_and_bad_ids(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="already exists"):
        skill_admin.create_skill("alpha", "Alpha", "Duplicate", "# Alpha")
    with pytest.raises(ValueError, match="skill_id"):
        skill_admin.create_skill("bad/id", "Bad", "Slash", "# Bad")
    with pytest.raises(ValueError, match="skill_id"):
        skill_admin.create_skill("under_score", "Bad", "Underscore", "# Bad")
    with pytest.raises(ValueError, match="instructions_markdown"):
        skill_admin.create_skill("blank-body", "Blank", "No body", "   ")


def test_create_skill_rolls_back_on_bad_script(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="script name"):
        skill_admin.create_skill(
            "rollback", "Rollback", "Fails midway", "# Body", {"../escape.py": "x"}
        )
    assert not (mock_home / "skills-library" / "rollback").exists()


def test_delete_skill_unlinks_scopes_and_archives(mock_home: Path) -> None:
    skills.enable_skill("alpha", "global")
    result = skill_admin.delete_skill("alpha")

    assert result["deleted"] is True
    assert {Path(path).parent.name for path in result["unlinked"]} == {"global", "codex", "claude"}
    for scope in ("global", "codex", "claude"):
        assert not os.path.lexists(mock_home / "active" / scope / "alpha")
    assert not (mock_home / "skills-library" / "alpha").exists()

    archived = Path(result["backup"])
    assert archived.parent.name.startswith("deleted-skills-")
    assert (archived / "SKILL.md").is_file()
    assert [row["id"] for row in skills.list_skills("global")] == ["beta", "gamma"]


def test_delete_skill_rejects_unknown_id(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        skill_admin.delete_skill("ghost")


def test_create_mcp_registers_and_deploys(mock_home: Path) -> None:
    result = catalog_admin.create_mcp(
        "gamma-mcp",
        "Gamma MCP",
        "Third fixture server.",
        "gamma",
        ["--stdio"],
        {"TOKEN": "x"},
        True,
    )
    assert result["created"] is True
    assert result["changed"] == [str(mock_home / "codex" / "config.toml")]
    assert result["globalEnabled"] is True

    data = json.loads((mock_home / "mcps.json").read_text())
    assert data["mcps"]["gamma-mcp"]["args"] == ["--stdio"]
    assert data["mcps"]["gamma-mcp"]["env"] == {"TOKEN": "x"}
    assert "gamma-mcp" in data["managedIds"]
    assert Path(result["backup"]).is_file()
    assert (mock_home / "binary-calls.log").read_text().splitlines() == ["--mcp-deploy"]


def test_create_mcp_rejects_duplicates_and_bad_input(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="already exists"):
        catalog_admin.create_mcp("alpha-mcp", "Alpha", "Duplicate", "alpha")
    with pytest.raises(ValueError, match="mcp_id"):
        catalog_admin.create_mcp("bad id", "Bad", "Space", "bad")
    with pytest.raises(ValueError, match="command"):
        catalog_admin.create_mcp("no-command", "No command", "Empty", "  ")
    assert not (mock_home / "binary-calls.log").exists()


def test_delete_mcp_removes_entry_and_redeploys(mock_home: Path) -> None:
    result = catalog_admin.delete_mcp("beta-mcp")
    assert result["deleted"] is True
    assert result["managed"] is False  # the deploy is what shrinks managedIds

    data = json.loads((mock_home / "mcps.json").read_text())
    assert "beta-mcp" not in data["mcps"]
    assert data["managedIds"] == ["alpha-mcp"]
    assert Path(result["backup"]).is_file()
    assert (mock_home / "binary-calls.log").read_text().splitlines() == ["--mcp-deploy"]
    assert [row["id"] for row in catalog.list_mcps()] == ["alpha-mcp"]


def test_delete_mcp_rejects_unknown_id(mock_home: Path) -> None:
    with pytest.raises(ValueError, match="unknown MCP server"):
        catalog_admin.delete_mcp("ghost-mcp")
    assert not (mock_home / "binary-calls.log").exists()
