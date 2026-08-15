"""Visual Director stage contract (prompt 04).

Mirrors the prompt's shot-list schema. The plan is a sequence of timed shots
that mirror the approved narration, plus channel branding flags.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from pr1me.models.common import ScriptCorrections, StableModel
from pr1me.models.contracts.base import StageInput, StageOutput

#: The four narration blocks a shot may support (PIPELINE_SPEC).
ScriptBlockName = Literal["hook", "explanation", "practical_insight", "ending"]


class VisualInput(StageInput):
    """Input for the visual director stage.

    The runner feeds the flattened outputs of the upstream stages; the board
    consumes the approved narration plus the fact-check verdict and corrections.
    """

    model_config = ConfigDict(extra="ignore")

    topic: str | None = Field(default=None, min_length=1)
    hook: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    practical_insight: str = Field(..., min_length=1)
    ending: str = Field(..., min_length=1)
    word_count: int | None = Field(default=None, ge=1, le=120)
    verdict: str | None = Field(default=None)
    corrections: ScriptCorrections = Field(default_factory=ScriptCorrections)


class VisualScene(StableModel):
    """Structured parameters a future ComfyUI/asset stage can consume."""

    subject: str = ""
    environment: str = ""
    composition: str = ""
    lighting: str = ""
    camera_motion: str = ""
    focus: str = ""
    style: str = ""


class VisualBranding(StableModel):
    """Channel branding decisions for the shot plan."""

    use_logo: bool = True
    use_broll: bool = True
    broll_source: str | None = None


class VisualShot(StableModel):
    """One timed shot in the plan."""

    id: int
    block: ScriptBlockName
    start_second: float
    end_second: float
    duration_seconds: float
    visual: str
    camera: str
    transition: str
    reason: str
    purpose: str
    learning_goal: str
    visual_type: str
    scene: VisualScene = Field(default_factory=VisualScene)


class VisualPlanOutput(StageOutput):
    """A complete 35-45s visual plan. Mirrors prompt 04's output schema."""

    total_seconds: float = 0.0
    shots: list[VisualShot] = Field(default_factory=list)
    branding: VisualBranding = Field(default_factory=VisualBranding)