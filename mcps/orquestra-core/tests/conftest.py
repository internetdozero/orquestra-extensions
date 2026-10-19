"""Throwaway ORQUESTRA_HOME trees and a fake native binary for the test suite."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

from orquestra_core import paths, skills

SCRATCH_ROOT = Path("/var/tmp/testing/orquestra-core-tests")

ALPHA = """---
name: Alpha Skill
description: First fixture skill for projection tests.
---

# Alpha

Body text that gives the estimator something to weigh: alpha beta gamma.
"""

BETA = """---
name: beta
description: Second fixture skill.
---

# Beta

Short body.
"""

GAMMA = """# Gamma

Gamma has no frontmatter, so its first prose line becomes the description.
"""

FAKE_BINARY = '''#!/usr/bin/env python3
"""Stand-in for the native orquestra binary inside the mock home."""

import json
import sys
from pathlib import Path

home = Path(__import__("os").environ["ORQUESTRA_HOME"])
args = sys.argv[1:]
(home / "binary-calls.log").open("a", encoding="utf-8").write(" ".join(args) + "\\n")

if args[:1] == ["--mcp-set"]:
    _, mcp_id, scope, state = args
    data = json.loads((home / "mcps.json").read_text())
    entry = data["mcps"][mcp_id]
    enabled = state == "on"
    if scope == "global":
        entry["globalEnabled"] = enabled
    else:
        harnesses = [item for item in entry.get("enabledHarnesses", []) if item != scope]
        if enabled:
            harnesses.append(scope)
        entry["enabledHarnesses"] = harnesses
    (home / "mcps.json").write_text(json.dumps(data, indent=2) + "\\n")
    print(json.dumps({"id": mcp_id, "scope": scope, "enabled": enabled}))
elif args == ["--mcp-deploy"]:
    data = json.loads((home / "mcps.json").read_text())
    data["managedIds"] = [item for item in data.get("managedIds", []) if item in data["mcps"]]
    (home / "mcps.json").write_text(json.dumps(data, indent=2))
    print(json.dumps({"changed": [str(home / "codex" / "config.toml")], "targets": 1, "servers": 2}))
elif args == ["--bridge-status"]:
    print(json.dumps([
        {"id": "codex", "label": "Codex", "installed": True, "supported": True,
         "bridged": True, "skillsLinked": True, "instructionsLinked": True,
         "configLinked": True, "secondaryCleared": True},
        {"id": "claude", "label": "Claude Code", "installed": True, "supported": True,
         "bridged": False, "skillsLinked": False, "instructionsLinked": True,
         "configLinked": True, "secondaryCleared": True},
    ]))
elif len(args) == 2 and args[0] == "--preset":
    preset_id = args[1]
    known = {"stealth", "rust-dev", "web-fullstack", "full-power"}
    if preset_id not in known:
        print(f"unknown preset: {preset_id}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"preset": preset_id, "applied": True, "changed": [], "errors": []}))
elif args == ["--bridge-deploy"]:
    print(json.dumps({"deployed": True, "harnesses": ["codex", "claude"], "errors": []}))
else:
    print(f"unsupported arguments: {args}", file=sys.stderr)
    sys.exit(2)
'''


def _write_skill(library: Path, name: str, content: str) -> None:
    directory = library / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(content, encoding="utf-8")


@pytest.fixture()
def mock_home(monkeypatch: pytest.MonkeyPatch) -> Path:
    """A complete OrquestraAI layout plus a fake binary, removed after the test."""
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    home = SCRATCH_ROOT / uuid.uuid4().hex
    home.mkdir()

    library = home / "skills-library"
    for name, content in (("alpha", ALPHA), ("beta", BETA), ("gamma", GAMMA)):
        _write_skill(library, name, content)

    for scope in ("global", "codex", "claude"):
        (home / "active" / scope).mkdir(parents=True)

    catalog = {
        "mcps": {
            "alpha-mcp": {
                "id": "alpha-mcp",
                "name": "Alpha MCP",
                "description": "First fixture server.",
                "command": "alpha",
                "args": [],
                "env": {},
                "globalEnabled": True,
                "enabledHarnesses": [],
            },
            "beta-mcp": {
                "id": "beta-mcp",
                "name": "Beta MCP",
                "description": "Second fixture server.",
                "command": "beta",
                "args": ["--stdio"],
                "env": {},
                "globalEnabled": False,
                "enabledHarnesses": ["codex"],
            },
        },
        "managedIds": ["alpha-mcp", "beta-mcp"],
    }
    (home / "mcps.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    (home / "AGENTS.md").write_text(
        "# Global Agent Instructions\n\n"
        "## Persona\n- Address the operator as senhor.\n\n"
        "## Workflow\n- Inspect before editing.\n\n"
        "## Tail\n- Keep patches small.\n",
        encoding="utf-8",
    )

    binary = home / "orquestra"
    binary.write_text(FAKE_BINARY, encoding="utf-8")
    binary.chmod(0o755)

    monkeypatch.setenv(paths.ENV_HOME, str(home))
    monkeypatch.setenv(paths.ENV_BIN, str(binary))
    skills.clear_cache()

    try:
        yield home
    finally:
        skills.clear_cache()
        shutil.rmtree(home, ignore_errors=True)
