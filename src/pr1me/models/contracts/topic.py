"""Topic stage contract (prompt 01)."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from pr1me.models.contracts.base import StageInput, StageOutput


class TopicInput(StageInput):
    """Input for the topic generator stage.

    Matches prompt 01's input contract: existing topics, a channel directive,
    and an optional category focus.
    """

    existing_topics: list[str] = Field(default_factory=list, max_length=200)
    directive: str = Field(..., min_length=1, description="Channel directive.")
    category_focus: str | None = Field(
        default=None, description="Optional category focus to restrict generation."
    )


class TopicOutput(StageOutput):
    """Single approved topic. Mirrors ``{"topic": string}`` from prompt 01."""

    topic: Annotated[str, Field(min_length=1, max_length=60)]