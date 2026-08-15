"""Stage 6: Consistency Engine.

Pins the cross-shot consistency baseline every generated image must honor:
object identity (with canonical descriptors and aliases), materials, lighting
direction, palette, perspective convention, environment, scale anchor, camera
language, and per-shot anchor notes.

The engine is deterministic by design: it freezes the decisions made by the
upstream stages into one auditable baseline, so no scene can drift into an
unrelated look. The Prompt Composer injects these anchors into every positive
and negative prompt (e.g. ``consistent lighting``, ``same color palette``,
``no color changes``).
"""

from __future__ import annotations

from collections import Counter

from pr1me.visual_architecture._common import VisualContext, make_logger
from pr1me.visual_architecture.contracts import (
    CanonicalObject,
    ConsistencyOutput,
    KnowledgeOutput,
    ScenePlanOutput,
    Shot,
    ShotConsistencyNote,
    ShotPlanOutput,
    VisualizationStrategyOutput,
    VisualStyleOutput,
)

__all__ = ["ConsistencyEngine", "build_baseline"]

#: Maximum number of objects pinned into the registry (framing constraint).
_MAX_REGISTRY_OBJECTS = 8

#: Perspective conventions per strategy style.
_PERSPECTIVE = {
    "cross_section": "consistent section plane across all mechanism views",
    "exploded_cad": "consistent isometric assembly angle across all views",
    "blueprint": "consistent orthographic projection planes",
    "technical_illustration": "consistent isometric projection",
    "simulation": "consistent model orientation for every simulation frame",
}

#: Continuity anchor phrases emitted verbatim into prompts.
_ANCHOR_PHRASES = (
    "consistent lighting direction across all shots",
    "identical color palette in every frame",
    "same environment and set dressing in every shot",
    "consistent subject scale and proportions",
    "no sudden material, lighting, or palette changes between scenes",
)


class ConsistencyEngine:
    """Stage 6 engine: upstream decisions -> cross-shot consistency baseline."""

    def __init__(self, context: VisualContext) -> None:
        self._context = context
        self._logger = make_logger("consistency_engine")

    async def run(
        self,
        *,
        knowledge: KnowledgeOutput,
        scene_plan: ScenePlanOutput,
        shot_plan: ShotPlanOutput,
        visual_style: VisualStyleOutput,
        strategy: VisualizationStrategyOutput,
    ) -> ConsistencyOutput:
        """Build the baseline from every upstream stage's decisions."""
        self._logger.info(
            "event=consistency_engine.started",
            n_objects=len(knowledge.objects),
            n_shots=len(shot_plan.shots),
        )
        baseline = build_baseline(
            knowledge=knowledge,
            scene_plan=scene_plan,
            shot_plan=shot_plan,
            visual_style=visual_style,
            strategy=strategy,
        )
        self._logger.info(
            "event=consistency_engine.completed",
            n_anchors=len(baseline.continuity_anchors),
            n_notes=len(baseline.shot_notes),
        )
        return baseline


def build_baseline(
    *,
    knowledge: KnowledgeOutput,
    scene_plan: ScenePlanOutput,
    shot_plan: ShotPlanOutput,
    visual_style: VisualStyleOutput,
    strategy: VisualizationStrategyOutput,
) -> ConsistencyOutput:
    """Deterministic baseline assembly from the upstream contracts."""
    materials = list(knowledge.materials) or ["anodized aluminum", "matte polymer"]
    registry = _object_registry(knowledge, materials)
    environment = _dominant_environment(scene_plan)
    camera_language = _camera_language(shot_plan)
    perspective = _PERSPECTIVE.get(
        strategy.style.value,
        "consistent documentary camera height and angle conventions",
    )

    anchors = list(_ANCHOR_PHRASES)
    anchors.append(f"scale reference: the {knowledge.scale.reference_object}")
    anchors.append(f"camera language: {camera_language}")
    anchors.append(f"perspective: {perspective}")

    lens_language = _lens_language(shot_plan)
    object_appearance = _object_appearance(knowledge, materials)
    anchors.append(f"lens language: {lens_language}")
    anchors.append(f"object appearance: {object_appearance}")

    notes = [
        ShotConsistencyNote(
            shot_id=shot.id,
            anchors=[
                f"subject identity: {_descriptor(shot, registry)}",
                f"environment: {environment}",
                f"palette: {_palette_pin(visual_style)}",
                f"lighting: {_lighting_pin(visual_style)}",
            ],
        )
        for shot in shot_plan.shots
    ]

    return ConsistencyOutput(
        object_registry=registry,
        materials=materials,
        lighting_direction=_lighting_pin(visual_style),
        palette=[color for color in visual_style.color_palette],
        perspective_convention=perspective,
        environment=environment,
        scale_anchor=f"{knowledge.scale.reference_object} ({knowledge.scale.description})",
        camera_language=camera_language,
        lens_language=lens_language,
        object_appearance=object_appearance,
        continuity_anchors=anchors,
        shot_notes=notes,
    )


# ---------------------------------------------------------------- internals --


def _object_registry(knowledge: KnowledgeOutput, materials: list[str]) -> list[CanonicalObject]:
    material = next(iter(materials), "")
    registry: list[CanonicalObject] = []
    for name in knowledge.objects[:_MAX_REGISTRY_OBJECTS]:
        descriptor = f"{name} in {material}" if material else name
        registry.append(
            CanonicalObject(
                name=name,
                canonical_descriptor=descriptor,
                aliases=[name],
                persistent=True,
            )
        )
    if not registry:
        registry.append(
            CanonicalObject(
                name=knowledge.scale.reference_object,
                canonical_descriptor=knowledge.scale.reference_object,
                aliases=[knowledge.scale.reference_object],
                persistent=True,
            )
        )
    return registry


def _dominant_environment(scene_plan: ScenePlanOutput) -> str:
    if not scene_plan.scenes:
        return "clean engineering environment"
    counts = Counter(scene.environment for scene in scene_plan.scenes)
    return counts.most_common(1)[0][0]


def _camera_language(shot_plan: ShotPlanOutput) -> str:
    if not shot_plan.shots:
        return "documentary engineering camera language"
    lenses = Counter(shot.lens for shot in shot_plan.shots)
    lens = lenses.most_common(1)[0][0]
    movements = Counter(shot.camera_movement for shot in shot_plan.shots)
    movement = movements.most_common(1)[0][0]
    return f"{movement} framing with {lens}; macro for details, static for mechanisms"


def _lens_language(shot_plan: ShotPlanOutput) -> str:
    """Freeze one lens family for the whole film (shot continuity)."""
    if not shot_plan.shots:
        return "one fixed lens family across the whole film"
    family = [shot.lens for shot in shot_plan.shots if shot.lens]
    family = list(dict.fromkeys(family))
    if not family:
        return "one fixed lens family across the whole film"
    return f"one fixed lens family ({', '.join(family)}) across the whole film"


def _object_appearance(knowledge: KnowledgeOutput, materials: list[str]) -> str:
    """Freeze one appearance per subject so the film reads as one shoot."""
    material = next(iter(materials), "")
    names = knowledge.objects or [knowledge.scale.reference_object]
    label = names[0] if names else "the subject"
    finish = f" in {material}" if material else ""
    return f"{label} keeps one identical appearance{finish} with the same finish and color in every shot"


def _descriptor(shot: Shot, registry: list[CanonicalObject]) -> str:
    """Reference the shot's scene objects through the registry when possible."""
    target = next(iter(registry), None)
    if target is None:
        return shot.focus
    return target.canonical_descriptor


def _palette_pin(visual_style: VisualStyleOutput) -> str:
    if not visual_style.color_palette:
        return "channel palette"
    hexes = ",".join(color.hex for color in visual_style.color_palette[:4])
    return f"fixed palette {hexes}"


def _lighting_pin(visual_style: VisualStyleOutput) -> str:
    return visual_style.lighting
