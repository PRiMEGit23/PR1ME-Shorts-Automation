"""Shared QA stack builder for the worked examples.

Turns a topic's EducationalPlan + a small scene spec into the full QA input
stack: VisualStoryboard, CompiledPrompt, and GeneratedImageMetadata. Kept
deterministic and compact so each worked example reads top to bottom.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge.compiler import compile_for_storyboard
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.image_qa.qa_models import GeneratedImageMetadata
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
from knowledge.visual_intelligence import VisualIntelligenceEngine, VisualStoryboard
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
)
from knowledge.visual_intelligence.visual_goal import VisualGoal


@dataclass(frozen=True)
class SceneSpec:
    """The minimal facts needed to direct one storyboard scene."""

    goal: VisualGoal
    shot_type: ShotType
    visualization: EngineeringVisualizationType | None = None
    visualization_tokens: tuple[str, ...] = ()
    entity: str = "the part"
    materials: tuple[Material, ...] = ()
    scene_importance: int = 3
    thumbnail_candidate: bool = False


@dataclass(frozen=True)
class RenderSpec:
    """What the (simulated) vision pipeline reports back from the render."""

    scene_id: str
    subject_present: bool = True
    subject_prominence: float = 1.0
    subject_occluded: bool = False
    hierarchy_clear: bool = True
    engineering_accuracy: float = 1.0
    geometry_correct: bool = True
    geometry_quality: float = 1.0
    material_correct: bool = True
    material_quality: float = 1.0
    camera_distance_matches: bool = True
    camera_angle_matches: bool = True
    lens_matches: bool = True
    lighting_direction_matches: bool = True
    lighting_style_matches: bool = True
    composition_rule_matches: bool = True
    composition_quality: float = 1.0
    clutter_level: float = 0.0
    visual_clarity: float = 1.0
    method_implemented: bool = True
    annotations_present: bool = True
    annotation_quality: float = 1.0
    comparison_axis_present: bool = True
    thumbnail_contrast: float = 1.0
    thumbnail_focus: float = 1.0
    thumbnail_negative_space: bool = True
    scene_consistency: float = 1.0
    consistency_violations: list[str] = field(default_factory=list)
    prompt_term_mismatches: list[str] = field(default_factory=list)


_ENGINE = VisualIntelligenceEngine()


def build_stack(
    plan: EducationalPlan,
    *,
    domain: EngineeringDomain,
    modality: Modality,
    specs: list[SceneSpec],
    thumbnail_scene_id: str,
    renders: list[RenderSpec],
) -> tuple[VisualStoryboard, dict[str, object], dict[str, GeneratedImageMetadata]]:
    """Build storyboard + compiled prompts + metadata for one topic.

    Returns (storyboard, prompts_by_scene_id, metadata_by_scene_id).
    """
    scenes = _scenes(plan, specs, thumbnail_scene_id)
    storyboard = _storyboard(plan, domain, modality, scenes, thumbnail_scene_id)
    compiled = compile_for_storyboard(storyboard, "sdxl", topic=plan.topic)
    prompts = {"scenes": compiled.scenes, "thumbnail": compiled.thumbnail}
    metadata = {
        spec.scene_id: _metadata(spec)
        for spec in renders
    }
    return storyboard, prompts, metadata


def _scenes(
    plan: EducationalPlan,
    specs: list[SceneSpec],
    thumbnail_scene_id: str,
) -> list[StoryboardScene]:
    scenes: list[StoryboardScene] = []
    for index, spec in enumerate(specs, start=1):
        scene_id = f"S{index}"
        subject = Subject(
            entity=spec.entity,
            materials=list(spec.materials) or [Material.PLA],
            surface_finish=[SurfaceFinish.SMOOTH],
        )
        vizs = (
            [
                EngineeringVisualization(
                    type=spec.visualization,
                    prompt_tokens=list(spec.visualization_tokens) or [spec.visualization.value],
                    rationale="planned by the Educational Director's visual method",
                )
            ]
            if spec.visualization
            else []
        )
        intent = SceneIntent(
            goal=spec.goal,
            shot_type=spec.shot_type,
            engineering_visualizations=vizs,
            rationale=f"{spec.goal.value} scene for '{plan.topic}'",
        )
        is_thumbnail = scene_id == thumbnail_scene_id
        scenes.append(
            StoryboardScene(
                scene_id=scene_id,
                scene_index=index,
                intent=intent,
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
                        NegativeSpace.OVERLAY_TOP if is_thumbnail else NegativeSpace.NONE
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
                primary_subject=subject,
                environment="clean studio workbench",
                color_palette=ColorPalette(base="neutral gray", accent="white"),
                scale_reference=ScaleReference(entity="ruler", size="5 cm"),
                consistency_tags=["same part", "same palette", "studio backdrop"],
                transition=Transition(
                    type=TransitionType.CUT,
                    rationale="continuity cut",
                ),
                thumbnail_priority=ThumbnailPriority(
                    score=15 if is_thumbnail else 10,
                    rank=1 if is_thumbnail else 2,
                    rationale="thumbnail candidate chosen by the storyboard",
                ),
                scene_importance=spec.scene_importance,
                thumbnail_candidate=spec.thumbnail_candidate or is_thumbnail,
            )
        )
    return scenes


def _storyboard(
    plan: EducationalPlan,
    domain: EngineeringDomain,
    modality: Modality,
    scenes: list[StoryboardScene],
    thumbnail_scene_id: str,
) -> VisualStoryboard:
    return VisualStoryboard(
        world_id="qa-example",
        engineering_domain=domain,
        modality=modality,
        topic=plan.topic,
        scenes=scenes,
        thumbnail_scene_id=thumbnail_scene_id,
    )


def _metadata(spec: RenderSpec) -> GeneratedImageMetadata:
    return GeneratedImageMetadata(
        scene_id=spec.scene_id,
        subject_present=spec.subject_present,
        subject_prominence=spec.subject_prominence,
        subject_occluded=spec.subject_occluded,
        hierarchy_clear=spec.hierarchy_clear,
        engineering_accuracy=spec.engineering_accuracy,
        geometry_correct=spec.geometry_correct,
        geometry_quality=spec.geometry_quality,
        material_correct=spec.material_correct,
        material_quality=spec.material_quality,
        camera_distance_matches=spec.camera_distance_matches,
        camera_angle_matches=spec.camera_angle_matches,
        lens_matches=spec.lens_matches,
        lighting_direction_matches=spec.lighting_direction_matches,
        lighting_style_matches=spec.lighting_style_matches,
        composition_rule_matches=spec.composition_rule_matches,
        composition_quality=spec.composition_quality,
        clutter_level=spec.clutter_level,
        visual_clarity=spec.visual_clarity,
        method_implemented=spec.method_implemented,
        annotations_present=spec.annotations_present,
        annotation_quality=spec.annotation_quality,
        comparison_axis_present=spec.comparison_axis_present,
        thumbnail_contrast=spec.thumbnail_contrast,
        thumbnail_focus=spec.thumbnail_focus,
        thumbnail_negative_space=spec.thumbnail_negative_space,
        scene_consistency=spec.scene_consistency,
        consistency_violations=spec.consistency_violations,
        prompt_term_mismatches=spec.prompt_term_mismatches,
    )


def _shot_for_method(method: str) -> ShotType:
    mapping = {
        "comparison board": ShotType.COMPARISON_SPLIT,
        "cross section": ShotType.CROSS_SECTION,
        "stress visualization": ShotType.ANNOTATED_DIAGRAM,
        "transparent housing": ShotType.TRANSPARENT,
        "motion visualization": ShotType.SLOW_MOTION,
        "exploded view": ShotType.EXPLODED_VIEW,
        "animation": ShotType.HERO,
        "thermal visualization": ShotType.ANNOTATED_DIAGRAM,
        "timeline": ShotType.PROCESS_SEQUENCE,
        "diagram": ShotType.ANNOTATED_DIAGRAM,
        "macro": ShotType.MACRO,
        "cutaway": ShotType.CUTAWAY,
        "xray": ShotType.XRAY,
        "infographic": ShotType.ANNOTATED_DIAGRAM,
        "CAD": ShotType.CAD_RENDER,
        "section view": ShotType.CROSS_SECTION,
        "microscope": ShotType.MICROSCOPE,
        "assembly sequence": ShotType.PROCESS_SEQUENCE,
    }
    return mapping.get(method, ShotType.HERO)


def default_specs(plan: EducationalPlan) -> list[SceneSpec]:
    """A generic 5-scene arc driven by the plan's visual methods."""
    methods = plan.visualization_priority
    return [
        SceneSpec(
            goal=VisualGoal.INTRODUCE_CONCEPT,
            shot_type=ShotType.HERO,
            entity="the part",
            scene_importance=4,
        ),
        SceneSpec(
            goal=VisualGoal.REVEAL_INTERNAL_GEOMETRY,
            shot_type=_shot_for_method(methods[0].value),
            visualization=EngineeringVisualizationType.CROSS_SECTION,
            visualization_tokens=("cutaway cross-section view",),
            entity="the part",
        ),
        SceneSpec(
            goal=VisualGoal.EXPLAIN_PROCESS,
            shot_type=_shot_for_method(methods[1].value),
            entity="the part",
        ),
        SceneSpec(
            goal=VisualGoal.COMPARE,
            shot_type=_shot_for_method(methods[2].value),
            entity="the part",
        ),
        SceneSpec(
            goal=VisualGoal.SUMMARIZE,
            shot_type=ShotType.HERO,
            entity="the part",
            scene_importance=5,
            thumbnail_candidate=True,
        ),
    ]