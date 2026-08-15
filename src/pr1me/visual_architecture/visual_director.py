"""Stage 5: Visual Director.

Chooses the cinematic look applied to every shot: lighting, mood, color
palette, atmosphere, rendering style, contrast, texture richness, realism
level, and the storytelling arc. The palette follows the channel's engineering
color language (green = correct, red = failure, blue = reference geometry,
yellow = important detail, orange = motion), so color always communicates
instead of decorating.

The deterministic core derives the look from the narration block distribution
and the chosen visualization strategy; the LLM path (when configured) makes the
same decision through the director template. Either way the output must be a
single coherent look — the consistency engine depends on it.
"""

from __future__ import annotations

from pr1me.visual_architecture._common import (
    VisualContext,
    llm_or_fallback,
    make_logger,
    model_dump_safe,
)
from pr1me.visual_architecture.contracts import (
    PaletteColor,
    ShotPlanOutput,
    VisualizationStrategyOutput,
    VisualStyleOutput,
)
from pr1me.visual_architecture.prompts import VISUAL_DIRECTOR_PROMPT

__all__ = ["VisualDirector", "direct_look"]

#: Channel engineering color language (prompt 04 convention). Roles are fixed
#: so the consistency engine can pin them across shots.
_PALETTE: tuple[PaletteColor, ...] = (
    PaletteColor(role="background", hex="#1A1D21", usage="dark neutral backdrop in every shot"),
    PaletteColor(role="accent", hex="#FF6B1A", usage="engineering accent on the primary mechanism"),
    PaletteColor(role="text", hex="#F5F7FA", usage="labels and measurement callouts"),
    PaletteColor(role="success", hex="#2ECC71", usage="correct or calibrated state"),
    PaletteColor(role="warning", hex="#F1C40F", usage="important engineering detail"),
    PaletteColor(role="failure", hex="#E74C3C", usage="failure, defect, or unsafe state"),
    PaletteColor(role="motion", hex="#F39C12", usage="motion paths and interaction arrows"),
)

_LIGHTING = {
    "hook": "dramatic key light from upper left with hard shadow separation",
    "explanation": "clean even studio lighting with a soft key from the left",
    "practical_insight": "practical warm workbench light with a cool rim",
    "ending": "polished three-point product lighting",
}

_MOOD = {
    "hook": "curious and high-energy",
    "explanation": "clear, focused, technical",
    "practical_insight": "confident and actionable",
    "ending": "premium and resolved",
}

_CONTRAST = {
    "hook": "high",
    "explanation": "balanced",
    "practical_insight": "balanced",
    "ending": "high",
}


class VisualDirector:
    """Stage 5 engine: shots + strategy -> the cinematic look."""

    def __init__(self, context: VisualContext) -> None:
        self._context = context
        self._logger = make_logger("visual_director")

    async def run(
        self,
        shots: ShotPlanOutput,
        strategy: VisualizationStrategyOutput,
    ) -> VisualStyleOutput:
        """Choose the look, preferring the LLM when configured."""
        self._logger.info(
            "event=visual_director.started",
            n_shots=len(shots.shots),
            strategy=strategy.style.value,
        )
        look = await llm_or_fallback(
            context=self._context,
            logger=self._logger,
            template=VISUAL_DIRECTOR_PROMPT,
            variables={"shots": model_dump_safe(shots), "strategy": model_dump_safe(strategy)},
            output_model=VisualStyleOutput,
            fallback=lambda: direct_look(shots, strategy),
        )
        self._logger.info(
            "event=visual_director.completed",
            realism=look.realism_level,
            thumbnail_mode=look.thumbnail_mode,
        )
        return look


def direct_look(
    shots: ShotPlanOutput,
    strategy: VisualizationStrategyOutput,
) -> VisualStyleOutput:
    """Deterministic look: block-weighted lighting, mood, and the fixed palette."""
    blocks = {shot.narration_block for shot in shots.shots}
    dominant = "explanation"
    for candidate in ("hook", "explanation", "practical_insight", "ending"):
        if candidate in blocks:
            dominant = candidate
    rendering = _rendering_style(strategy)
    return VisualStyleOutput(
        lighting=_LIGHTING[dominant],
        mood=_MOOD[dominant],
        color_palette=[color for color in _PALETTE],
        atmosphere="precision manufacturing environment",
        rendering_style=rendering,
        contrast=_CONTRAST[dominant],
        texture_richness="high machined-metal fidelity, matte polymer, tactile filament",
        realism_level="photorealistic",
        storytelling_arc="curiosity -> mechanism -> application -> memory anchor",
        thumbnail_mode=_has_thumbnail(shots),
    )


def _rendering_style(strategy: VisualizationStrategyOutput) -> str:
    style = strategy.style.value
    if style in {"exploded_cad", "cross_section", "blueprint", "technical_illustration"}:
        return "clean engineering render with measured proportions"
    if style in {"simulation"}:
        return "engineering simulation visualization over a photoreal base"
    return "photorealistic industrial photography"


def _has_thumbnail(shots: ShotPlanOutput) -> bool:
    return any(shot.is_thumbnail for shot in shots.shots)
