"""Lighting planning: deterministic lighting decisions per shot archetype.

Diagram-like shots get flat studio key light. Photographic shots get a
cinematic setup per archetype, then a material refinement: metals take a hard
key (with rim on hero shots), plastics take a softbox. The refinement never
touches diagram lighting, where shadows and texture are rejected anyway.
"""

from __future__ import annotations

from knowledge.visual_architecture import (
    LightDirection,
    LightingStyle,
    Material,
    Scene,
)
from knowledge.visual_intelligence.shot_selector import is_diagram_like
from knowledge.visual_intelligence.storyboard import LightingPlan, ShotType

_METALS = frozenset(
    {
        Material.STAINLESS_STEEL,
        Material.ALUMINIUM,
        Material.STEEL,
        Material.BRASS,
        Material.COPPER,
        Material.TITANIUM,
    }
)
_PLASTICS = frozenset(
    {
        Material.PLA,
        Material.ABS,
        Material.PETG,
        Material.NYLON,
        Material.TPU,
        Material.POLYCARBONATE,
        Material.PEEK,
        Material.RESIN,
    }
)

_DIAGRAM_LIGHT = LightingPlan(
    direction=LightDirection.KEY,
    style=LightingStyle.STUDIO,
    key_color="neutral",
    note="flat diagram light, no photographic shadows",
)

_MACRO_LIGHT = LightingPlan(
    direction=LightDirection.SIDE,
    style=LightingStyle.RAKING,
    practical_sources=["bench lamp"],
    key_color="neutral",
    note="raking side light rakes surface texture",
)

_HERO_LIGHT = LightingPlan(
    direction=LightDirection.RIM,
    style=LightingStyle.STUDIO,
    practical_sources=["bench lamp"],
    key_color="neutral",
    note="studio key with rim separates the subject from the lab",
)

_SHOT_LIGHT_TABLE: dict[ShotType, LightingPlan] = {
    ShotType.MACRO: _MACRO_LIGHT,
    ShotType.EXTREME_MACRO: _MACRO_LIGHT,
    ShotType.MICROSCOPE: _MACRO_LIGHT,
    ShotType.HERO: _HERO_LIGHT,
    ShotType.CROSS_SECTION: _DIAGRAM_LIGHT,
    ShotType.CUTAWAY: _MACRO_LIGHT,
    ShotType.TRANSPARENT: LightingPlan(
        direction=LightDirection.BACK,
        style=LightingStyle.STUDIO,
        key_color="neutral",
        note="backlight makes the transparent shell glow evenly",
    ),
    ShotType.EXPLODED_VIEW: _DIAGRAM_LIGHT,
    ShotType.ISOMETRIC: _DIAGRAM_LIGHT,
    ShotType.ORTHOGRAPHIC: _DIAGRAM_LIGHT,
    ShotType.BLUEPRINT: _DIAGRAM_LIGHT,
    ShotType.CAD_RENDER: _DIAGRAM_LIGHT,
    ShotType.XRAY: _DIAGRAM_LIGHT,
    ShotType.WIREFRAME_OVERLAY: _DIAGRAM_LIGHT,
    ShotType.ANNOTATED_DIAGRAM: _DIAGRAM_LIGHT,
    ShotType.PROCESS_SEQUENCE: _DIAGRAM_LIGHT,
    ShotType.MANUFACTURING_SEQUENCE: _DIAGRAM_LIGHT,
    ShotType.SLOW_MOTION: LightingPlan(
        direction=LightDirection.SIDE,
        style=LightingStyle.SOFTBOX,
        key_color="neutral",
        note="soft side light keeps fast motion readable",
    ),
    ShotType.TIME_LAPSE: LightingPlan(
        direction=LightDirection.MIXED,
        style=LightingStyle.GRADIENT,
        key_color="cool",
        note="gradient light reads the passage of time",
    ),
    ShotType.BEFORE_AFTER: _DIAGRAM_LIGHT,
    ShotType.COMPARISON_SPLIT: _DIAGRAM_LIGHT,
}


def plan_lighting(shot: ShotType, scene: Scene) -> LightingPlan:
    """Choose the lighting plan for one scene, deterministically."""
    plan = _SHOT_LIGHT_TABLE[shot]
    if is_diagram_like(shot):
        return plan

    materials = {m for m in scene.primary_subject.materials}
    if materials & _METALS:
        if shot is ShotType.HERO:
            return plan.model_copy(
                update={"style": LightingStyle.HARD_KEY, "direction": LightDirection.RIM,
                        "note": "hard key with rim reads machined metal edges"}
            )
        return plan.model_copy(
            update={"style": LightingStyle.HARD_KEY, "direction": LightDirection.KEY,
                    "note": "hard key light reads machined metal surfaces"}
        )
    if materials & _PLASTICS and plan.style not in (LightingStyle.STUDIO,):
        return plan.model_copy(
            update={"style": LightingStyle.SOFTBOX,
                    "note": "softbox diffuses across smooth plastic surfaces"}
        )
    return plan