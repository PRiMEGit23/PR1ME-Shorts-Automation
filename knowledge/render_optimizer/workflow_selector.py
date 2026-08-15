"""Workflow selector: pick a ComfyUI render profile from the scene intent.

Deterministic mapping from the storyboard's engineering visualization and
shot type to a RenderProfileKey. Falls back to HERO when nothing special
applies, so every scene has a profile.

The optimizer also uses this: when a rule prescribes a visualization switch
(e.g. engineering accuracy low -> cutaway), it asks the selector which
workflow profile the new visualization implies.
"""

from __future__ import annotations

from knowledge.render_optimizer.render_profiles import RenderProfileKey
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualizationType,
    ShotType,
)

#: Engineering visualization -> workflow profile.
VISUALIZATION_PROFILES: dict[EngineeringVisualizationType, RenderProfileKey] = {
    EngineeringVisualizationType.CROSS_SECTION: RenderProfileKey.CUTAWAY,
    EngineeringVisualizationType.EXPLODED_ASSEMBLY: RenderProfileKey.EXPLODED,
    EngineeringVisualizationType.TRANSPARENT_HOUSING: RenderProfileKey.TRANSPARENT,
    EngineeringVisualizationType.WIREFRAME_OVERLAY: RenderProfileKey.CAD,
    EngineeringVisualizationType.STRESS_DIRECTION: RenderProfileKey.STRESS_VISUALIZATION,
    EngineeringVisualizationType.HEAT_MAP: RenderProfileKey.THERMAL_VISUALIZATION,
    EngineeringVisualizationType.FORCE_ARROWS: RenderProfileKey.STRESS_VISUALIZATION,
    EngineeringVisualizationType.TOLERANCE_OVERLAY: RenderProfileKey.CAD,
    EngineeringVisualizationType.DIMENSION_OVERLAY: RenderProfileKey.BLUEPRINT,
    EngineeringVisualizationType.MATERIAL_CALLOUTS: RenderProfileKey.DIAGRAM,
    EngineeringVisualizationType.MANUFACTURING_STEPS: RenderProfileKey.DIAGRAM,
    EngineeringVisualizationType.LAYER_PRINT: RenderProfileKey.DIAGRAM,
}

#: Shot type -> workflow profile.
SHOT_PROFILES: dict[ShotType, RenderProfileKey] = {
    ShotType.MACRO: RenderProfileKey.MACRO,
    ShotType.EXTREME_MACRO: RenderProfileKey.MACRO,
    ShotType.HERO: RenderProfileKey.HERO,
    ShotType.CROSS_SECTION: RenderProfileKey.CUTAWAY,
    ShotType.CUTAWAY: RenderProfileKey.CUTAWAY,
    ShotType.TRANSPARENT: RenderProfileKey.TRANSPARENT,
    ShotType.EXPLODED_VIEW: RenderProfileKey.EXPLODED,
    ShotType.ISOMETRIC: RenderProfileKey.CAD,
    ShotType.ORTHOGRAPHIC: RenderProfileKey.CAD,
    ShotType.BLUEPRINT: RenderProfileKey.BLUEPRINT,
    ShotType.CAD_RENDER: RenderProfileKey.CAD,
    ShotType.MICROSCOPE: RenderProfileKey.MACRO,
    ShotType.SLOW_MOTION: RenderProfileKey.HERO,
    ShotType.TIME_LAPSE: RenderProfileKey.HERO,
    ShotType.PROCESS_SEQUENCE: RenderProfileKey.DIAGRAM,
    ShotType.BEFORE_AFTER: RenderProfileKey.COMPARISON,
    ShotType.COMPARISON_SPLIT: RenderProfileKey.COMPARISON,
    ShotType.XRAY: RenderProfileKey.TRANSPARENT,
    ShotType.WIREFRAME_OVERLAY: RenderProfileKey.CAD,
    ShotType.ANNOTATED_DIAGRAM: RenderProfileKey.DIAGRAM,
    ShotType.MANUFACTURING_SEQUENCE: RenderProfileKey.DIAGRAM,
}

_DEFAULT_PROFILE = RenderProfileKey.HERO


def select_workflow_profile(
    visualization_type: EngineeringVisualizationType | None = None,
    shot_type: ShotType | None = None,
) -> tuple[RenderProfileKey, str]:
    """Pick a profile, preferring the engineering visualization.

    Returns (profile_key, reason) so the caller can explain the choice.
    Visualization wins over shot type because the workflow must support the
    overlay, not just the framing.
    """
    if visualization_type is not None:
        profile = VISUALIZATION_PROFILES.get(visualization_type)
        if profile is not None:
            return profile, f"engineering visualization {visualization_type.value!r}"
    if shot_type is not None:
        profile = SHOT_PROFILES.get(shot_type)
        if profile is not None:
            return profile, f"shot type {shot_type.value!r}"
    return _DEFAULT_PROFILE, f"no matching profile, default {_DEFAULT_PROFILE.value!r}"