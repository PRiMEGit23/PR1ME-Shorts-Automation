"""Render profiles: the ComfyUI workflow profiles the optimizer may select.

A profile is a deterministic, model-agnostic description of how a ComfyUI
workflow is configured for one visualization genre (macro, diagram, CAD,
blueprint, exploded, cutaway, transparent, stress). In this phase the
profiles are data only: the workflow builder (Phase 1) consumes them, and
the optimizer's workflow_selector picks them by visualization type. Nothing
here executes ComfyUI.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RenderProfileKey(StrEnum):
    """The selectable ComfyUI workflow profiles."""

    MACRO = "macro"
    DIAGRAM = "diagram"
    CAD = "cad"
    BLUEPRINT = "blueprint"
    EXPLODED = "exploded"
    CUTAWAY = "cutaway"
    TRANSPARENT = "transparent"
    STRESS_VISUALIZATION = "stress visualization"
    THERMAL_VISUALIZATION = "thermal visualization"
    COMPARISON = "comparison"
    HERO = "hero"


class RenderProfile(BaseModel):
    """One deterministic ComfyUI workflow profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: RenderProfileKey
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=400)
    sampler: str = Field(min_length=1, max_length=40)
    steps: int = Field(ge=1, le=80)
    cfg: float = Field(ge=1.0, le=15.0)
    resolution: str = Field(min_length=1, max_length=40)
    negative_tokens: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    loras: tuple[str, ...] = Field(default_factory=tuple, max_length=4)
    node_notes: dict[str, str] = Field(default_factory=dict, max_length=8)


_MACRO_NEGATIVES = ("text", "words", "hands", "duplicate subject")
_DIAGRAM_NEGATIVES = ("photo", "photorealistic", "3d render", "text watermark")
_CAD_NEGATIVES = ("photo", "film grain", "rough surface", "text watermark")
_BLUEPRINT_NEGATIVES = ("photo", "color", "shading", "text watermark")
_EXPLODED_NEGATIVES = ("photo", "fog", "text watermark", "cluttered")
_CUTAWAY_NEGATIVES = ("photo", "text watermark", "fog")
_TRANSPARENT_NEGATIVES = ("photo", "opaque shell", "text watermark", "fog")
_STRESS_NEGATIVES = ("photo", "text watermark", "fog", "dull colors")
_THERMAL_NEGATIVES = ("photo", "text watermark", "realistic skin", "dull colors")
_COMPARISON_NEGATIVES = ("photo", "text watermark", "cluttered")
_HERO_NEGATIVES = ("text", "words", "low quality", "blurry")


RENDER_PROFILES: dict[RenderProfileKey, RenderProfile] = {
    RenderProfileKey.MACRO: RenderProfile(
        key=RenderProfileKey.MACRO,
        name="Macro inspection",
        description=(
            "Shallow depth of field, 100mm macro lens, tight framing for "
            "surface-level inspection of small features."
        ),
        sampler="dpmpp_2m",
        steps=30,
        cfg=7.0,
        resolution="832x1216",
        negative_tokens=_MACRO_NEGATIVES,
        loras=("macro-detail",),
        node_notes={
            "sampler": "dpmpp_2m / karras",
            "lora": "macro-detail",
            "dof": "shallow",
        },
    ),
    RenderProfileKey.DIAGRAM: RenderProfile(
        key=RenderProfileKey.DIAGRAM,
        name="Technical diagram",
        description=(
            "Flat 2D technical diagram style: clean lines, callouts, labels, "
            "no photorealism."
        ),
        sampler="dpmpp_2m",
        steps=28,
        cfg=7.5,
        resolution="832x1216",
        negative_tokens=_DIAGRAM_NEGATIVES,
        node_notes={"style": "technical diagram", "labels": "annotations"},
    ),
    RenderProfileKey.CAD: RenderProfile(
        key=RenderProfileKey.CAD,
        name="CAD render",
        description=(
            "Clean CAD surface render: matte studio lighting, exact geometry, "
            "neutral gray studio floor."
        ),
        sampler="dpmpp_2m",
        steps=32,
        cfg=6.5,
        resolution="832x1216",
        negative_tokens=_CAD_NEGATIVES,
        loras=("cad-sharp",),
        node_notes={"style": "CAD render", "lighting": "studio"},
    ),
    RenderProfileKey.BLUEPRINT: RenderProfile(
        key=RenderProfileKey.BLUEPRINT,
        name="Blueprint drawing",
        description=(
            "Blueprint aesthetic: white lines on blue, dimension overlays, "
            "orthographic framing."
        ),
        sampler="euler_a",
        steps=26,
        cfg=7.0,
        resolution="832x1216",
        negative_tokens=_BLUEPRINT_NEGATIVES,
        node_notes={"style": "blueprint", "overlay": "dimension lines"},
    ),
    RenderProfileKey.EXPLODED: RenderProfile(
        key=RenderProfileKey.EXPLODED,
        name="Exploded assembly view",
        description=(
            "Exploded view with parts separated along assembly axes, aligned "
            "ghost lines, labeled callouts."
        ),
        sampler="dpmpp_2m",
        steps=30,
        cfg=7.0,
        resolution="832x1216",
        negative_tokens=_EXPLODED_NEGATIVES,
        node_notes={"style": "exploded view", "ghost_lines": "on"},
    ),
    RenderProfileKey.CUTAWAY: RenderProfile(
        key=RenderProfileKey.CUTAWAY,
        name="Cutaway section view",
        description=(
            "Cutaway section through the part: crisp interior surfaces, "
            "section hatch, visible internal geometry."
        ),
        sampler="dpmpp_2m",
        steps=30,
        cfg=7.0,
        resolution="832x1216",
        negative_tokens=_CUTAWAY_NEGATIVES,
        node_notes={"style": "cutaway", "section_hatch": "on"},
    ),
    RenderProfileKey.TRANSPARENT: RenderProfile(
        key=RenderProfileKey.TRANSPARENT,
        name="Transparent housing view",
        description=(
            "Semi-transparent outer shell revealing internal parts in place, "
            "soft studio light, subtle glass shading."
        ),
        sampler="dpmpp_2m",
        steps=32,
        cfg=6.5,
        resolution="832x1216",
        negative_tokens=_TRANSPARENT_NEGATIVES,
        node_notes={"shell": "transparent glass", "lighting": "soft studio"},
    ),
    RenderProfileKey.STRESS_VISUALIZATION: RenderProfile(
        key=RenderProfileKey.STRESS_VISUALIZATION,
        name="Stress visualization",
        description=(
            "FEA-style stress map: colored gradient overlay on the geometry, "
            "force arrows, legend callout."
        ),
        sampler="dpmpp_2m",
        steps=28,
        cfg=7.5,
        resolution="832x1216",
        negative_tokens=_STRESS_NEGATIVES,
        node_notes={"style": "FEA heat map", "arrows": "force direction"},
    ),
    RenderProfileKey.THERMAL_VISUALIZATION: RenderProfile(
        key=RenderProfileKey.THERMAL_VISUALIZATION,
        name="Thermal visualization",
        description=(
            "Thermal camera look: temperature gradient colors over the part, "
            "heat flow arrows, temperature scale callout."
        ),
        sampler="dpmpp_2m",
        steps=28,
        cfg=7.5,
        resolution="832x1216",
        negative_tokens=_THERMAL_NEGATIVES,
        node_notes={"style": "thermal map", "scale": "temperature legend"},
    ),
    RenderProfileKey.COMPARISON: RenderProfile(
        key=RenderProfileKey.COMPARISON,
        name="Comparison board",
        description=(
            "Split comparison layout: side-by-side panels on a clean board, "
            "label bars, consistent camera across panels."
        ),
        sampler="dpmpp_2m",
        steps=30,
        cfg=7.0,
        resolution="832x1216",
        negative_tokens=_COMPARISON_NEGATIVES,
        node_notes={"layout": "split panels", "labels": "on"},
    ),
    RenderProfileKey.HERO: RenderProfile(
        key=RenderProfileKey.HERO,
        name="Hero product shot",
        description=(
            "High-impact hero shot: dramatic key light, clean backdrop, "
            "strong contrast for thumbnails."
        ),
        sampler="dpmpp_2m",
        steps=32,
        cfg=7.5,
        resolution="832x1216",
        negative_tokens=_HERO_NEGATIVES,
        loras=("hero-contrast",),
        node_notes={"lighting": "dramatic key", "contrast": "high"},
    ),
}


def profile_for(key: RenderProfileKey) -> RenderProfile:
    """Fetch a profile, failing loudly on unknown keys."""
    try:
        return RENDER_PROFILES[key]
    except KeyError as exc:
        name = key.value if isinstance(key, RenderProfileKey) else key
        raise KeyError(f"no render profile for {name!r}") from exc