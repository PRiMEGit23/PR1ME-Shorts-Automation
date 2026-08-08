"""Stage contract markers.

Every stage receives exactly one input model and returns exactly one output
model. Both must be JSON-serializable. The pipeline keeps no shared mutable
state aside from these documented contracts.
"""

from __future__ import annotations

from typing import TypeVar

from pr1me.models.common import StableModel

InputT = TypeVar("InputT", bound=StableModel)
OutputT = TypeVar("OutputT", bound=StableModel)


class StageInput(StableModel):
    """Marker for a stage input contract."""


class StageOutput(StableModel):
    """Marker for a stage output contract."""


class ValidationOutput(StageOutput):
    """Generic validated output envelope used by deterministic audit stages."""

    validation: object | None = None