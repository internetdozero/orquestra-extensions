"""Local wrangler CLI fallback: config discovery, parsing and execution.

Used when no API token is configured, or when a project's ``wrangler.toml`` /
``wrangler.jsonc`` already binds the resource being addressed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

WRANGLER_CONFIG_NAMES = ("wrangler.toml", "wrangler.jsonc", "wrangler.json")


class WranglerError(RuntimeError):
    """Raised when the local wrangler fallback cannot run."""


def find_wrangler_config(start: Path | None = None) -> Path | None:
    """Locate a wrangler config in the working directory (not its parents)."""
    base = start or Path.cwd()
    for name in WRANGLER_CONFIG_NAMES:
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None


def read_wrangler_config(path: Path) -> dict[str, Any]:
    """Parse wrangler.toml (minimal), .jsonc or .json into a dict."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json" or text.lstrip().startswith("{"):
        cleaned = _strip_json_comments(text) if path.suffix == ".jsonc" else text
        return json.loads(cleaned)
    return _parse_toml(text)


def _strip_json_comments(text: str) -> str:
    """Remove ``//`` and ``/* */`` comments, ignoring them inside strings.

    A line-based split on ``//`` would truncate any value holding a URL
    (``"https://example.com"``), so the scan tracks string and block-comment
    state character by character instead.
    """
    output: list[str] = []
    in_string = False
    escaped = False
    in_block = False
    index = 0
    while index < len(text):
        char = text[index]
        pair = text[index : index + 2]

        if in_block:
            if pair == "*/":
                in_block = False
                index += 2
            else:
                output.append("\n" if char == "\n" else " ")
                index += 1
            continue

        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue

        if pair == "//":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        if pair == "/*":
            in_block = True
            index += 2
            continue

        output.append(char)
        index += 1

    return "".join(output)


def _parse_toml(text: str) -> dict[str, Any]:
    """Minimal TOML subset parser for wrangler configs (tables, str/int/bool/array)."""
    data: dict[str, Any] = {}
    current: dict[str, Any] = data
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("[["):
            continue
        if line.startswith("[") and line.endswith("]"):
            header = line[1:-1].strip().strip('"')
            section: dict[str, Any] = {}
            data[header] = section
            current = section
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().strip('"')
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            current[key] = [
                item.strip().strip('"') for item in inner.split(",") if item.strip()
            ]
        elif value.startswith('"') or value.startswith("'"):
            current[key] = value[1:-1]
        elif value.lower() in {"true", "false"}:
            current[key] = value.lower() == "true"
        else:
            try:
                current[key] = int(value)
            except ValueError:
                current[key] = value
    return data


def wrangler_binary() -> str | None:
    found = shutil.which("wrangler")
    if found:
        return found
    local_cwd = Path.cwd() / "node_modules" / ".bin" / "wrangler"
    if local_cwd.is_file() and os.access(local_cwd, os.X_OK):
        return str(local_cwd)
    sintonia_node = Path.home() / "Persistente" / "Coding" / "sites" / "sintonia" / "node_modules" / ".bin" / "wrangler"
    if sintonia_node.is_file() and os.access(sintonia_node, os.X_OK):
        return str(sintonia_node)
    return shutil.which("npx")


def run_wrangler(args: Iterable[str], *, cwd: Path | None = None,
                 timeout: float = 60.0) -> str:
    """Run the local wrangler CLI and return combined stdout/stderr text."""
    binary = wrangler_binary()
    if not binary:
        raise WranglerError(
            "wrangler CLI not found on PATH. Install it (npm i -g wrangler) or set "
            "CLOUDFLARE_API_TOKEN so the REST API path can be used."
        )
    command = [binary, "wrangler", *args] if binary.endswith("npx") else [binary, *args]
    try:
        completed = subprocess.run(
            command, cwd=str(cwd) if cwd else None, timeout=timeout,
            capture_output=True, text=True, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise WranglerError(f"wrangler timed out after {timeout}s: {' '.join(command)}") from exc
    if completed.returncode != 0:
        output = (completed.stderr or completed.stdout or "").strip()
        raise WranglerError(f"{' '.join(command)} failed ({completed.returncode}): {output[:500]}")
    return completed.stdout