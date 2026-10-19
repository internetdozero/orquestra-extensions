"""Condense the native bridge report into a fleet-level answer."""

from __future__ import annotations

from typing import Any

from . import bridge

# Fields the control plane cares about; the native report carries more.
FIELDS = (
    "id",
    "label",
    "installed",
    "supported",
    "bridged",
    "skillsLinked",
    "instructionsLinked",
    "configLinked",
    "secondaryCleared",
)


def fleet_status() -> dict[str, Any]:
    """Return every harness with its link state plus fleet-wide counters."""
    report = bridge.bridge_status()
    harnesses = [{key: item.get(key) for key in FIELDS} for item in report]
    bridged = [item["id"] for item in harnesses if item.get("bridged")]
    installed = [item["id"] for item in harnesses if item.get("installed")]
    return {
        "count": len(harnesses),
        "installed": len(installed),
        "bridged": len(bridged),
        "unbridged": [item["id"] for item in harnesses if not item.get("bridged")],
        "harnesses": harnesses,
    }


def deploy_bridge() -> dict[str, Any]:
    """Back up and symlink every installed harness into the fleet projection."""
    return bridge.deploy_bridge()
