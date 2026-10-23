"""MCP entrypoint: registers the idea-vault tools and runs the transport."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from . import blackboard, ideas
from .errors import actionable
from .schema import (
    BuilderDispatch,
    Category,
    IdeaInput,
    Priority,
    Status,
    StatusFilter,
)
from .store import ENV_DB_PATH, configure, get_database

INSTRUCTIONS = """Local idea vault and inter-agent blackboard backed by one SQLite file.

Use the idea tools to capture thoughts without leaving the terminal, and the
board tools to leave asynchronous notes for other agents working concurrently:
post with post_board_note, then read_board_notes with unread_only to pick up
what is waiting for you. Call read_board_notes(mark_as_read=True) once handled.

category, priority and status are closed sets, and their accepted values are
published in each tool's schema. A rejected value returns the error text with
the accepted options, so read it instead of retrying with a guess.
"""

server = MCPServer(
    name="idea-vault",
    title="Idea Vault",
    version="0.1.0",
    instructions=INSTRUCTIONS,
)


def tool(*, description: str) -> Callable[[Callable[..., Any]], Any]:
    """Register a tool whose anticipated failures reach the caller verbatim."""
    return lambda fn: server.tool(description=description)(actionable(fn))


@tool(
    description="Capture a new idea in the local vault. Returns the stored idea with its id."
)
def record_idea(
    project: str,
    title: str,
    description: str = "",
    category: Category = "feature",
    priority: Priority = "medium",
    tags: list[str] | None = None,
    prompt: BuilderDispatch = None,
) -> dict[str, Any]:
    """Record an idea. category: feature|architecture|bug|ux|idea, priority: low|medium|high|critical.

    prompt carries the compact English Builder dispatch, not a restatement of rules
    already enforced by AGENTS.md.
    """
    with get_database() as conn:
        return ideas.record_idea(
            conn, project, title, description, category, priority, tags,
            status="open", prompt=prompt,
        )


@tool(
    description="Bulk insert multiple ideas for a project in a single transaction."
)
def record_ideas_batch(
    project: str,
    items: list[IdeaInput],
) -> dict[str, Any]:
    """Record multiple ideas atomically. Each item can include title, description, category, priority, tags, status, and prompt."""
    with get_database() as conn:
        return ideas.record_ideas_batch(
            conn, project, [item.model_dump() for item in items]
        )


@tool(
    description="List ideas filtered by project, status (default open), category and priority."
)
def list_ideas(
    project: str | None = None,
    status: StatusFilter = "open",
    category: Category | None = None,
    priority: Priority | None = None,
    limit: int = 200,
    offset: int = 0,
    compact: bool = False,
) -> dict[str, Any]:
    """List ideas. status: open|in_progress|completed|archived|all."""
    with get_database() as conn:
        return ideas.list_ideas(
            conn,
            project,
            status,
            category,
            priority,
            limit=limit,
            offset=offset,
            compact=compact,
        )


@tool(
    description="Search ideas by title, description, tags or prompt (case-insensitive substring match)."
)
def search_ideas(query: str, project: str | None = None) -> dict[str, Any]:
    """Search the vault, optionally scoped to one project."""
    with get_database() as conn:
        return ideas.search_ideas(conn, query, project)


@tool(
    description="Update an existing idea's title, description, category, priority, tags, or prompt."
)
def update_idea(
    idea_id: int,
    title: str | None = None,
    description: str | None = None,
    category: Category | None = None,
    priority: Priority | None = None,
    tags: list[str] | None = None,
    prompt: BuilderDispatch = None,
) -> dict[str, Any]:
    """Update an existing idea's fields by id. None leaves every field untouched.

    prompt replaces the Builder dispatch with the same compact English contract.
    """
    with get_database() as conn:
        return ideas.update_idea(
            conn, idea_id, title, description, category, priority, tags, prompt
        )


@tool(
    description="Transition an idea to open, in_progress, completed or archived."
)
def update_idea_status(idea_id: int, status: Status) -> dict[str, Any]:
    """Update an idea's status by id."""
    with get_database() as conn:
        return ideas.update_idea_status(conn, idea_id, status)


@tool(description="Permanently delete an idea from the vault by its ID.")
def delete_idea(idea_id: int) -> dict[str, Any]:
    """Permanently delete an idea from the vault by its ID."""
    with get_database() as conn:
        return ideas.delete_idea(conn, idea_id)


@tool(
    description="Export one project's open and in-progress ideas as grouped GitHub-style markdown."
)
def export_ideas_markdown(project: str) -> dict[str, Any]:
    """Return markdown grouped by category, ready to paste into a README or issue."""
    with get_database() as conn:
        return ideas.export_ideas_markdown(conn, project)


@tool(
    description="Post an asynchronous note to the shared blackboard for other agents."
)
def post_board_note(
    project: str,
    topic: str,
    note: str,
    sender: str = "agent",
    target: str = "all",
) -> dict[str, Any]:
    """Append a collaboration note. topic: backend|frontend|contract|general or any label."""
    with get_database() as conn:
        return blackboard.post_board_note(conn, project, topic, note, sender, target)


@tool(
    description="Read blackboard notes for a project, unread only by default, optionally marking them read."
)
def read_board_notes(
    project: str,
    topic: str | None = None,
    unread_only: bool = True,
    mark_as_read: bool = False,
    target: str | None = None,
) -> dict[str, Any]:
    """Fetch collaboration notes addressed to you or to all agents."""
    with get_database() as conn:
        return blackboard.read_board_notes(
            conn, project, topic, unread_only, mark_as_read, target
        )


@tool(
    description="Delete handled blackboard notes: read notes only by default, or every note with include_unread."
)
def clear_board_notes(
    project: str,
    topic: str | None = None,
    include_unread: bool = False,
) -> dict[str, Any]:
    """Clean up resolved notes for a project, optionally scoped to one topic."""
    with get_database() as conn:
        return blackboard.clear_board_notes(conn, project, topic, include_unread)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, open the vault and serve MCP over the chosen transport."""
    parser = argparse.ArgumentParser(prog="idea-vault", description=__doc__)
    parser.add_argument(
        "--db", default=None, help=f"SQLite database path (env: {ENV_DB_PATH})"
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "sse", "streamable-http"),
        help="MCP transport (default: stdio)",
    )
    args = parser.parse_args(argv)
    path = configure(args.db)
    database = get_database()
    with database as conn:
        conn.execute("SELECT 1")
    print(f"idea-vault: serving {path}", file=sys.stderr)
    server.run(args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
