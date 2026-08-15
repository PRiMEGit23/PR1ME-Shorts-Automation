"""Storyboard builder: EducationalPlan -> directed VisualStoryboard.

The mission pipeline is Knowledge -> Educational Director -> AI Director ->
Visual Intelligence -> Storyboard. VisualIntelligenceEngine plans from a
VisualArchitecture; the runtime adapter maps the EducationalPlan's visual
methods onto directed scenes.

Two paths, one contract:

- ``director=None`` (legacy): the deterministic five-scene mapping the
  knowledge example stack uses (knowledge/image_qa/examples/_stack.py),
  mirrored here so the runtime stands alone. A test asserts the two
  storyboards are identical for the same plan.
- ``director=DirectorOutput`` (Phase 8): the storyboard is a verbatim
  translation of the AI Director's brief. No heuristics live here - every
  creative decision (importance, budgets, shot, camera, lighting,
  composition, motion, transition, mood, thumbnail) comes from the
  directive and is copied onto the scene.

The canonical shot-for-method mapping lives in
knowledge/ai_director/director_rules and is shared by both paths.

No model calls, no knowledge changes.
"""

from __future__ import annotations

from knowledge.ai_director.director_models import DirectorOutput
from knowledge.ai_director.director_rules import shot_for_method
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.visual_architecture import (
    CameraAngle,
    CameraDistance,
    ColorPalette,
    CompositionRule,
    Depth,
    DepthOfField,
    EngineeringDomain,
    Framing,
    Lens,
    LightDirection,
    LightingStyle,
    Material,
    Modality,
    Mood,
    Motion,
    NegativeSpace,
    ScaleReference,
    Subject,
    SurfaceFinish,
    TransitionType,
)
from knowledge.visual_intelligence.storyboard import (
    CameraPlan,
    CompositionPlan,
    EngineeringVisualization,
    EngineeringVisualizationType,
    LightingPlan,
    SceneIntent,
    ShotType,
    StoryboardScene,
    ThumbnailPriority,
    Transition,
    VisualStoryboard,
)
from knowledge.visual_intelligence.visual_goal import VisualGoal


def _shot_for_method(method: str) -> ShotType:
    """Legacy string-keyed shot lookup; delegates to the canonical rules."""
    return shot_for_method(method)


class StoryboardBuilder:
    """Deterministic plan -> storyboard adapter for the runtime pipeline."""

    def build(
        self,
        plan: EducationalPlan,
        *,
        engineering_domain: EngineeringDomain,
        modality: Modality,
        director: DirectorOutput | None = None,
    ) -> VisualStoryboard:
        """Direct a scene arc from the plan, or translate the director's brief."""
        if director is not None:
            return self._build_from_director(
                plan, engineering_domain, modality, director
            )
        return self._build_legacy(plan, engineering_domain, modality)

    # ------------------------------------------------------------ legacy --

    def _build_legacy(
        self,
        plan: EducationalPlan,
        engineering_domain: EngineeringDomain,
        modality: Modality,
    ) -> VisualStoryboard:
        """The canonical five-scene arc driven by the plan's visual methods."""
        methods = plan.visualization_priority
        specs = [
            (VisualGoal.INTRODUCE_CONCEPT, ShotType.HERO, None, 4, False),
            (
                VisualGoal.REVEAL_INTERNAL_GEOMETRY,
                shot_for_method(methods[0]),
                EngineeringVisualizationType.CROSS_SECTION,
                3,
                False,
            ),
            (
                VisualGoal.EXPLAIN_PROCESS,
                shot_for_method(methods[1]),
                None,
                3,
                False,
            ),
            (VisualGoal.COMPARE, shot_for_method(methods[2]), None, 3, False),
            (VisualGoal.SUMMARIZE, ShotType.HERO, None, 5, True),
        ]
        scenes: list[StoryboardScene] = []
        for index, (goal, shot_type, visualization, importance, thumbnail) in enumerate(
            specs, start=1
        ):
            scene_id = f"S{index}"
            vizs: list[EngineeringVisualization] = []
            if visualization is not None:
                vizs = [
                    EngineeringVisualization(
                        type=visualization,
                        prompt_tokens=["cutaway cross-section view"],
                        rationale="planned by the Educational Director's visual method",
                    )
                ]
            scenes.append(
                StoryboardScene(
                    scene_id=scene_id,
                    scene_index=index,
                    intent=SceneIntent(
                        goal=goal,
                        shot_type=shot_type,
                        engineering_visualizations=vizs,
                        rationale=f"{goal.value} scene for '{plan.topic}'",
                    ),
                    camera=CameraPlan(
                        distance=CameraDistance.MACRO,
                        angle=CameraAngle.EYE,
                        lens=Lens.MACRO_100,
                        framing=Framing.SUBJECT_CENTER,
                    ),
                    composition=CompositionPlan(
                        rule=CompositionRule.RULE_OF_THIRDS,
                        emphasis="primary subject",
                        negative_space=(
                            NegativeSpace.OVERLAY_TOP if thumbnail else NegativeSpace.NONE
                        ),
                    ),
                    lighting=LightingPlan(
                        direction=LightDirection.KEY,
                        style=LightingStyle.STUDIO,
                        key_color="white",
                    ),
                    depth=Depth(
                        midground="workbench",
                        background="studio backdrop",
                        dof=DepthOfField.SHALLOW,
                    ),
                    mood=Mood.PRECISE,
                    motion=Motion(),
                    primary_subject=Subject(
                        entity="the part",
                        materials=[Material.PLA],
                        surface_finish=[SurfaceFinish.SMOOTH],
                    ),
                    environment="clean studio workbench",
                    color_palette=ColorPalette(base="neutral gray", accent="white"),
                    scale_reference=ScaleReference(entity="ruler", size="5 cm"),
                    consistency_tags=["same part", "same palette", "studio backdrop"],
                    transition=Transition(
                        type=TransitionType.CUT,
                        rationale="continuity cut",
                    ),
                    thumbnail_priority=ThumbnailPriority(
                        score=15 if thumbnail else 10,
                        rank=1 if thumbnail else 2,
                        rationale="thumbnail candidate chosen by the storyboard",
                    ),
                    scene_importance=importance,
                    thumbnail_candidate=thumbnail,
                )
            )
        thumbnail_scene_id = next(
            s.scene_id for s in scenes if s.thumbnail_candidate
        )
        return VisualStoryboard(
            world_id="runtime",
            engineering_domain=engineering_domain,
            modality=modality,
            topic=plan.topic,
            scenes=scenes,
            thumbnail_scene_id=thumbnail_scene_id,
        )

    # ------------------------------------------------------- AI Director --

    def _build_from_director(
        self,
        plan: EducationalPlan,
        engineering_domain: EngineeringDomain,
        modality: Modality,
        director: DirectorOutput,
    ) -> VisualStoryboard:
        """Translate the AI Director's brief onto the storyboard verbatim."""
        scenes: list[StoryboardScene] = []
        for directive in director.scene_directives:
            scenes.append(
                StoryboardScene(
                    scene_id=directive.scene_id,
                    scene_index=directive.scene_index,
                    intent=SceneIntent(
                        goal=directive.visual_goal,
                        shot_type=directive.shot_type,
                        engineering_visualizations=directive.engineering_visualizations,
                        rationale=(
                            f"{directive.visual_goal.value} scene directed by the "
                            f"AI Director for '{plan.topic}'"
                        ),
                    ),
                    camera=directive.camera,
                    composition=directive.composition,
                    lighting=directive.lighting,
                    depth=Depth(
                        midground="workbench",
                        background="studio backdrop",
                        dof=DepthOfField.SHALLOW,
                    ),
                    mood=directive.mood,
                    motion=directive.motion,
                    primary_subject=Subject(
                        entity="the part",
                        materials=[Material.PLA],
                        surface_finish=[SurfaceFinish.SMOOTH],
                    ),
                    environment="clean studio workbench",
                    color_palette=ColorPalette(base="neutral gray", accent="white"),
                    scale_reference=ScaleReference(entity="ruler", size="5 cm"),
                    consistency_tags=["same part", "same palette", "studio backdrop"],
                    transition=directive.transition,
                    thumbnail_priority=directive.thumbnail_priority,
                    scene_importance=directive.importance,
                    thumbnail_candidate=directive.is_thumbnail,
                )
            )
        return VisualStoryboard(
            world_id="runtime",
            engineering_domain=engineering_domain,
            modality=modality,
            topic=plan.topic,
            scenes=scenes,
            thumbnail_scene_id=director.thumbnail_scene_id,
        )
