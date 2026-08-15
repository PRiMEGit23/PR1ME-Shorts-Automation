"""Composition planning: deterministic framing decisions per shot archetype.

Row shots align options side by side, diagram shots center the geometry, and
photographic shots follow the hierarchy: a leading subject with a secondary
sits left- or right-heavy, a lone subject gets the rule of thirds. Negative
space defers to the spec's explicit overlay declaration, then falls back to an
overlay-friendly top slot for annotation-heavy shots.
"""

from __future__ import annotations

from knowledge.visual_architecture import CompositionRule, NegativeSpace, Scene
from knowledge.visual_intelligence.shot_selector import is_row_shot
from knowledge.visual_intelligence.storyboard import CompositionPlan, ShotType

_OVERLAY_SHOTS = frozenset(
    {
        ShotType.ANNOTATED_DIAGRAM,
        ShotType.BLUEPRINT,
        ShotType.ORTHOGRAPHIC,
        ShotType.XRAY,
        ShotType.WIREFRAME_OVERLAY,
        ShotType.PROCESS_SEQUENCE,
        ShotType.MANUFACTURING_SEQUENCE,
        ShotType.COMPARISON_SPLIT,
        ShotType.BEFORE_AFTER,
    }
)

_CENTERED_SHOTS = frozenset(
    {
        ShotType.MACRO,
        ShotType.EXTREME_MACRO,
        ShotType.MICROSCOPE,
        ShotType.CROSS_SECTION,
        ShotType.CUTAWAY,
        ShotType.TRANSPARENT,
        ShotType.EXPLODED_VIEW,
        ShotType.ISOMETRIC,
        ShotType.ORTHOGRAPHIC,
        ShotType.BLUEPRINT,
        ShotType.CAD_RENDER,
        ShotType.XRAY,
        ShotType.WIREFRAME_OVERLAY,
        ShotType.ANNOTATED_DIAGRAM,
    }
)


def plan_composition(shot: ShotType, scene: Scene) -> CompositionPlan:
    """Choose the composition plan for one scene, deterministically."""
    hierarchy = scene.subject_hierarchy
    emphasis = scene.visual_focus or hierarchy.focus_object

    if is_row_shot(shot):
        rule = CompositionRule.CENTER_ROW
    elif shot in _CENTERED_SHOTS:
        rule = CompositionRule.CENTERED
    elif scene.secondary_subjects:
        rule = (
            CompositionRule.LEFT_HEAVY
            if hierarchy.focus_object == hierarchy.primary
            else CompositionRule.RIGHT_HEAVY
        )
    else:
        rule = CompositionRule.RULE_OF_THIRDS

    if scene.composition.negative_space != NegativeSpace.NONE:
        negative_space = scene.composition.negative_space
    elif shot in _OVERLAY_SHOTS:
        negative_space = NegativeSpace.OVERLAY_TOP
    else:
        negative_space = NegativeSpace.NONE

    return CompositionPlan(
        rule=rule,
        emphasis=emphasis,
        negative_space=negative_space,
        note=f"composition derived for {shot.value}",
    )