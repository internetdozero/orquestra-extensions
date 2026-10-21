"""Locating and reading the operator's .env: precedence, scope and no leakage."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from web_search import env_file


def test_parse_handles_export_quotes_comments_and_crlf() -> None:
    text = (
        "# operator secrets\r\n"
        "\r\n"
        "export EXA_API_KEY='quoted-key'\r\n"
        'OTHER="also-quoted"\r\n'
        "TRAILING=value  # inline comment\r\n"
        "NO_EQUALS\r\n"
        "=orphan\r\n"
    )
    assert env_file.parse(text) == {
        "EXA_API_KEY": "quoted-key",
        "OTHER": "also-quoted",
        "TRAILING": "value",
    }


def test_explicit_override_is_the_only_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "operator.env"
    monkeypatch.setenv(env_file.ENV_OVERRIDE, str(target))
    assert env_file.candidates() == [target]


def test_load_reads_only_the_requested_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key_file = tmp_path / "app.env"
    key_file.write_text("EXA_API_KEY=from-file\nOTHER_SECRET=keep-out\n", encoding="utf-8")
    monkeypatch.setenv(env_file.ENV_OVERRIDE, str(key_file))
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("OTHER_SECRET", raising=False)

    assert env_file.load(("EXA_API_KEY",)) == key_file
    assert os.environ["EXA_API_KEY"] == "from-file"
    assert "OTHER_SECRET" not in os.environ


def test_existing_environment_value_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key_file = tmp_path / "app.env"
    key_file.write_text("EXA_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setattr(env_file, "candidates", lambda: [key_file])
    monkeypatch.setenv("EXA_API_KEY", "from-shell")

    assert env_file.load(("EXA_API_KEY",)) is None
    assert os.environ["EXA_API_KEY"] == "from-shell"


def test_missing_file_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(env_file, "candidates", lambda: [tmp_path / "absent.env"])
    assert env_file.load(("EXA_API_KEY",)) is None


def test_package_location_wins_over_the_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    package = repo / "mcps" / "pkg" / "web_search"
    package.mkdir(parents=True)
    (repo / ".env").write_text("EXA_API_KEY=package-side\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".env").write_text("EXA_API_KEY=cwd-side\n", encoding="utf-8")

    monkeypatch.setattr(env_file, "__file__", str(package / "env_file.py"))
    monkeypatch.delenv(env_file.ENV_OVERRIDE, raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.chdir(elsewhere)

    assert env_file.load(("EXA_API_KEY",)) == repo / ".env"
    assert os.environ["EXA_API_KEY"] == "package-side"


def test_candidates_walk_up_from_the_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("EXA_API_KEY=nested\n", encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.delenv(env_file.ENV_OVERRIDE, raising=False)
    monkeypatch.chdir(nested)

    paths = env_file.candidates()
    assert tmp_path / ".env" in paths
    # The nearest file ends the walk, so nothing above it is offered.
    assert paths[-1] == tmp_path / ".env"
