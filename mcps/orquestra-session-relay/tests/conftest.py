"""Shared fixtures: a temporary relay home."""

from __future__ import annotations

import pytest

from session_relay.paths import HOME_ENV


@pytest.fixture
def relay_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv(HOME_ENV, str(home))
    return home
