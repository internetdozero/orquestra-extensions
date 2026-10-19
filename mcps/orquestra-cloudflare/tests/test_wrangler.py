"""Local wrangler fallback: config discovery, parsing and CLI execution."""

from __future__ import annotations

import json
import subprocess

import pytest

from cloudflare_mcp import wrangler as wrangler_module
from cloudflare_mcp.wrangler import (
    WranglerError,
    _parse_toml,
    _strip_json_comments,
    find_wrangler_config,
    read_wrangler_config,
    run_wrangler,
)


def test_find_and_parse_wrangler_configs(tmp_path):
    assert find_wrangler_config(tmp_path) is None

    toml_path = tmp_path / "wrangler.toml"
    toml_path.write_text('name = "demo"\nmain = "src/index.ts"\n', encoding="utf-8")
    found = find_wrangler_config(tmp_path)
    assert found is not None and found.name == "wrangler.toml"
    assert read_wrangler_config(found) == {"name": "demo", "main": "src/index.ts"}

    jsonc_path = tmp_path / "app.jsonc"
    jsonc_path.write_text('{\n  // a note\n  "name": "demo2"\n}\n', encoding="utf-8")
    assert read_wrangler_config(jsonc_path) == {"name": "demo2"}


def test_toml_subset_parser_reads_tables_flags_and_arrays():
    parsed = _parse_toml(
        '# comment\nname = "worker"\nmain = "src/index.ts"\ncompat = true\n'
        'tags = ["a", "b"]\n[observability]\nenabled = true\n'
    )
    assert parsed == {
        "name": "worker",
        "main": "src/index.ts",
        "compat": True,
        "tags": ["a", "b"],
        "observability": {"enabled": True},
    }


def test_jsonc_stripping_keeps_urls_and_removes_comments():
    text = (
        "{\n"
        "  // drop me\n"
        '  "url": "https://example.com//path",\n'
        "  /* and me */\n"
        '  "n": 1\n'
        "}\n"
    )
    assert json.loads(_strip_json_comments(text)) == {
        "url": "https://example.com//path",
        "n": 1,
    }


def test_jsonc_stripping_handles_a_trailing_comment_without_newline():
    assert _strip_json_comments('{"a": 1} // done').strip() == '{"a": 1}'


def test_run_wrangler_reports_a_missing_binary(monkeypatch):
    monkeypatch.setattr(wrangler_module, "wrangler_binary", lambda: None)
    with pytest.raises(WranglerError) as error:
        run_wrangler(["d1", "list"])
    assert "wrangler CLI not found" in str(error.value)


def test_run_wrangler_surfaces_a_failed_command(monkeypatch):
    monkeypatch.setattr(wrangler_module, "wrangler_binary", lambda: "/usr/bin/wrangler")
    failed = subprocess.CompletedProcess(["wrangler"], 1, stdout="", stderr="boom")
    monkeypatch.setattr(wrangler_module.subprocess, "run", lambda *args, **kwargs: failed)

    with pytest.raises(WranglerError) as error:
        run_wrangler(["d1", "list"])
    assert "boom" in str(error.value)


def test_run_wrangler_returns_stdout(monkeypatch):
    monkeypatch.setattr(wrangler_module, "wrangler_binary", lambda: "/usr/bin/wrangler")
    ok = subprocess.CompletedProcess(["wrangler"], 0, stdout='{"ok": true}', stderr="")
    monkeypatch.setattr(wrangler_module.subprocess, "run", lambda *args, **kwargs: ok)

    assert run_wrangler(["d1", "list"]) == '{"ok": true}'
