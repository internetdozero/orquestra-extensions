"""Closed vocabularies published to MCP clients as JSON schema enums.

A free-form ``str`` target makes the model guess which sweeps and caches exist
and pay a round trip for each wrong guess. Declaring ``Literal`` puts the
options in the tool schema the client already reads.

The literals mirror ``sweep.TARGET_TYPES`` and ``caches.DEFAULT_TARGETS``;
``tests/test_schema.py`` fails if the two ever drift apart.
"""

from __future__ import annotations

from typing import Literal

SweepTarget = Literal["orphans", "browsers", "compilers"]
CacheTarget = Literal["sockets", "staging", "testing_scratch"]
