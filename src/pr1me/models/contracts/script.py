"""Script stage contract (prompt 02)."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from pr1me.models.common import ScriptBlock
from pr1me.models.contracts.base import StageInput, StageOutput


class ScriptInput(StageInput):
    """Input for the script generator stage (the approved topic).

    The runner feeds the flattened outputs of the upstream stages; only the
    topic (and optional factual context) are consumed here.
    """

    model_config = ConfigDict(extra="ignore")

    topic: str = Field(..., min_length=1, max_length=60)
    factual_context: str | None = Field(default=None)


class ScriptOutput(ScriptBlock, StageOutput):
    """Generated script. Mirrors prompt 02's output schema.

    ``word_count`` is the total across the four blocks and must be <= 120.
    """

    word_count: int = Field(..., ge=1, le=120)