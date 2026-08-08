"""Motion Graphics stage contract (pipeline step between Audio Mix and Assembly).

The stage consumes the approved visual plan and the narration blocks, derives a
small deterministic set of on-screen overlays (captions and callouts), and
returns a single :class:`MotionGraphicsOutput` describing the overlay layer.

Because the pipeline runner flattens every upstream output into one dict, only
the uniquely-named columns survive intact. :class:`MotionGraphicsInput` carries
the four narration blocks and the plan's shot list; every other upstream field
is ignored.

These models are plain data: no transport, no video knowledge, no rendering.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from pr1me.models.common import StableModel, ValidationDescriptor
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.contracts.visual import ScriptBlockName, VisualShot


class MotionOverlayStyle(StableModel):
    """Typography tokens applied to one on-screen overlay."""

    font: str = Field(..., min_length=1)
    size_px: int = Field(..., ge=1)
    color: str = Field(..., min_length=1)
    accent: str = Field(..., min_length=1)


class MotionOverlay(StableModel):
    """One caption/callout overlay referenced from the output."""

    id: int
    text: str = Field(..., min_length=1)
    start_second: float = Field(..., ge=0.0)
    end_second: float = Field(..., ge=0.0)
    duration_seconds: float = Field(..., ge=1.5, le=4.0)
    pos_x: float = Field(..., ge=0.0)
    pos_y: float = Field(..., ge=0.0)
    style: MotionOverlayStyle


class MotionStyleUsed(StableModel):
    """The exact styling that was applied to the overlay set."""

    font: str = Field(..., min_length=1)
    size_px: int = Field(..., ge=1)
    color: str = Field(..., min_length=1)
    safe_margin_px: int = Field(..., ge=0)


class MotionGraphicsOutput(StageOutput):
    """The machine-readable overlay instruction set for one Short."""

    overlays: list[MotionOverlay] = Field(default_factory=list)
    style_used: MotionStyleUsed
    total_overlays: int = Field(default=0, ge=0, le=5)
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)


class MotionGraphicsInput(StageInput):
    """Input for the motion graphics stage.

    ``hook``/``explanation``/``practical_insight``/``ending`` carry the approved
    narration text and ``shots`` the timed visual plan the overlays align to.
    ``extra`` is ignored because the pipeline runner feeds the flattened outputs
    of every upstream stage alongside these.
    """

    model_config = ConfigDict(extra="ignore")

    hook: str
    explanation: str
    practical_insight: str
    ending: str
    shots: list[VisualShot] = Field(default_factory=list)

    def narration_for(self, block: ScriptBlockName) -> str:
        """Return the approved narration text for one script block."""
        return getattr(self, block)