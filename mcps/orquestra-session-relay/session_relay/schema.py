"""Closed vocabularies published to MCP clients as JSON schema enums.

Harness ids were an undocumented ``str``: an agent had to call the tool, read
"unknown harness", and try again. Declaring ``Literal`` puts the accepted ids
in the schema the client already reads.

Canonical ids come from the adapter registry and the accepted aliases from
``adapters.ALIASES``; ``tests/test_schema.py`` fails if the two drift apart.
"""

from __future__ import annotations

from typing import Literal

Harness = Literal[
    "antigravity",
    "claude",
    "codex",
    "copilot",
    "freebuff",
    "grok",
    "hermes",
    "kilo",
    "opencode",
    "claude-code",
    "gemini",
    "manicode",
    "open-code",
    "xai",
]
