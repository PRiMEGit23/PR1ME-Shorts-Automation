"""Learning Engine schemas: observations, history, patterns, proposals (Phase 11).

The Learning Engine never edits the knowledge base. Everything it reads is
a deterministic record of completed pipeline runs (``ProjectRecord`` /
``PipelineHistory``); everything it writes is a reviewable
``ImprovementProposal`` with supporting evidence and a ``KnowledgeDiff``.
No LLM, no randomness, no timestamps: the same history always produces the
same report, and trends are ordered by the caller-supplied ``run_index``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from knowledge.visual_architecture import (
    CameraAngle,
    CameraDistance,
    Framing,
    Lens,
    LightDirection,
    LightingStyle,
    TransitionType,
)
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualizationType,
    ShotType,
)

#: The Learning Engine's own version stamp.
LEARNING_ENGINE_VERSION = "11.0.0"


class ProposalKind(StrEnum):
    """The six reviewable improvement kinds the engine can generate."""

    KNOWLEDGE = "knowledge"
    MODEL = "model"
    DIRECTOR = "director"
    COMPILER = "compiler"
    WORKFLOW = "workflow"
    OPTIMIZATION = "optimization"


class SceneObservation(BaseModel):
    """One scene of one completed run: the smallest learnable unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1, max_length=120)
    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    scene_index: int = Field(ge=1)
    seed: int
    topic: str = Field(min_length=1, max_length=200)
    cognitive_step: str = Field(default="", max_length=60)

    #: The cinematic decisions the scene was shot with (storyboard facts).
    shot_type: ShotType
    camera_distance: CameraDistance
    camera_angle: CameraAngle
    lens: Lens
    framing: Framing
    light_direction: LightDirection
    lighting_style: LightingStyle
    transition_type: TransitionType
    visualization_type: EngineeringVisualizationType | None = None

    #: The compiled backend decisions (Model Director facts).
    image_model: str = Field(min_length=1, max_length=40)
    video_model: str = Field(min_length=1, max_length=40)
    render_profile: str = Field(min_length=1, max_length=40)
    quality_target: str = Field(min_length=1, max_length=40)

    #: What the pipeline predicted before rendering.
    predicted_qa: float = Field(ge=0.0, le=100.0)

    #: What the pipeline observed after rendering (the QA verdict winner).
    qa_score: float = Field(ge=0.0, le=100.0)
    educational_score: float = Field(ge=0.0, le=100.0)
    retention_prediction: float = Field(ge=0.0, le=100.0)
    thumbnail_priority: int = Field(ge=0)

    #: Render-loop facts (attempts, switches, mutations, optimizer actions).
    attempts: int = Field(ge=1, le=12)
    failed_attempts: int = Field(ge=0, le=12)
    model_switches: int = Field(ge=0)
    prompt_mutations: int = Field(ge=0)
    optimization_actions: int = Field(ge=0)

    #: Resource facts (predicted duration / VRAM when the pipeline is simulated).
    render_duration_ms: float = Field(ge=0.0)
    vram_mb: int = Field(ge=0)

    #: The negative-token signature of the winning prompt (sorted, joined).
    negative_tokens: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    passed: bool


class ProjectRecord(BaseModel):
    """One completed (or failed) pipeline run, ready for learning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1, max_length=120)
    job_id: str = Field(default="", min_length=0, max_length=120)
    #: Caller-supplied ordering for trends (no timestamps: determinism).
    run_index: int = Field(ge=0)
    topic: str = Field(min_length=1, max_length=200)
    seed: int
    status: Literal["complete", "failed"] = "complete"
    published: bool = True
    total_duration_ms: float = Field(ge=0.0)
    scenes: tuple[SceneObservation, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def _scenes_belong_to_this_run(self) -> ProjectRecord:
        if any(scene.run_id != self.run_id for scene in self.scenes):
            raise ValueError(f"scene run_id must match project run_id {self.run_id!r}")
        ids = [scene.scene_id for scene in self.scenes]
        expected = [f"S{i}" for i in range(1, len(ids) + 1)]
        if ids != expected:
            raise ValueError(
                f"scene ids must be consecutive S1..S{len(ids)}, got {ids}"
            )
        return self


class PipelineHistory(BaseModel):
    """The immutable input to learning: one deterministic run history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = LEARNING_ENGINE_VERSION
    projects: tuple[ProjectRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _run_indexes_must_be_unique(self) -> PipelineHistory:
        indexes = [project.run_index for project in self.projects]
        if len(set(indexes)) != len(indexes):
            raise ValueError(f"run_index must be unique, got {sorted(indexes)}")
        return self


# ------------------------------------------------------------------ outputs --


class LeaderboardRow(BaseModel):
    """One deterministic leaderboard row (count, mean, min, max, pass rate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=200)
    count: int = Field(ge=1)
    mean: float = Field(ge=0.0, le=100.0)
    minimum: float = Field(ge=0.0, le=100.0)
    maximum: float = Field(ge=0.0, le=100.0)
    pass_rate: float = Field(ge=0.0, le=1.0)

    #: Optional render metrics (render leaderboard).
    mean_attempts: float | None = None
    mean_duration_ms: float | None = None
    mean_vram_mb: float | None = None
    #: Optional curriculum metrics (topic leaderboard).
    mean_retention: float | None = None
    mean_educational: float | None = None
    mean_thumbnail_priority: float | None = None


class QualitySummary(BaseModel):
    """The overall deterministic health of a run history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_count: int = Field(ge=0)
    passed_scenes: int = Field(ge=0)
    failed_scenes: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    mean_qa: float = Field(ge=0.0, le=100.0)
    mean_educational: float = Field(ge=0.0, le=100.0)
    mean_attempts: float = Field(ge=0.0)
    total_switches: int = Field(ge=0)
    mean_duration_ms: float = Field(ge=0.0)
    mean_vram_mb: float = Field(ge=0.0)
    mean_retention: float = Field(ge=0.0, le=100.0)


class SuccessProfile(BaseModel):
    """What one winning group looks like: the successes behind a pattern."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: str = Field(min_length=1, max_length=40)
    key: str = Field(min_length=1, max_length=200)
    passed: int = Field(ge=0)
    total: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    mean_qa: float = Field(ge=0.0, le=100.0)
    mean_educational: float = Field(ge=0.0, le=100.0)
    scene_ids: tuple[str, ...] = Field(default_factory=tuple)


class FailureProfile(BaseModel):
    """What one losing group looks like: the failures behind a proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: str = Field(min_length=1, max_length=40)
    key: str = Field(min_length=1, max_length=200)
    failed: int = Field(ge=0)
    total: int = Field(ge=0)
    failure_rate: float = Field(ge=0.0, le=1.0)
    mean_attempts: float = Field(ge=0.0)
    total_switches: int = Field(ge=0)
    mean_mutations: float = Field(ge=0.0)
    mean_actions: float = Field(ge=0.0)
    worst_qa: float = Field(ge=0.0, le=100.0)
    worst_scene: str = Field(default="", max_length=40)
    scene_ids: tuple[str, ...] = Field(default_factory=tuple)


class PatternObservation(BaseModel):
    """One deterministic comparison: a winner group vs the rest of a history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pattern_id: str = Field(pattern=r"^[a-z0-9_\-\.]+$")
    #: qa / attempts / retention: what is being compared.
    metric: str = Field(min_length=1, max_length=40)
    #: The observation dimension (shot_type, image_model, lens, ...).
    dimension: str = Field(min_length=1, max_length=40)
    winner: str = Field(min_length=1, max_length=200)
    #: The aggregate of every other group in the same dimension.
    rest_mean: float = Field(ge=0.0, le=100.0)
    delta: float
    winner_count: int = Field(ge=1)
    rest_count: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    #: True when a lower value is better (attempts / duration).
    better_when_lower: bool = False
    evidence_scenes: tuple[str, ...] = Field(default_factory=tuple)
    description: str = Field(min_length=1, max_length=300)


class KnowledgeDiff(BaseModel):
    """A reviewable before/after edit against the (never modified) knowledge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_kind: ProposalKind
    module: str = Field(min_length=1, max_length=200)
    table: str = Field(min_length=1, max_length=120)
    entry_key: str = Field(min_length=1, max_length=120)
    field: str = Field(min_length=1, max_length=120)
    before: str = Field(min_length=1, max_length=120)
    after: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[str, ...] = Field(default_factory=tuple)
    predicted_improvement: str = Field(min_length=1, max_length=200)


class ImprovementProposal(BaseModel):
    """The base of every reviewable improvement the engine generates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ProposalKind
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[str, ...] = Field(default_factory=tuple)
    affected_modules: tuple[str, ...] = Field(default_factory=tuple)
    predicted_improvement: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=400)
    diff: KnowledgeDiff | None = None


class KnowledgeProposal(ImprovementProposal):
    """A knowledge-table edit: one entry field before/after with evidence."""

    kind: Literal[ProposalKind.KNOWLEDGE] = ProposalKind.KNOWLEDGE
    knowledge_table: str = Field(min_length=1, max_length=120)
    entry_key: str = Field(min_length=1, max_length=120)
    field: str = Field(min_length=1, max_length=120)
    before: str = Field(min_length=1, max_length=120)
    after: str = Field(min_length=1, max_length=120)


class ModelRecommendation(ImprovementProposal):
    """Adopt a winning image / video model for a scope with measured gain."""

    kind: Literal[ProposalKind.MODEL] = ProposalKind.MODEL
    scope_key: str = Field(min_length=1, max_length=200)
    from_model: str = Field(min_length=1, max_length=40)
    to_model: str = Field(min_length=1, max_length=40)
    predicted_qa_gain: float = Field(ge=0.0)


class DirectorRecommendation(ImprovementProposal):
    """Adopt a winning cinematic decision (shot, lens, light, transition)."""

    kind: Literal[ProposalKind.DIRECTOR] = ProposalKind.DIRECTOR
    area: str = Field(min_length=1, max_length=60)
    scope_key: str = Field(min_length=1, max_length=200)
    current_value: str = Field(min_length=1, max_length=120)
    suggested_value: str = Field(min_length=1, max_length=120)


class CompilerRecommendation(ImprovementProposal):
    """Adopt a winning prompt pattern (negative token signature, context)."""

    kind: Literal[ProposalKind.COMPILER] = ProposalKind.COMPILER
    prompt_field: str = Field(pattern=r"^(positive|negative)$")
    token: str = Field(min_length=1, max_length=120)
    context: str = Field(min_length=1, max_length=200)


class WorkflowRecommendation(ImprovementProposal):
    """Adopt a winning render profile for a scope with measured gain."""

    kind: Literal[ProposalKind.WORKFLOW] = ProposalKind.WORKFLOW
    scope_key: str = Field(min_length=1, max_length=200)
    current_profile: str = Field(min_length=1, max_length=40)
    suggested_profile: str = Field(min_length=1, max_length=40)
    predicted_qa_gain: float = Field(ge=0.0)


class OptimizationRecommendation(ImprovementProposal):
    """Adjust a deterministic optimizer rule based on measured failure."""

    kind: Literal[ProposalKind.OPTIMIZATION] = ProposalKind.OPTIMIZATION
    trigger: str = Field(min_length=1, max_length=200)
    optimizer_rule: str = Field(min_length=1, max_length=80)
    current_value: str = Field(min_length=1, max_length=120)
    suggested_value: str = Field(min_length=1, max_length=120)


#: Every concrete proposal the engine can produce (for validation dispatch).
Proposal = (
    KnowledgeProposal
    | ModelRecommendation
    | DirectorRecommendation
    | CompilerRecommendation
    | WorkflowRecommendation
    | OptimizationRecommendation
)


class LearningReport(BaseModel):
    """The complete deterministic output of one learning pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = LEARNING_ENGINE_VERSION
    project_count: int = Field(ge=0)
    scene_count: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    overall: QualitySummary
    success_profiles: tuple[SuccessProfile, ...] = Field(default_factory=tuple)
    failure_profiles: tuple[FailureProfile, ...] = Field(default_factory=tuple)
    patterns: tuple[PatternObservation, ...] = Field(default_factory=tuple)
    proposals: tuple[Proposal, ...] = Field(default_factory=tuple)
    knowledge_diffs: tuple[KnowledgeDiff, ...] = Field(default_factory=tuple)
    #: The eight leaderboards, keyed by name (model, workflow, prompt, qa,
    #: render, topic, visual_strategy, engineering_visualization).
    leaderboards: dict[str, tuple[LeaderboardRow, ...]] = Field(default_factory=dict)
    summary: str = Field(min_length=1, max_length=400)
