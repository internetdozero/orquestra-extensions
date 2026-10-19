"""Shared fixtures: a throwaway SQLite vault per test."""

from __future__ import annotations

import pytest

from idea_vault.store import ENV_DB_PATH, connect, reset_databases


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "vault" / "ideas.sqlite3")
    yield connection
    connection.close()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "data" / "ideas.sqlite3"
    monkeypatch.setenv(ENV_DB_PATH, str(path))
    reset_databases()
    yield path
    reset_databases()
