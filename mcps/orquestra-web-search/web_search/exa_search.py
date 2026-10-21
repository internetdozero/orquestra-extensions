"""Server-side Exa search: one query in, titled results with cited highlights out.

The Exa client reads ``EXA_API_KEY`` from the process environment, falling back
to a local ``.env`` located by :mod:`web_search.env_file` so an MCP client that
passes no env block still works. This module is imported only by the MCP server
and its CLI, never by a browser bundle or a template, so the key stays
operator-side.
"""

from __future__ import annotations

import os
import re
from typing import Any, Protocol

from exa_py import Exa
from requests import RequestException

from . import env_file

ENV_VAR = "EXA_API_KEY"
DEFAULT_NUM_RESULTS = 5
MAX_NUM_RESULTS = 100

# Exa answers these statuses for the failures the caller can act on.
STATUS_HINTS = {
    401: f"{ENV_VAR} was rejected by Exa (401): the key is invalid or revoked.",
    402: "Exa credits are exhausted (402): top up the billing page of the account.",
    429: "Exa rate limit reached (429): retry once the window resets.",
}

_STATUS_CODE = re.compile(r"status code (\d{3})")


class SearchError(RuntimeError):
    """A search failure the feature can show instead of a silent empty result."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class Searcher(Protocol):
    """The slice of ``Exa`` this feature uses, so tests can stand in for it."""

    def search(self, query: str, **options: Any) -> Any: ...


def api_key() -> str:
    """Return the Exa key from the environment or a local ``.env``, or fail."""
    key = os.environ.get(ENV_VAR, "").strip()
    if not key:
        env_file.load((ENV_VAR,))
        key = os.environ.get(ENV_VAR, "").strip()
    if not key:
        raise SearchError(
            f"{ENV_VAR} is not set. Put it in the MCP server's env block, in "
            f"the repository .env (copy .env.example), or in the file named "
            f"by {env_file.ENV_OVERRIDE}; exporting it in the shell also works."
        )
    return key


def client(searcher: Searcher | None = None) -> Searcher:
    """Build an Exa client from the environment, or return an injected stand-in."""
    if searcher is not None:
        return searcher
    return Exa(api_key())


def _status_of(error: Exception) -> int | None:
    """Recover the HTTP status Exa reported; exa-py raises ValueError with it inline."""
    match = _STATUS_CODE.search(str(error))
    return int(match.group(1)) if match else None


def _as_search_error(error: Exception) -> SearchError:
    if isinstance(error, SearchError):
        return error
    if isinstance(error, RequestException):
        return SearchError(f"Could not reach Exa: {error}")
    status = _status_of(error)
    if status is not None:
        hint = STATUS_HINTS.get(status, f"Exa returned status {status}.")
        return SearchError(hint, status)
    return SearchError(f"Exa search failed: {error}")


def _result(row: Any) -> dict[str, Any]:
    """Keep only what the feature shows, and fall back to the URL when untitled."""
    url = row.url
    return {
        "title": row.title or url,
        "url": url,
        "published_date": row.published_date,
        "author": row.author,
        "highlights": [passage for passage in (row.highlights or []) if passage],
    }


def run_search(
    query: str,
    num_results: int = DEFAULT_NUM_RESULTS,
    include_domains: list[str] | None = None,
    start_published_date: str | None = None,
    searcher: Searcher | None = None,
) -> dict[str, Any]:
    """Search the web for ``query`` and return titled results with highlights.

    ``include_domains`` and ``start_published_date`` are hard constraints only;
    leave them unset for an ordinary search.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise SearchError("query must be a non-empty string")
    if num_results < 1:
        raise SearchError("num_results must be at least 1")
    if num_results > MAX_NUM_RESULTS:
        raise SearchError(f"num_results must be at most {MAX_NUM_RESULTS}")

    options: dict[str, Any] = {
        "type": "auto",
        "num_results": num_results,
        "contents": {"highlights": True},
    }
    if include_domains:
        options["include_domains"] = include_domains
    if start_published_date:
        options["start_published_date"] = start_published_date

    try:
        response = client(searcher).search(cleaned, **options)
    except Exception as error:  # every Exa failure becomes one readable state
        raise _as_search_error(error) from error

    results = [_result(row) for row in (response.results or [])]
    report: dict[str, Any] = {
        "query": cleaned,
        "count": len(results),
        "results": results,
    }
    if not results:
        report["note"] = "Exa returned no results for this query."
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """Render a report as text with each result's source link, for the CLI and handoffs."""
    lines = [f"Exa search: {report['query']} — {report['count']} result(s)"]
    if not report["results"]:
        lines.append(report.get("note", "No results."))
        return "\n".join(lines)
    for index, result in enumerate(report["results"], start=1):
        meta = " · ".join(
            part
            for part in (result.get("author"), result.get("published_date"))
            if part
        )
        heading = f"{index}. [{result['title']}]({result['url']})"
        lines.append(f"{heading} — {meta}" if meta else heading)
        for passage in result.get("highlights") or []:
            lines.append(f"   - {passage}")
    return "\n".join(lines)
