"""Search shaping, hard constraints and honest error mapping, with no network."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
from typing import Any

import pytest
from requests import ConnectionError as RequestsConnectionError

from web_search import env_file, exa_search


class FakeExa:
    """Stand-in for ``Exa`` that records the options the feature sends."""

    def __init__(self, results: list[Any] | None = None, error: Exception | None = None) -> None:
        self.results = results or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def search(self, query: str, **options: Any) -> SimpleNamespace:
        self.calls.append({"query": query, **options})
        if self.error is not None:
            raise self.error
        return SimpleNamespace(results=self.results)


def row(**overrides: Any) -> SimpleNamespace:
    base = {
        "title": "Exa highlights",
        "url": "https://exa.ai/docs/highlights",
        "published_date": "2026-09-30",
        "author": "Exa",
        "highlights": ["Highlights quote the passages that answer the query."],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_missing_key_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(exa_search.ENV_VAR, raising=False)
    # The override is authoritative, so pointing it at an absent file keeps the
    # developer's real repository .env out of this test.
    monkeypatch.setenv(env_file.ENV_OVERRIDE, str(tmp_path / "absent.env"))
    with pytest.raises(exa_search.SearchError) as caught:
        exa_search.run_search("exa highlights")
    assert exa_search.ENV_VAR in str(caught.value)
    assert caught.value.status is None


def test_key_comes_from_a_local_env_file_without_an_export(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key_file = tmp_path / "operator.env"
    key_file.write_text(f"{exa_search.ENV_VAR}=file-key-not-real\n", encoding="utf-8")
    monkeypatch.delenv(exa_search.ENV_VAR, raising=False)
    monkeypatch.setenv(env_file.ENV_OVERRIDE, str(key_file))

    built = exa_search.client()
    assert built.headers["x-api-key"] == "file-key-not-real"  # type: ignore[attr-defined]


def test_search_asks_for_auto_type_and_highlights() -> None:
    fake = FakeExa(results=[row()])
    report = exa_search.run_search("exa highlights", searcher=fake)
    assert fake.calls == [
        {
            "query": "exa highlights",
            "type": "auto",
            "num_results": exa_search.DEFAULT_NUM_RESULTS,
            "contents": {"highlights": True},
        }
    ]
    assert report["count"] == 1
    assert report["results"][0] == {
        "title": "Exa highlights",
        "url": "https://exa.ai/docs/highlights",
        "published_date": "2026-09-30",
        "author": "Exa",
        "highlights": ["Highlights quote the passages that answer the query."],
    }


def test_hard_constraints_pass_through_and_untitled_rows_fall_back_to_url() -> None:
    fake = FakeExa(results=[row(title=None, highlights=None, author=None)])
    report = exa_search.run_search(
        "  agent memory  ",
        num_results=7,
        include_domains=["exa.ai"],
        start_published_date="2026-01-01",
        searcher=fake,
    )
    call = fake.calls[0]
    assert call["query"] == "agent memory"
    assert call["num_results"] == 7
    assert call["include_domains"] == ["exa.ai"]
    assert call["start_published_date"] == "2026-01-01"
    assert report["results"][0]["title"] == "https://exa.ai/docs/highlights"
    assert report["results"][0]["highlights"] == []


def test_empty_results_are_reported_honestly() -> None:
    report = exa_search.run_search("nothing matches this", searcher=FakeExa(results=[]))
    assert report["count"] == 0
    assert report["results"] == []
    assert report["note"] == "Exa returned no results for this query."


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "invalid or revoked"),
        (402, "credits are exhausted"),
        (429, "rate limit"),
    ],
)
def test_http_statuses_become_readable_errors(status: int, expected: str) -> None:
    error = ValueError(f"Request failed with status code {status}: {{'error': 'x'}}")
    with pytest.raises(exa_search.SearchError) as caught:
        exa_search.run_search("exa highlights", searcher=FakeExa(error=error))
    assert caught.value.status == status
    assert expected in str(caught.value)
    assert str(status) in str(caught.value)


def test_unknown_status_still_names_it() -> None:
    error = ValueError("Request failed with status code 503: upstream unavailable")
    with pytest.raises(exa_search.SearchError) as caught:
        exa_search.run_search("exa highlights", searcher=FakeExa(error=error))
    assert caught.value.status == 503
    assert "503" in str(caught.value)


def test_network_failure_is_not_an_empty_result() -> None:
    with pytest.raises(exa_search.SearchError) as caught:
        exa_search.run_search(
            "exa highlights", searcher=FakeExa(error=RequestsConnectionError("dns down"))
        )
    assert "Could not reach Exa" in str(caught.value)
    assert caught.value.status is None


@pytest.mark.parametrize(("query", "num_results"), [("   ", 5), ("exa", 0), ("exa", 101)])
def test_bad_arguments_fail_before_any_request(query: str, num_results: int) -> None:
    fake = FakeExa(results=[row()])
    with pytest.raises(exa_search.SearchError):
        exa_search.run_search(query, num_results=num_results, searcher=fake)
    assert fake.calls == []


def test_markdown_render_keeps_the_source_link() -> None:
    report = exa_search.run_search("exa highlights", searcher=FakeExa(results=[row()]))
    text = exa_search.render_markdown(report)
    assert "[Exa highlights](https://exa.ai/docs/highlights)" in text
    assert "Highlights quote the passages that answer the query." in text


def test_client_reads_the_environment_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(exa_search.ENV_VAR, "test-key-not-real")
    built = exa_search.client()
    assert built.headers["x-api-key"] == "test-key-not-real"  # type: ignore[attr-defined]
