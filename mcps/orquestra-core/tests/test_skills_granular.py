"""Unit tests for granular skills CLI capabilities exposed to AI agents."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from orquestra_core import server, skill_admin, skills


def _call(name: str, **arguments: Any) -> Any:
    return asyncio.run(server.server.call_tool(name, arguments))


def test_list_skills_with_filters(mock_home: Path) -> None:
    # mock_home has alpha, beta, gamma from conftest
    # Let's create an official skill and one with scripts
    skill_admin.create_skill(
        "orquestra-helper",
        "Orquestra Helper",
        "Official helper skill",
        "# Helper\nOfficial tool instructions.",
        {"run.sh": "#!/bin/sh\necho ok\n"},
    )

    all_skills = skills.list_skills()
    assert any(s["id"] == "orquestra-helper" for s in all_skills)

    # filter_text
    filtered = skills.list_skills(filter_text="helper")
    assert len(filtered) == 1
    assert filtered[0]["id"] == "orquestra-helper"

    # official_only
    official = skills.list_skills(official_only=True)
    assert all(s["id"].startswith("orquestra-") for s in official)
    assert any(s["id"] == "orquestra-helper" for s in official)

    # has_scripts_only
    with_scripts = skills.list_skills(has_scripts_only=True)
    assert any(s["id"] == "orquestra-helper" for s in with_scripts)
    helper = next(s for s in with_scripts if s["id"] == "orquestra-helper")
    assert helper["has_scripts"] is True
    assert helper["script_files"] == ["run.sh"]


def test_inspect_skill(mock_home: Path) -> None:
    skill_admin.create_skill(
        "inspectable-skill",
        "Inspectable Skill",
        "Detailed skill for testing inspection",
        "# Inspectable\nBody content for inspection.",
        {"tool.py": "print('inspect')"},
    )

    info = skills.inspect_skill("inspectable-skill")
    assert info["id"] == "inspectable-skill"
    assert info["name"] == "Inspectable Skill"
    assert info["description"] == "Detailed skill for testing inspection"
    assert info["tokens"] > 0
    assert info["has_scripts"] is True
    assert info["scripts"] == ["tool.py"]
    assert "global" in info["scopes"]
    assert info["active_in_scope"] is False

    with pytest.raises(ValueError, match="not found"):
        skills.inspect_skill("non-existent-skill")


def test_get_and_set_skill_content(mock_home: Path) -> None:
    # Read existing skill
    res = skills.get_skill_content("alpha")
    assert res["id"] == "alpha"
    assert "name: Alpha" in res["content"]
    assert res["tokens"] > 0
    assert res["bytes"] > 0

    # Write new valid content
    new_content = "---\nname: Alpha Renamed\ndescription: Updated alpha skill\n---\n\n# Alpha Renamed\nNew body."
    update_res = skills.set_skill_content("alpha", new_content)
    assert update_res["written"] is True
    assert update_res["name"] == "Alpha Renamed"
    assert update_res["description"] == "Updated alpha skill"

    # Verify updated content persists
    verified = skills.get_skill_content("alpha")
    assert "Alpha Renamed" in verified["content"]

    # Validation errors on invalid content
    with pytest.raises(ValueError, match="must not be empty"):
        skills.set_skill_content("alpha", "   ")

    with pytest.raises(ValueError, match="must declare 'name' and 'description'"):
        skills.set_skill_content("alpha", "---\nname: OnlyName\n---\nMissing description")


def test_validate_skill_scenarios(mock_home: Path, tmp_path: Path) -> None:
    # 1. Valid skill from library
    valid = skill_admin.validate_skill("alpha")
    assert valid["valid"] is True
    assert valid["id"] == "alpha"
    assert valid["file_count"] >= 1

    # 2. Valid external directory
    ext_dir = tmp_path / "custom-skill"
    ext_dir.mkdir()
    (ext_dir / "SKILL.md").write_text("---\nname: Custom\ndescription: Custom skill\n---\n\n# Body\n")
    valid_ext = skill_admin.validate_skill(str(ext_dir))
    assert valid_ext["valid"] is True
    assert valid_ext["name"] == "Custom"

    # 3. Missing manifest
    empty_dir = tmp_path / "empty-skill"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match="missing SKILL.md"):
        skill_admin.validate_skill(str(empty_dir))

    # 4. Manifest missing description
    bad_dir = tmp_path / "bad-frontmatter"
    bad_dir.mkdir()
    (bad_dir / "SKILL.md").write_text("---\nname: Bad\n---\n# Missing desc\n")
    with pytest.raises(ValueError, match="frontmatter missing required field 'description'"):
        skill_admin.validate_skill(str(bad_dir))

    # 5. Non-existent path
    with pytest.raises(ValueError, match="not found"):
        skill_admin.validate_skill(str(tmp_path / "does-not-exist"))


def test_skills_summary_and_batch(mock_home: Path) -> None:
    summary_before = skills.skills_summary()
    assert summary_before["total_skills"] >= 3
    assert "global" in summary_before["scopes"]

    # Batch enable all
    batch_en = skills.batch_skills("enable", "global")
    assert batch_en["action"] == "enable"
    assert batch_en["count"] > 0

    summary_after = skills.skills_summary()
    assert summary_after["scopes"]["global"]["active"] == summary_after["total_skills"]

    # Batch disable all
    batch_dis = skills.batch_skills("disable", "global")
    assert batch_dis["action"] == "disable"
    assert batch_dis["count"] > 0

    summary_final = skills.skills_summary()
    assert summary_final["scopes"]["global"]["active"] == 0

    # Invalid batch action
    with pytest.raises(ValueError, match="action must be 'enable' or 'disable'"):
        skills.batch_skills("restart")


def test_import_skill_local(mock_home: Path, tmp_path: Path) -> None:
    source = tmp_path / "imported-skill"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: Imported Skill\ndescription: Skill imported from folder\n---\n\n# Imported\nInstructions."
    )
    (source / "scripts").mkdir()
    (source / "scripts" / "run.py").write_text("print('imported')\n")

    res = skill_admin.import_skill(str(source), enable=True)
    assert res["id"] == "imported-skill"
    assert res["imported"] is True
    assert res["enabled"] is True

    # Check that inspect sees it in library
    inspect_res = skills.inspect_skill("imported-skill")
    assert inspect_res["name"] == "Imported Skill"
    assert inspect_res["has_scripts"] is True

    # Re-importing existing should fail without overwrite
    with pytest.raises(ValueError, match="already exists"):
        skill_admin.import_skill(str(source))


def test_mcp_tools_roundtrip(mock_home: Path) -> None:
    # 1. orquestra_inspect_skill
    inspect_call = _call("orquestra_inspect_skill", skill_id="alpha")
    assert inspect_call.is_error is False
    assert inspect_call.structured_content["id"] == "alpha"

    # 2. orquestra_validate_skill
    val_call = _call("orquestra_validate_skill", target="alpha")
    assert val_call.is_error is False
    assert val_call.structured_content["valid"] is True

    # 3. orquestra_get_skill_content
    get_call = _call("orquestra_get_skill_content", skill_id="alpha")
    assert get_call.is_error is False
    assert "Alpha" in get_call.structured_content["content"]

    # 4. orquestra_set_skill_content
    new_doc = "---\nname: Alpha V2\ndescription: Alpha updated via MCP\n---\n\n# New\n"
    set_call = _call("orquestra_set_skill_content", skill_id="alpha", content=new_doc)
    assert set_call.is_error is False
    assert set_call.structured_content["name"] == "Alpha V2"

    # 5. orquestra_skills_summary
    sum_call = _call("orquestra_skills_summary")
    assert sum_call.is_error is False
    assert "total_skills" in sum_call.structured_content

    # 6. orquestra_batch_skills
    batch_call = _call("orquestra_batch_skills", action="enable", scope="global")
    assert batch_call.is_error is False
    assert batch_call.structured_content["action"] == "enable"

    # 7. orquestra_disable_skill with inherited_from_global check
    dis_call = _call("orquestra_disable_skill", skill_id="alpha", scope="claude")
    assert dis_call.is_error is False
    assert dis_call.structured_content["inherited_from_global"] is True
