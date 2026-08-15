"""Stage 2: Engineering Visual Analyzer.

Decides the single best documentary visualization style for the extracted
knowledge, plus fallback styles and the one educational requirement the
imagery must satisfy.

The deterministic core maps the extracted concepts, mechanisms, and processes
onto the thirteen-style catalog through didactic heuristics: internal
structures demand cross sections, assemblies demand exploded CAD, stress and
motion demand simulation, and so on. The LLM path (when configured) makes the
same decision through the analyzer template.
"""

from __future__ import annotations

from pr1me.visual_architecture._common import (
    VisualContext,
    llm_or_fallback,
    make_logger,
    model_dump_safe,
)
from pr1me.visual_architecture.contracts import (
    KnowledgeOutput,
    VisualizationStrategyOutput,
    VisualizationStyle,
)
from pr1me.visual_architecture.prompts import VISUAL_ANALYZER_PROMPT

__all__ = ["VisualAnalyzer", "choose_strategy"]

#: Trigger words per style, checked against the knowledge block. The first
#: matching style (in priority order) wins; later entries are fallbacks.
_STRATEGY_RULES: list[tuple[VisualizationStyle, tuple[str, ...], tuple[str, ...]]] = [
    (
        VisualizationStyle.CROSS_SECTION,
        ("cross section", "cutaway", "internal", "layer", "interface"),
        ("sectional", "cutaway"),
    ),
    (
        VisualizationStyle.EXPLODED_CAD,
        ("assembly", "assembled", "exploded", "components", "fits together"),
        ("exploded view", "assembly render"),
    ),
    (
        VisualizationStyle.MANUFACTURING_PROCESS,
        ("injection molding", "casting", "forging", "sintering", "welding", "process"),
        ("manufacturing", "production line"),
    ),
    (
        VisualizationStyle.SIMULATION,
        ("stress", "strain", "load", "fatigue", "simulation", "deformation"),
        ("simulation visualization", "fringe plot"),
    ),
    (
        VisualizationStyle.BLUEPRINT,
        ("tolerance", "clearance", "dimension", "measurement", "calibration"),
        ("engineering blueprint", "dimensional drawing"),
    ),
    (
        VisualizationStyle.MATERIAL_VISUALIZATION,
        ("material", "filament", "alloy", "composite", "polymer", "glass"),
        ("material study", "sample comparison"),
    ),
    (
        VisualizationStyle.MACRO_MECHANICAL,
        ("surface", "finish", "micro", "detail", "nozzle", "grip"),
        ("extreme macro", "surface texture"),
    ),
    (
        VisualizationStyle.MICROSCOPE,
        ("microscope", "microscopic", "crystal", "grain", "fiber"),
        ("electron micrograph", "microscopy"),
    ),
    (
        VisualizationStyle.SLOW_MOTION,
        ("melt", "flow", "drip", "droplet", "impact", "snap"),
        ("high-speed capture", "slow motion"),
    ),
    (
        VisualizationStyle.ASSEMBLY_SEQUENCE,
        ("sequence", "step", "stage", "order", "first", "then"),
        ("assembly sequence", "step-by-step"),
    ),
    (
        VisualizationStyle.REAL_WORLD_COMPARISON,
        ("compare", "comparison", "vs", "versus", "difference"),
        ("side-by-side comparison", "benchmark"),
    ),
    (
        VisualizationStyle.TECHNICAL_ILLUSTRATION,
        ("diagram", "illustrate", "schematic", "annotated"),
        ("technical illustration", "annotated diagram"),
    ),
    (
        VisualizationStyle.INDUSTRIAL_PHOTOGRAPHY,
        (),
        ("industrial photography", "documentary photography"),
    ),
]

#: Default rationale template when nothing more specific applies.
_DEFAULT_RATIONALE = (
    "Industrial documentary photography keeps the mechanism believable while "
    "letting the real engineering speak for itself."
)


class VisualAnalyzer:
    """Stage 2 engine: knowledge -> visualization strategy."""

    def __init__(self, context: VisualContext) -> None:
        self._context = context
        self._logger = make_logger("visual_analyzer")

    async def run(self, knowledge: KnowledgeOutput) -> VisualizationStrategyOutput:
        """Choose the best teaching style, preferring the LLM when configured."""
        self._logger.info("event=visual_analyzer.started", n_concepts=len(knowledge.concepts))
        strategy = await llm_or_fallback(
            context=self._context,
            logger=self._logger,
            template=VISUAL_ANALYZER_PROMPT,
            variables=model_dump_safe(knowledge),
            output_model=VisualizationStrategyOutput,
            fallback=lambda: choose_strategy(knowledge),
        )
        self._logger.info(
            "event=visual_analyzer.completed",
            style=strategy.style.value,
        )
        return strategy


def choose_strategy(knowledge: KnowledgeOutput) -> VisualizationStrategyOutput:
    """Deterministic style decision driven by the knowledge block.

    Every trigger check runs against the combined concepts, processes,
    mechanisms, and critical visual elements. The first hit in priority order
    wins; the industrial photography fallback is always last.
    """
    haystack = _knowledge_text(knowledge)
    ranked: list[VisualizationStyle] = []
    for style, triggers, _alternatives in _STRATEGY_RULES:
        if any(token in haystack for token in triggers):
            ranked.append(style)
            if len(ranked) >= 3:
                break
    if not ranked:
        ranked = [VisualizationStyle.INDUSTRIAL_PHOTOGRAPHY]

    primary = ranked[0]
    alternatives = [style.value for style in ranked[1:3]]
    if len(alternatives) < 2:
        for style, _, _ in _STRATEGY_RULES:
            if style not in ranked:
                alternatives.append(style.value)
            if len(alternatives) >= 2:
                break
    rationale = _rationale(primary, knowledge)
    requirement = (
        f"The imagery must make the {knowledge.primary_concept() or 'mechanism'} "
        "physically believable and immediately readable."
    )
    return VisualizationStrategyOutput(
        style=primary,
        rationale=rationale,
        alternatives=alternatives,
        educational_requirement=requirement,
    )


def _knowledge_text(knowledge: KnowledgeOutput) -> str:
    parts = list(knowledge.concepts)
    parts.extend(knowledge.processes)
    parts.extend(knowledge.physics)
    parts.extend(mechanism.name for mechanism in knowledge.mechanisms)
    parts.extend(knowledge.critical_visual_elements)
    return " ".join(parts).lower()


def _rationale(style: VisualizationStyle, knowledge: KnowledgeOutput) -> str:
    if style is VisualizationStyle.INDUSTRIAL_PHOTOGRAPHY:
        return _DEFAULT_RATIONALE
    concept = knowledge.primary_concept()
    label = style.value.replace("_", " ")
    subject = concept or "the mechanism"
    return (
        f"{label.title()} is the most direct way to show {subject}: "
        f"it isolates exactly the detail the narration explains."
    )
