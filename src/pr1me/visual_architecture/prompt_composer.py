"""Stage 7: Prompt Composer.

Generates production-grade, ComfyUI-ready prompts: one per shot, built from the
structured decisions of every upstream stage. The positive prompt follows the
channel's fixed token order — subject, engineering detail, materials, surface
detail, environment, composition, camera, lighting, focus, depth, physics,
scale, atmosphere, rendering style, storytelling, quality — and every sentence
must carry engineering information. No prompt stuffing: empty fields are filled
with concrete defaults, never decorative filler.

The composer is deterministic and repair-aware: the validator's issues are
mapped back onto the structured fields (``repairs``), so regeneration is a
targeted fix, not a blind retry. Repairing a field replaces its value with the
canonical default, which is guaranteed to satisfy the validator's rubric.
"""

from __future__ import annotations

from collections.abc import Mapping

from pr1me.models.contracts.visual import ScriptBlockName
from pr1me.visual_architecture._common import VisualContext, make_logger
from pr1me.visual_architecture.contracts import (
    ComposedPrompt,
    ConsistencyOutput,
    KnowledgeOutput,
    PromptCompositionOutput,
    PromptFields,
    Shot,
    ShotPlanOutput,
    VisualizationStrategyOutput,
    VisualStyleOutput,
)

__all__ = ["PromptComposer", "build_negative_prompt", "compose_positive"]

#: Base hygiene negatives (channel default, mirrors prompt 07's library).
_HYGIENE_NEGATIVES = (
    "blurry",
    "low quality",
    "low resolution",
    "noise",
    "watermark",
    "text artifacts",
    "duplicate objects",
    "deformed objects",
    "incorrect geometry",
    "cropped subject",
    "oversaturation",
    "cartoon",
    "anime",
    "unrealistic lighting",
    "extra objects",
)

#: Palette lock so no generated image drifts in color.
_PALETTE_LOCK = "no color changes from the fixed palette"

#: Aspect qualifier appended to every positive prompt.
_ASPECT_QUALIFIER = "vertical 9:16 engineering composition"

#: Quality descriptors applied to regular shots.
_QUALITY_BASE = ("photorealistic industrial photography", "sharp focus", "high dynamic range")

#: Quality descriptors applied to the thumbnail shot.
_QUALITY_THUMBNAIL = ("high contrast", "strong readability at small size")

#: Visual storytelling phrase per narration block.
_STORYTELLING: dict[ScriptBlockName, str] = {
    "hook": "curiosity-driven opening frame",
    "explanation": "the mechanism shown mid-explanation",
    "practical_insight": "the actionable change shown in context",
    "ending": "the resolved memory anchor",
}

#: Default physics phrasing when the narration names none.
_DEFAULT_PHYSICS = "realistic physical behavior with correct proportions"

#: Canonical repair values. A repair replaces the offending field with one of
#: these so the regenerated prompt deterministically satisfies the rubric.
_REPAIR_DEFAULTS: dict[str, str] = {
    "subject": "primary engineering subject",
    "environment": "clean engineering environment",
    "composition": "single focal subject, clear hierarchy, minimal clutter",
    "camera": "documentary angle, static framing, 85mm lens",
    "lighting": "consistent soft key light from upper left",
    "materials": "anodized aluminum, matte polymer",
    "surface_detail": "machined metal surface with precise tolerances",
    "physics": _DEFAULT_PHYSICS,
    "scale": "true physical scale with realistic proportions",
    "atmosphere": "precision manufacturing environment",
    "rendering_style": "photorealistic industrial photography",
    "engineering_detail": "the mechanism shown accurately at its working interface",
    "storytelling": "the engineering explanation advanced by this frame",
}

#: Director-mandated visual treatments -> concrete prompt guidance. The phrase
#: is appended to the engineering detail so the requirement is explicit in the
#: positive prompt and survives into the ComfyUI payload.
_TREATMENT_PHRASES: dict[str, str] = {
    "macro_detail": "extreme macro detail of the working interface, surface texture legible",
    "exploded_view": "exploded view with every part separated along its assembly axis",
    "animation": "the mechanism caught mid-motion, action frozen in a dynamic still",
}

#: Composition addendum for the single climax shot.
_CLIMAX_COMPOSITION = (
    "the visual climax of the film — maximum clarity, the mechanism at full fidelity"
)


class PromptComposer:
    """Stage 7 engine: every upstream decision -> one prompt per shot."""

    def __init__(self, context: VisualContext) -> None:
        self._context = context
        self._logger = make_logger("prompt_composer")

    async def compose_all(
        self,
        *,
        shot_plan: ShotPlanOutput,
        knowledge: KnowledgeOutput,
        strategy: VisualizationStrategyOutput,
        visual_style: VisualStyleOutput,
        consistency: ConsistencyOutput,
        repairs: Mapping[int, list[str]] | None = None,
    ) -> PromptCompositionOutput:
        """Compose every shot prompt, applying ``repairs`` where given."""
        self._logger.info(
            "event=prompt_composer.started",
            n_shots=len(shot_plan.shots),
            n_repairs=len(repairs) if repairs else 0,
        )
        prompts: list[ComposedPrompt] = []
        for shot in shot_plan.shots:
            issues = list(repairs.get(shot.id, [])) if repairs else []
            prompts.append(
                compose_shot(
                    shot=shot,
                    knowledge=knowledge,
                    strategy=strategy,
                    visual_style=visual_style,
                    consistency=consistency,
                    repairs=issues,
                )
            )
        self._logger.info("event=prompt_composer.completed", n_prompts=len(prompts))
        return PromptCompositionOutput(prompts=prompts)


def compose_shot(
    *,
    shot: Shot,
    knowledge: KnowledgeOutput,
    strategy: VisualizationStrategyOutput,
    visual_style: VisualStyleOutput,
    consistency: ConsistencyOutput,
    repairs: list[str] | None = None,
) -> ComposedPrompt:
    """Compose one shot's prompt (pure function, repair-aware)."""
    issues = set(repairs or ())
    thumbnail = shot.is_thumbnail
    subject = _repair_or("subject", issues) or _shot_subject(shot, consistency)
    environment = _repair_or("environment", issues) or consistency.environment
    composition = _repair_or("composition", issues) or _shot_composition(shot, thumbnail)
    camera = _repair_or("camera", issues) or f"{shot.camera_angle}, {shot.camera_movement} at {shot.distance}"
    lighting = _repair_or("lighting", issues) or visual_style.lighting
    materials = _repair_or("materials", issues) or _join(consistency.materials)
    concept = knowledge.primary_concept()
    engineering_detail = _repair_or("engineering_detail", issues) or _engineering_detail(
        shot, concept
    )
    physics = _repair_or("physics", issues) or _join(knowledge.physics) or _DEFAULT_PHYSICS
    surface_detail = _repair_or("surface_detail", issues) or visual_style.texture_richness
    scale = _repair_or("scale", issues) or consistency.scale_anchor
    atmosphere = _repair_or("atmosphere", issues) or visual_style.atmosphere
    rendering = _repair_or("rendering_style", issues) or visual_style.rendering_style
    storytelling = _repair_or("storytelling", issues) or _STORYTELLING.get(
        shot.narration_block, "engineering scene"
    )

    fields = PromptFields(
        subject=subject,
        environment=environment,
        composition=composition,
        camera=camera,
        lens=shot.lens,
        lighting=lighting,
        materials=materials,
        surface_detail=surface_detail,
        physics=physics,
        scale=scale,
        atmosphere=atmosphere,
        rendering_style=rendering,
        engineering_detail=engineering_detail,
        visual_storytelling=storytelling,
        focus=shot.focus,
        depth=shot.depth,
    )
    quality = list(_QUALITY_THUMBNAIL if thumbnail else _QUALITY_BASE)
    if shot.is_hero and not thumbnail:
        quality.append("highest render fidelity, maximum engineering detail")
    positive = compose_positive(
        fields,
        concept=concept,
        thumbnail=thumbnail,
        strategy=strategy,
        quality_constraints=quality,
    )
    negative = build_negative_prompt(knowledge=knowledge, consistency=consistency)
    return ComposedPrompt(
        shot_id=shot.id,
        narration_block=shot.narration_block,
        fields=fields,
        positive_prompt=positive,
        negative_prompt=negative,
        quality_constraints=quality,
        is_thumbnail=thumbnail,
    )


def _shot_composition(shot: Shot, thumbnail: bool) -> str:
    if thumbnail:
        return "large central subject, minimal clutter, high contrast"
    composition = shot.composition
    if shot.is_climax:
        return f"{composition}, {_CLIMAX_COMPOSITION}"
    return composition


def _engineering_detail(shot: Shot, concept: str) -> str:
    detail = f"{shot.focus} of the {concept or 'mechanism'} shown accurately"
    phrase = _TREATMENT_PHRASES.get(shot.treatment)
    if phrase:
        detail = f"{detail}, {phrase}"
    return detail


def compose_positive(
    fields: PromptFields,
    *,
    concept: str,
    thumbnail: bool,
    strategy: VisualizationStrategyOutput,
    quality_constraints: list[str] | None = None,
) -> str:
    """Deterministic positive prompt in the channel's fixed token order."""
    parts: list[str] = [fields.subject]
    if concept and concept.lower() not in fields.subject.lower():
        parts.append(f"({concept}:1.2)")
    parts.extend(
        [
            fields.engineering_detail,
            fields.materials,
            fields.surface_detail,
            fields.environment,
            fields.composition,
            f"{fields.camera}, {fields.lens}",
            fields.lighting,
            fields.focus,
            fields.depth,
            fields.physics,
            fields.scale,
            fields.atmosphere,
            fields.rendering_style,
            fields.visual_storytelling,
        ]
    )
    if not thumbnail:
        parts.append(strategy.educational_requirement)
    parts.extend(quality_constraints or ())
    parts.append(_ASPECT_QUALIFIER)
    return ", ".join(_non_empty(parts))


def build_negative_prompt(
    *,
    knowledge: KnowledgeOutput,
    consistency: ConsistencyOutput,
) -> str:
    """Deterministic negative prompt: hygiene + forbidden inaccuracies + locks."""
    terms: list[str] = list(_HYGIENE_NEGATIVES)
    terms.extend(knowledge.forbidden_inaccuracies)
    terms.append(_PALETTE_LOCK)
    terms.append("no subject or environment changes between shots")
    if consistency.lighting_direction:
        terms.append("no lighting direction changes")
    if consistency.lens_language:
        terms.append("no lens or focal-length changes between shots")
    if consistency.object_appearance:
        terms.append("no changes to the object's appearance between shots")
    return ", ".join(terms)


# ---------------------------------------------------------------- internals --


def _shot_subject(shot: Shot, consistency: ConsistencyOutput) -> str:
    if consistency.object_registry:
        return consistency.object_registry[0].canonical_descriptor
    return shot.focus


def _repair_or(name: str, issues: set[str]) -> str:
    if name in issues:
        return _REPAIR_DEFAULTS[name]
    return ""


def _join(values: list[str]) -> str:
    return ", ".join(values)


def _non_empty(parts: list[str]) -> list[str]:
    return [part.strip() for part in parts if part and part.strip()]
