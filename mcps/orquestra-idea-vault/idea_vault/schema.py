"""Closed vocabularies published to MCP clients as JSON schema enums.

A free-form ``str`` parameter makes the model guess the accepted values and
pay a round trip for each wrong guess. Declaring ``Literal`` here puts the
options in the tool schema the client already reads.

The literals mirror ``store.CATEGORIES``/``PRIORITIES``/``STATUSES``;
``tests/test_schema.py`` fails if the two ever drift apart.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["feature", "architecture", "bug", "ux", "idea"]
Priority = Literal["low", "medium", "high", "critical"]
Status = Literal["open", "in_progress", "completed", "archived"]
# Listing accepts the stored statuses plus "all" for an unfiltered scan.
StatusFilter = Literal["open", "in_progress", "completed", "archived", "all"]


class IdeaInput(BaseModel):
    """One idea inside a batch insert, validated before anything is written."""

    title: str = Field(description="Short imperative title, e.g. 'Cache vault reads'.")
    description: str = Field("", description="What the idea covers and why.")
    category: Category = "feature"
    priority: Priority = "medium"
    tags: list[str] | None = None
    status: Status = "open"
    prompt: str | None = Field(
        None, description="Builder prompt: the instruction handed to the implementer."
    )
