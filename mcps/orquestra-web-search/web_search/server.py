"""MCP entrypoint: one Exa web search exposed as a tool, plus a one-shot CLI query."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

from . import exa_search

INSTRUCTIONS = """Web search for agents, backed by Exa.

web_search takes a query and returns up to num_results pages (1-100, default 5),
each with title, url, published_date, author and query-relevant highlights.
Highlights are the recommended content option: they quote the passages that
answer the query instead of the whole page body.

include_domains and start_published_date are hard constraints — pass them only
when a domain or a date floor is genuinely required. Search has no pagination,
so widen num_results rather than asking for a next page.

The tool reads EXA_API_KEY from the server's environment, then from a local
.env next to the installed package or above the working directory
(WEB_SEARCH_ENV_FILE overrides that lookup). A missing key, a rejected key
(401), exhausted credits (402) and rate limiting (429) come back as an
{"error": ...} object with the HTTP status in error_status, never as an empty
result list.
"""

server = MCPServer(
    name="web-search",
    title="Web Search (Exa)",
    version="0.1.0",
    instructions=INSTRUCTIONS,
)

FALLBACK_ERROR_STATUS = "See the message for details."


@server.tool(
    description=(
        "Search the web with Exa. Returns title, url, published_date, author and "
        "highlights per result. num_results is 1-100 (default 5); include_domains "
        "and start_published_date are optional hard constraints. Failures return "
        "an error object instead of an empty list."
    )
)
def web_search(
    query: str,
    num_results: int = exa_search.DEFAULT_NUM_RESULTS,
    include_domains: list[str] | None = None,
    start_published_date: str | None = None,
) -> dict[str, Any]:
    """Query in, cited results out."""
    try:
        return exa_search.run_search(
            query,
            num_results=num_results,
            include_domains=include_domains,
            start_published_date=start_published_date,
        )
    except exa_search.SearchError as error:
        return {
            "error": str(error),
            "error_status": error.status or FALLBACK_ERROR_STATUS,
        }


def main(argv: list[str] | None = None) -> int:
    """Serve MCP over the chosen transport, or run one search with --query."""
    parser = argparse.ArgumentParser(prog="web-search", description=__doc__)
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "sse", "streamable-http"),
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--query",
        help="Run one search for this query, print the results and exit.",
    )
    parser.add_argument(
        "--num-results",
        type=int,
        default=exa_search.DEFAULT_NUM_RESULTS,
        help=f"Results for --query (1-{exa_search.MAX_NUM_RESULTS}, default 5).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the --query result as JSON instead of readable text.",
    )
    args = parser.parse_args(argv)

    if args.query:
        try:
            report = exa_search.run_search(args.query, num_results=args.num_results)
        except exa_search.SearchError as error:
            print(f"web-search: {error}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(exa_search.render_markdown(report))
        return 0

    print(f"web-search: serving over {args.transport}", file=sys.stderr)
    server.run(args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
