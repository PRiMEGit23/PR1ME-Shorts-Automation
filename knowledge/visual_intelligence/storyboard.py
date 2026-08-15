"""Visual Storyboard schema: the derived, goal-driven shot plan for a topic.

A VisualStoryboard is the deterministic output of the Visual Intelligence
Engine. It carries no prompt strings and no model syntax: each StoryboardScene
bundles the semantic intent (VisualGoal, ShotType, engineering visualizations),
the cinematic plans (camera, lighting, composition, transition), the thumbnail
priority computed by the ThumbnailDirector, and the content needed to compile
it (subjects, environment, depth, palette, mood, scale reference, negatives,
tags). The Prompt Compiler therefore needs nothing but the storyboard itself.

Plan field names mirror the VisualArchitecture Camera/Composition/Lighting
models so the existing SDXL phrase builders apply unchanged.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from knowledge.visual_architecture import (
    MAX_SCENES,
    MIN_SCENES,
    CameraAngle,
    CameraDistance,
    CameraHeight,
    ColorPalette,
    CompositionRule,
    Depth,
    EngineeringDomain,
    Framing,
    Lens,
    LightDirection,
    LightingStyle,
    Modality,
    Mood,
    Motion,
    NegativeSpace,
    ScaleReference,
    Subject,
    TransitionType,
)
from knowledge.visual_intelligence.visual_goal import VisualGoal

STORYBOARD_VERSION = "1.0.0"


class ShotType(StrEnum):
    """The cinematic shot archetype chosen for a scene's visual goal."""

    MACRO = "macro shot"
    EXTREME_MACRO = "extreme macro shot"
    HERO = "hero shot"
    CROSS_SECTION = "cross-section"
    CUTAWAY = "cutaway"
    TRANSPARENT = "transparent view"
    EXPLODED_VIEW = "exploded view"
    ISOMETRIC = "isometric"
    ORTHOGRAPHIC = "orthographic"
    BLUEPRINT = "blueprint"
    CAD_RENDER = "CAD render"
    MICROSCOPE = "microscope"
    SLOW_MOTION = "slow motion"
    TIME_LAPSE = "time lapse"
    PROCESS_SEQUENCE = "process sequence"
    BEFORE_AFTER = "before/after"
    COMPARISON_SPLIT = "comparison split"
    XRAY = "X-ray"
    WIREFRAME_OVERLAY = "wireframe overlay"
    ANNOTATED_DIAGRAM = "annotated diagram"
    MANUFACTURING_SEQUENCE = "manufacturing sequence"


class EngineeringVisualizationType(StrEnum):
    """An engineering overlay or rendering style applied on top of the shot."""

    CROSS_SECTION = "cross section"
    EXPLODED_ASSEMBLY = "exploded assembly"
    TRANSPARENT_HOUSING = "transparent housing"
    WIREFRAME_OVERLAY = "wireframe overlay"
    STRESS_DIRECTION = "stress direction"
    HEAT_MAP = "heat map"
    FORCE_ARROWS = "force arrows"
    TOLERANCE_OVERLAY = "tolerance overlay"
    DIMENSION_OVERLAY = "dimension overlay"
    MATERIAL_CALLOUTS = "material callouts"
    MANUFACTURING_STEPS = "manufacturing steps"
    LAYER_PRINT = "layer-by-layer print"


class EngineeringVisualization(BaseModel):
    """One engineering visualization with the tokens the compiler may use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: EngineeringVisualizationType
    elements: list[str] = Field(default_factory=list, max_length=8)
    prompt_tokens: list[str] = Field(default_factory=list, max_length=8)
    rationale: str = Field(default="", max_length=200)


class SceneIntent(BaseModel):
    """Why the scene exists and how it will be realized, before any phrasing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    goal: VisualGoal
    shot_type: ShotType
    engineering_visualizations: list[EngineeringVisualization] = Field(
        default_factory=list, max_length=2
    )
    rationale: str = Field(default="", max_length=300)


class CameraPlan(BaseModel):
    """Camera decision. Field names mirror VisualArchitecture.Camera."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    distance: CameraDistance
    angle: CameraAngle
    lens: Lens
    framing: Framing
    height: CameraHeight = CameraHeight.TABLE
    note: str = Field(default="", max_length=200)


class CompositionPlan(BaseModel):
    """Composition decision. Field names mirror VisualArchitecture.Composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: CompositionRule
    emphasis: str = Field(min_length=1, max_length=120)
    negative_space: NegativeSpace = NegativeSpace.NONE
    note: str = Field(default="", max_length=200)


class LightingPlan(BaseModel):
    """Lighting decision. Field names mirror VisualArchitecture.Lighting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    direction: LightDirection
    style: LightingStyle
    practical_sources: list[str] = Field(default_factory=list)
    key_color: str = Field(default="", max_length=60)
    note: str = Field(default="", max_length=200)


class Transition(BaseModel):
    """The cut into this scene from the previous one."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: TransitionType
    direction: str | None = None
    rationale: str = Field(default="", max_length=200)


class ThumbnailPriority(BaseModel):
    """Where this scene ranks as a thumbnail candidate and why."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score: int
    rank: int = Field(ge=1)
    rationale: str = Field(default="", max_length=300)


class StoryboardScene(BaseModel):
    """One fully directed scene: intent + plans + the content to compile it.

    The scene is self-contained: the compiler reads subjects, environment,
    depth, palette, mood, scale reference, negatives, and tags from this model
    alone and never needs the originating VisualArchitecture row.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    scene_index: int = Field(ge=1)
    intent: SceneIntent
    camera: CameraPlan
    composition: CompositionPlan
    lighting: LightingPlan
    depth: Depth
    mood: Mood
    motion: Motion = Field(default_factory=Motion)
    primary_subject: Subject
    secondary_subjects: list[Subject] = Field(default_factory=list, max_length=3)
    environment: str = Field(default="", max_length=120)
    color_palette: ColorPalette
    scale_reference: ScaleReference | None = None
    objects_to_avoid: list[str] = Field(default_factory=list, max_length=12)
    negative_elements: list[str] = Field(default_factory=list, max_length=12)
    consistency_tags: list[str] = Field(default_factory=list, max_length=12)
    branding_tags: list[str] = Field(default_factory=list, max_length=8)
    transition: Transition
    thumbnail_priority: ThumbnailPriority
    scene_importance: int = Field(default=3, ge=1, le=5)
    thumbnail_candidate: bool = False


class VisualStoryboard(BaseModel):
    """The full deterministic shot plan for one curated topic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = STORYBOARD_VERSION
    world_id: str = Field(min_length=1, max_length=60)
    engineering_domain: EngineeringDomain
    modality: Modality
    topic: str = Field(min_length=1, max_length=200)
    scenes: list[StoryboardScene] = Field(min_length=MIN_SCENES, max_length=MAX_SCENES)
    thumbnail_scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")

    @model_validator(mode="after")
    def _scenes_must_be_consecutive_and_unique(self) -> VisualStoryboard:
        ids = [s.scene_id for s in self.scenes]
        expected = [f"S{i}" for i in range(1, len(ids) + 1)]
        if ids != expected:
            raise ValueError(f"scene ids must be consecutive S1..S{len(ids)}, got {ids}")
        return self

    @model_validator(mode="after")
    def _thumbnail_scene_must_exist_and_rank_first(self) -> VisualStoryboard:
        ids = [s.scene_id for s in self.scenes]
        if self.thumbnail_scene_id not in ids:
            raise ValueError(
                f"thumbnail_scene_id '{self.thumbnail_scene_id}' is not a storyboard scene"
            )
        rank_one = [s for s in self.scenes if s.thumbnail_priority.rank == 1]
        if len(rank_one) != 1 or rank_one[0].scene_id != self.thumbnail_scene_id:
            raise ValueError(
                f"thumbnail_scene_id '{self.thumbnail_scene_id}' must be the single rank-1 scene"
            )
        return self