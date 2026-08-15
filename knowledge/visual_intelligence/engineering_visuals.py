"""Engineering visualization selection: overlays that teach the physics.

For goals that explain a mechanism, force, or material behavior, a plain shot
is not enough: the scene needs a visualization overlay. Selection is a
deterministic table from VisualGoal to EngineeringVisualizationType, and each
visualization carries fixed prompt tokens the compiler can phrase without
inventing engineering content.
"""

from __future__ import annotations

from knowledge.visual_architecture import EngineeringDomain
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualization,
    EngineeringVisualizationType,
    ShotType,
)
from knowledge.visual_intelligence.visual_goal import VisualGoal

_AM_DOMAINS = frozenset(
    {EngineeringDomain.FDM, EngineeringDomain.RESIN_AM, EngineeringDomain.INDUSTRIAL_AM}
)

_VISUALIZATION_TOKENS: dict[EngineeringVisualizationType, tuple[str, ...]] = {
    EngineeringVisualizationType.CROSS_SECTION: (
        "clean planar cross-section cut",
        "internal structure exposed",
    ),
    EngineeringVisualizationType.EXPLODED_ASSEMBLY: (
        "exploded assembly view",
        "parts separated along one axis",
    ),
    EngineeringVisualizationType.TRANSPARENT_HOUSING: (
        "semi-transparent housing revealing internal parts",
    ),
    EngineeringVisualizationType.WIREFRAME_OVERLAY: (
        "translucent wireframe overlay on the part",
    ),
    EngineeringVisualizationType.STRESS_DIRECTION: (
        "stress direction arrows over the geometry",
        "color-coded stress visualization",
    ),
    EngineeringVisualizationType.HEAT_MAP: (
        "thermal heat map gradient over the part",
        "blue to red temperature scale",
    ),
    EngineeringVisualizationType.FORCE_ARROWS: (
        "white force arrows showing load paths",
        "compression and tension arrows",
    ),
    EngineeringVisualizationType.TOLERANCE_OVERLAY: (
        "dimension callouts with tolerance labels",
    ),
    EngineeringVisualizationType.DIMENSION_OVERLAY: (
        "dimension arrows and measurement labels",
    ),
    EngineeringVisualizationType.MATERIAL_CALLOUTS: (
        "material callout labels with arrows",
    ),
    EngineeringVisualizationType.MANUFACTURING_STEPS: (
        "numbered manufacturing step diagram",
    ),
    EngineeringVisualizationType.LAYER_PRINT: (
        "layer-by-layer build animation style",
        "stacked layer lines",
    ),
}

_GOAL_VISUALIZATIONS: dict[VisualGoal, EngineeringVisualizationType | None] = {
    VisualGoal.REVEAL_INTERNAL_GEOMETRY: EngineeringVisualizationType.CROSS_SECTION,
    VisualGoal.EXPLAIN_FORCE_FLOW: EngineeringVisualizationType.FORCE_ARROWS,
    VisualGoal.EXPLAIN_HEAT_FLOW: EngineeringVisualizationType.HEAT_MAP,
    VisualGoal.EXPLAIN_ASSEMBLY: EngineeringVisualizationType.EXPLODED_ASSEMBLY,
    VisualGoal.EXPLAIN_MANUFACTURING: EngineeringVisualizationType.MANUFACTURING_STEPS,
    VisualGoal.EXPLAIN_PROCESS: EngineeringVisualizationType.LAYER_PRINT,
    VisualGoal.EXPLAIN_SCALE: EngineeringVisualizationType.DIMENSION_OVERLAY,
    VisualGoal.EXPLAIN_OPTIMIZATION: EngineeringVisualizationType.WIREFRAME_OVERLAY,
    VisualGoal.EXPLAIN_MATERIAL_PROPERTIES: EngineeringVisualizationType.MATERIAL_CALLOUTS,
    VisualGoal.EXPLAIN_FAILURE: EngineeringVisualizationType.STRESS_DIRECTION,
    VisualGoal.EXPLAIN_MECHANISM: None,
    VisualGoal.EXPLAIN_MOTION: None,
    VisualGoal.COMPARE: None,
    VisualGoal.HIGHLIGHT_DIFFERENCE: None,
    VisualGoal.INTRODUCE_CONCEPT: None,
    VisualGoal.SUMMARIZE: None,
}


def select_engineering_visualizations(
    goal: VisualGoal,
    shot: ShotType,
    *,
    domain: EngineeringDomain,
) -> list[EngineeringVisualization]:
    """Choose the engineering visualizations for a scene, deterministically.

    Goals that only describe a shot (compare, summarize, motion) get none.
    Process goals get a layer-by-layer print only for additive manufacturing
    domains, where that visualization is accurate.
    """
    target = _GOAL_VISUALIZATIONS[goal]
    if target is None:
        return []

    if (
        goal is VisualGoal.REVEAL_INTERNAL_GEOMETRY
        and shot is ShotType.TRANSPARENT
    ):
        target = EngineeringVisualizationType.TRANSPARENT_HOUSING
    if goal is VisualGoal.EXPLAIN_PROCESS and domain not in _AM_DOMAINS:
        return []

    return [
        EngineeringVisualization(
            type=target,
            elements=list(_VISUALIZATION_TOKENS[target]),
            prompt_tokens=list(_VISUALIZATION_TOKENS[target]),
            rationale=f"goal '{goal.value}' maps to {target.value} visualization",
        )
    ]