"""Render profile selector: the workflow genre for a scene (Phase 10).

The bridge between the Model Director and the render profiles. The genre
selection is *not* duplicated: the canonical mapping from engineering
visualization / shot type to RenderProfileKey is owned by
``knowledge.render_optimizer.select_workflow_profile`` and is reused
verbatim. This module only interprets the result for the Model Director
and applies the quality-target adjustments (steps multiplier, upscaler,
refiner).
"""

from __future__ import annotations

from knowledge.model_director.backend_rules import QUALITY_TARGETS, QualityTarget
from knowledge.model_director.model_registry import REGISTRY
from knowledge.render_optimizer.render_profiles import RenderProfileKey
from knowledge.render_optimizer.workflow_selector import select_workflow_profile
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualizationType,
    ShotType,
)


def select_render_profile(
    shot_type: ShotType | None,
    visualization_type: EngineeringVisualizationType | None = None,
) -> tuple[RenderProfileKey, str]:
    """The workflow genre for a scene (same mapping the optimizer uses)."""
    return select_workflow_profile(
        visualization_type=visualization_type,
        shot_type=shot_type,
    )


def quality_target_for(
    *,
    is_hero: bool,
    is_thumbnail: bool,
    importance: int,
    visual_budget: int,
    quality_target: QualityTarget | None = None,
) -> tuple[QualityTarget, str]:
    """The deterministic quality tier for a scene.

    Hero / thumbnail scenes and high-budget scenes get the premium tier;
    low-budget scenes get the fast tier; everything else is balanced. An
    explicit request overrides the rule (and never downgrades a hero).
    """
    if quality_target is not None:
        return quality_target, f"explicit {quality_target.value!r} target"
    if is_hero or is_thumbnail:
        return QualityTarget.PREMIUM, "hero/thumbnail scene earns the premium tier"
    if importance >= 4:
        return QualityTarget.PREMIUM, "high importance earns the premium tier"
    if visual_budget <= 4:
        return QualityTarget.FAST, "low visual budget earns the fast tier"
    return QualityTarget.BALANCED, "balanced tier by default"


def target_settings(
    target: QualityTarget, model_key: str
) -> tuple[float, str, str]:
    """(steps multiplier, upscaler, refiner) for a target.

    The upscaler / refiner are clamped into the model's supported sets so
    a target never prescribes something the backend cannot run.
    """
    settings = QUALITY_TARGETS[target]
    spec = REGISTRY.get(model_key)
    upscaler = settings["upscaler"]
    if upscaler != "none" and upscaler not in spec.supported_upscalers:
        upscaler = next((u for u in spec.supported_upscalers if u != "none"), "none")
    refiner = settings["refiner"]
    if refiner != "none" and refiner not in spec.supported_refiners:
        refiner = "none"
    return float(settings["steps_multiplier"]), upscaler, refiner
