"""Filesystem layout and native binary discovery for the OrquestraAI control plane."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ENV_HOME = "ORQUESTRA_HOME"
ENV_BIN = "ORQUESTRA_BIN"
GLOBAL_SCOPE = "global"
DEFAULT_BIN = Path.home() / ".local" / "bin" / "orquestra"


def home() -> Path:
    """Root of the OrquestraAI state tree (`~/.orquestra` unless overridden)."""
    override = os.environ.get(ENV_HOME, "").strip()
    return Path(override).expanduser() if override else Path.home() / ".orquestra"


def skills_library() -> Path:
    """Master vault that holds one directory per skill."""
    return home() / "skills-library"


def active_root() -> Path:
    """Directory holding one projection per scope, including `global`."""
    return home() / "active"


def harness_ids() -> list[str]:
    """Every harness scope OrquestraAI has projected, in alphabetical order."""
    root = active_root()
    try:
        names = [entry.name for entry in root.iterdir() if entry.is_dir()]
    except FileNotFoundError:
        return []
    return sorted(name for name in names if name != GLOBAL_SCOPE)


def active_scope(scope: str) -> Path:
    """Resolve a scope name to its projection directory, validating it first."""
    name = (scope or GLOBAL_SCOPE).strip()
    if name == GLOBAL_SCOPE:
        return active_root() / GLOBAL_SCOPE
    if name not in harness_ids():
        allowed = ", ".join([GLOBAL_SCOPE, *harness_ids()])
        raise ValueError(f"unknown scope '{name}'; expected one of: {allowed}")
    return active_root() / name


def catalog_path() -> Path:
    """The MCP catalog compiled into every harness config."""
    return home() / "mcps.json"


def instructions_path() -> Path:
    """The master `AGENTS.md` symlinked into each harness."""
    return home() / "AGENTS.md"


def backups_dir() -> Path:
    """Where pre-change copies of catalog and instruction files are kept."""
    return home() / "backups"


def binary() -> str:
    """Path to the native `orquestra` binary, preferring `ORQUESTRA_BIN`."""
    override = os.environ.get(ENV_BIN, "").strip()
    if override:
        return override
    found = shutil.which("orquestra")
    if found:
        return found
    if DEFAULT_BIN.is_file():
        return str(DEFAULT_BIN)
    return "orquestra"


def presets_path() -> Path:
    """Custom operator presets JSON (`~/.orquestra/presets.json`)."""
    return home() / "presets.json"
