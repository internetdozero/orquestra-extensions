"""Closed vocabularies published to MCP clients as JSON schema enums.

A free-form ``str`` parameter makes the model guess the accepted values and
pay a round trip for each wrong guess. Declaring ``Literal`` here puts the
options in the tool schema the client already reads.

The literals mirror ``store.CATEGORIES``/``PRIORITIES``/``STATUSES``;
``tests/test_schema.py`` fails if the two ever drift apart.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Category = Literal["feature", "architecture", "bug", "ux", "idea"]
Priority = Literal["low", "medium", "high", "critical"]
Status = Literal["open", "in_progress", "completed", "archived"]
# Listing accepts the stored statuses plus "all" for an unfiltered scan.
StatusFilter = Literal["open", "in_progress", "completed", "archived", "all"]

# One dispatch contract shared by every tool that accepts a Builder prompt, so
# the guidance reaches the client schema instead of living only in a skill file.
BuilderDispatch = Annotated[
    str | None,
    Field(
        description=(
            "Compact English Builder dispatch prompt (Mission, Workspace, Targets, "
            "Scope, Idea Vault Lifecycle hooks, Verification). Avoid redundant "
            "guardrails."
        )
    ),
]


class IdeaInput(BaseModel):
    """One idea inside a batch insert, validated before anything is written."""

    title: str = Field(description="Short imperative title, e.g. 'Cache vault reads'.")
    description: str = Field("", description="What the idea covers and why.")
    category: Category = "feature"
    priority: Priority = "medium"
    tags: list[str] | None = None
    status: Status = "open"
    prompt: BuilderDispatch = None
