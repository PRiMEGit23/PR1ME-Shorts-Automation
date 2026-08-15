"""Render optimization schema: what the optimizer decided and why.

The optimizer closes the loop after Image QA. Given the report that REJECTED
an image, it produces an OptimizedRenderPlan: concrete actions, typed
changes to the storyboard scene (camera, lighting, composition,
visualization), deterministic prompt mutations, a workflow profile switch,
and a deterministic projection of the expected score improvement.

Nothing here renders anything: the plan is instructions a future stage (or a
human) executes, exactly like the QA repair suggestions - but stronger,
because each action names the exact field to change and the exact prompt
phrase to mutate.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from knowledge.image_qa.qa_models import QACheck
from knowledge.render_optimizer.render_profiles import RenderProfileKey
from knowledge.visual_architecture import (
    CameraAngle,
    CameraDistance,
    CompositionRule,
    Framing,
    Lens,
    LightDirection,
    LightingStyle,
    NegativeSpace,
)
from knowledge.visual_intelligence.storyboard import EngineeringVisualizationType

OPTIMIZER_VERSION = "1.0.0"

#: Scores improve monotonically toward these caps per optimization round.
MAX_SCORE = 100.0
MAX_GAIN_PER_ROUND = 40.0


class OptimizationActionKind(StrEnum):
    """What kind of change one optimization action represents."""

    VISUALIZATION = "visualization"
    CAMERA = "camera"
    LIGHTING = "lighting"
    COMPOSITION = "composition"
    PROMPT = "prompt"
    WORKFLOW = "workflow"
    CONSISTENCY = "consistency"


class OptimizationAction(BaseModel):
    """One concrete action: what to change, by how much, and why."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: OptimizationActionKind
    check: QACheck
    instruction: str = Field(min_length=1, max_length=300)
    expected_gain: float = Field(ge=0.0, le=MAX_GAIN_PER_ROUND)
    target_score: str = Field(min_length=1, max_length=40)
    rationale: str = Field(min_length=1, max_length=400)


class MutationKind(StrEnum):
    REPLACE = "replace"
    APPEND = "append"


class PromptMutation(BaseModel):
    """A deterministic edit to the compiled prompt or negative prompt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: MutationKind
    target_prompt: str = Field(pattern=r"^(positive|negative)$")
    target: str = Field(default="", max_length=300)
    replacement: str = Field(default="", max_length=300)
    rationale: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def _replace_requires_target(self) -> PromptMutation:
        if self.kind is MutationKind.REPLACE and not self.target:
            raise ValueError("a REPLACE mutation requires a target phrase")
        return self


class CameraChange(BaseModel):
    """Camera fields to change on the storyboard scene."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    distance: CameraDistance | None = None
    angle: CameraAngle | None = None
    lens: Lens | None = None
    framing: Framing | None = None
    rationale: str = Field(min_length=1, max_length=300)


class LightingChange(BaseModel):
    """Lighting fields to change on the storyboard scene."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    direction: LightDirection | None = None
    style: LightingStyle | None = None
    rationale: str = Field(min_length=1, max_length=300)


class CompositionChange(BaseModel):
    """Composition fields to change on the storyboard scene."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: CompositionRule | None = None
    emphasis: str | None = Field(default=None, max_length=120)
    negative_space: NegativeSpace | None = None
    rationale: str = Field(min_length=1, max_length=300)


class VisualizationChange(BaseModel):
    """Engineering visualization to add or replace on the scene."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: EngineeringVisualizationType
    elements: list[str] = Field(default_factory=list, max_length=8)
    prompt_tokens: list[str] = Field(default_factory=list, max_length=8)
    rationale: str = Field(min_length=1, max_length=300)


class WorkflowChange(BaseModel):
    """Switch to a different ComfyUI workflow profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: RenderProfileKey
    rationale: str = Field(min_length=1, max_length=300)


class ExpectedScoreImprovement(BaseModel):
    """Deterministic projection of the eight scores after the actions run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engineering: float = Field(ge=0.0, le=MAX_SCORE)
    educational: float = Field(ge=0.0, le=MAX_SCORE)
    composition: float = Field(ge=0.0, le=MAX_SCORE)
    subject_hierarchy: float = Field(ge=0.0, le=MAX_SCORE)
    visual_clarity: float = Field(ge=0.0, le=MAX_SCORE)
    thumbnail: float = Field(ge=0.0, le=MAX_SCORE)
    consistency: float = Field(ge=0.0, le=MAX_SCORE)
    overall: float = Field(ge=0.0, le=MAX_SCORE)
    improvement: float = Field(ge=0.0, le=MAX_SCORE)
    predicted_pass: bool


class OptimizedRenderPlan(BaseModel):
    """The full optimization prescription for one rejected image."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = OPTIMIZER_VERSION
    topic: str = Field(min_length=1, max_length=200)
    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    optimization_actions: list[OptimizationAction] = Field(
        default_factory=list, max_length=24
    )
    prompt_mutations: list[PromptMutation] = Field(default_factory=list, max_length=32)
    workflow_changes: list[WorkflowChange] = Field(default_factory=list, max_length=6)
    camera_changes: list[CameraChange] = Field(default_factory=list, max_length=4)
    lighting_changes: list[LightingChange] = Field(default_factory=list, max_length=4)
    composition_changes: list[CompositionChange] = Field(
        default_factory=list, max_length=4
    )
    visualization_changes: list[VisualizationChange] = Field(
        default_factory=list, max_length=4
    )
    expected_score_improvement: ExpectedScoreImprovement
    rationale: str = Field(min_length=1, max_length=500)