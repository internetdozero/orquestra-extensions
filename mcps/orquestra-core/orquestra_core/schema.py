"""Closed vocabularies published to MCP clients as JSON schema enums.

Scope names cannot live here: they are whatever `~/.orquestra/active` holds on
this machine, so `paths.active_scope` validates them and its message lists the
valid ones. HTTP methods are fixed by the protocol, so they belong in the
schema and never reach the vault as a typo.
"""

from __future__ import annotations

from typing import Literal

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
