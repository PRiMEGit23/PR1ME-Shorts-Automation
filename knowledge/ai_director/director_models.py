"""AI Director schemas: the creative decisions that precede any prompt.

The AI Director is a deterministic decision engine that sits between the
Educational Director and Visual Intelligence. It consumes an EducationalPlan
(the teaching intent) and emits a DirectorOutput: one SceneDirective per
scene carrying the full creative brief - importance, budgets, emphasis,
camera, lighting, composition, motion, transition, mood - plus the global
arc decisions (hero scene, thumbnail scene, recap scene, reveal plan, pacing
profile, emotion arc) and the predicted retention / attention numbers.

Everything downstream reads this brief instead of inventing its own
heuristics. The models are pure data: frozen, extra="forbid", mirroring the
rest of the knowledge base. No randomness, no LLM, no rendering syntax.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from knowledge.educational_director.educational_models import TeachingStrategy
from knowledge.visual_architecture import Mood
from knowledge.visual_intelligence.storyboard import (
    CameraPlan,
    CompositionPlan,
    EngineeringVisualization,
    LightingPlan,
    Motion,
    ShotType,
    ThumbnailPriority,
    Transition,
)
from knowledge.visual_intelligence.visual_goal import VisualGoal

AI_DIRECTOR_VERSION = "8.0.0"

MIN_DIRECTED_SCENES = 4
MAX_DIRECTED_SCENES = 6


class SceneDirective(BaseModel):
    """The AI Director's full creative brief for one scene.

    The directive is the single source of truth for this scene: the Visual
    Intelligence / Storyboard layer copies it verbatim into the storyboard,
    and every downstream module (prompt compiler, workflow builder, render
    optimizer) consumes the decisions it encodes. All numeric fields are
    deterministic rule outputs, never random.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_index: int = Field(ge=1)
    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")

    #: Why the scene exists and how it will be realized.
    visual_goal: VisualGoal
    shot_type: ShotType
    engineering_visualizations: list[EngineeringVisualization] = Field(
        default_factory=list, max_length=2
    )

    #: Scene importance (1-5) and the creative budgets (1-10 each).
    importance: int = Field(ge=1, le=5)
    visual_budget: int = Field(ge=1, le=10)
    animation_budget: int = Field(ge=1, le=10)
    motion_budget: int = Field(ge=1, le=10)
    camera_intensity: int = Field(ge=1, le=10)
    lighting_priority: int = Field(ge=1, le=10)
    diagram_priority: int = Field(ge=1, le=10)
    engineering_emphasis: int = Field(ge=1, le=10)
    comparison_emphasis: int = Field(ge=1, le=10)

    #: Emotional intensity (1-10) and information pacing (1-10).
    emotion: int = Field(ge=1, le=10)
    pacing: int = Field(ge=1, le=10)

    #: Predicted outcome of this scene, before any render happens.
    retention_score: float = Field(ge=0.0, le=100.0)
    expected_attention: float = Field(ge=0.0, le=100.0)

    #: When the scene's information is revealed relative to the other scenes.
    reveal_order: int = Field(ge=1)

    #: The concrete cinematic decisions (mapping lives in director_rules).
    camera: CameraPlan
    lighting: LightingPlan
    composition: CompositionPlan
    motion: Motion
    mood: Mood
    transition: Transition

    #: Where this scene ranks as a thumbnail candidate (rank 1 = the pick).
    thumbnail_priority: ThumbnailPriority

    #: Structural roles: at most one scene holds each role.
    is_hero: bool = False
    is_thumbnail: bool = False
    is_recap: bool = False

    #: Why the director chose this brief (traceability, not prose).
    rationale: str = Field(default="", max_length=300)


class DirectorOutput(BaseModel):
    """The complete creative brief for one topic, decided before any prompt.

    Produced entirely deterministically from an EducationalPlan. Carries the
    arc structure (scene count, hero / thumbnail / recap), every scene's
    creative brief, the global profiles (emotion arc, pacing profile, reveal
    plan), and the predicted retention / attention - everything the Visual
    Intelligence layer needs to build the storyboard, and nothing about
    rendering.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = AI_DIRECTOR_VERSION
    topic: str = Field(min_length=1, max_length=200)
    teaching_strategy: TeachingStrategy
    scene_count: int = Field(ge=MIN_DIRECTED_SCENES, le=MAX_DIRECTED_SCENES)
    scene_directives: list[SceneDirective] = Field(
        min_length=MIN_DIRECTED_SCENES, max_length=MAX_DIRECTED_SCENES
    )

    hero_scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    thumbnail_scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    recap_scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")

    emotion_arc: str = Field(min_length=1, max_length=60)
    pacing_profile: str = Field(min_length=1, max_length=60)
    reveal_plan: str = Field(min_length=1, max_length=60)

    #: Predicted outcomes of the whole film, before a single render.
    predicted_retention: float = Field(ge=0.0, le=100.0)
    predicted_attention: float = Field(ge=0.0, le=100.0)

    #: One-sentence deterministic summary of the directing decisions.
    summary: str = Field(default="", max_length=400)

    @model_validator(mode="after")
    def _directives_consecutive(self) -> DirectorOutput:
        ids = [d.scene_id for d in self.scene_directives]
        expected = [f"S{i}" for i in range(1, len(ids) + 1)]
        if ids != expected:
            raise ValueError(f"scene ids must be consecutive S1..S{len(ids)}, got {ids}")
        if [d.scene_index for d in self.scene_directives] != list(range(1, len(ids) + 1)):
            raise ValueError("scene_index must run 1..n in directive order")
        return self

    @model_validator(mode="after")
    def _roles_are_unique_and_consistent(self) -> DirectorOutput:
        heroes = [s for s in self.scene_directives if s.is_hero]
        thumbnails = [s for s in self.scene_directives if s.is_thumbnail]
        recaps = [s for s in self.scene_directives if s.is_recap]
        if len(heroes) != 1:
            raise ValueError(f"exactly one hero scene required, got {len(heroes)}")
        if len(thumbnails) != 1:
            raise ValueError(f"exactly one thumbnail scene required, got {len(thumbnails)}")
        if len(recaps) != 1:
            raise ValueError(f"exactly one recap scene required, got {len(recaps)}")
        hero, thumbnail, recap = heroes[0], thumbnails[0], recaps[0]
        if hero.scene_id != self.hero_scene_id:
            raise ValueError("hero_scene_id must match the single is_hero directive")
        if thumbnail.scene_id != self.thumbnail_scene_id:
            raise ValueError("thumbnail_scene_id must match the single is_thumbnail directive")
        if recap.scene_id != self.recap_scene_id:
            raise ValueError("recap_scene_id must match the single is_recap directive")
        if recap.scene_id != self.scene_directives[-1].scene_id:
            raise ValueError("the recap scene must be the final scene")
        if hero.scene_id == recap.scene_id:
            raise ValueError("the hero scene and the recap scene must be distinct")
        if thumbnail.scene_id == recap.scene_id:
            raise ValueError("the thumbnail scene and the recap scene must be distinct")
        if thumbnail.thumbnail_priority.rank != 1:
            raise ValueError("the thumbnail scene must be the single rank-1 candidate")
        rank_one = [
            d.scene_id for d in self.scene_directives if d.thumbnail_priority.rank == 1
        ]
        if rank_one != [thumbnail.scene_id]:
            raise ValueError(
                f"exactly one rank-1 thumbnail candidate required, got {rank_one}"
            )
        return self
