"""Visual method selection: the visual genres that teach this topic best.

A deterministic table maps each teaching strategy to an ordered list of visual
teaching methods (primary first). Topic-specific refinements then swap in
methods the strategy table would miss - for example, motion visualization for
gearsets and thermal visualization for molding cooling. The result is the
VisualizationPriority the downstream visual director will honor.
"""

from __future__ import annotations

from knowledge.educational_director.educational_models import (
    TeachingStrategy,
    VisualTeachingMethod,
)
from knowledge.visual_intelligence.visual_intelligence import KnowledgeBaseRow

_STRATEGY_METHODS: dict[TeachingStrategy, tuple[VisualTeachingMethod, ...]] = {
    TeachingStrategy.COMPARISON: (
        VisualTeachingMethod.COMPARISON_BOARD,
        VisualTeachingMethod.CROSS_SECTION,
        VisualTeachingMethod.STRESS_VISUALIZATION,
    ),
    TeachingStrategy.BEFORE_AFTER: (
        VisualTeachingMethod.COMPARISON_BOARD,
        VisualTeachingMethod.MACRO,
        VisualTeachingMethod.TIMELINE,
    ),
    TeachingStrategy.CAUSE_EFFECT: (
        VisualTeachingMethod.DIAGRAM,
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.CROSS_SECTION,
    ),
    TeachingStrategy.PROBLEM_SOLUTION: (
        VisualTeachingMethod.DIAGRAM,
        VisualTeachingMethod.EXPLODED_VIEW,
        VisualTeachingMethod.COMPARISON_BOARD,
    ),
    TeachingStrategy.QUESTION_ANSWER: (
        VisualTeachingMethod.DIAGRAM,
        VisualTeachingMethod.CAD,
        VisualTeachingMethod.INFOGRAPHIC,
    ),
    TeachingStrategy.LAYER_BY_LAYER_REVEAL: (
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.CROSS_SECTION,
        VisualTeachingMethod.EXPLODED_VIEW,
    ),
    TeachingStrategy.HIDDEN_GEOMETRY: (
        VisualTeachingMethod.CROSS_SECTION,
        VisualTeachingMethod.CUTAWAY,
        VisualTeachingMethod.XRAY,
    ),
    TeachingStrategy.FAILURE_ANALYSIS: (
        VisualTeachingMethod.STRESS_VISUALIZATION,
        VisualTeachingMethod.CROSS_SECTION,
        VisualTeachingMethod.MACRO,
    ),
    TeachingStrategy.MECHANICAL_BREAKDOWN: (
        VisualTeachingMethod.TRANSPARENT_HOUSING,
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.CAD,
    ),
    TeachingStrategy.ANIMATION_FIRST: (
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.MOTION_VISUALIZATION,
        VisualTeachingMethod.CAD,
    ),
    TeachingStrategy.DIAGRAM_FIRST: (
        VisualTeachingMethod.DIAGRAM,
        VisualTeachingMethod.INFOGRAPHIC,
        VisualTeachingMethod.SECTION_VIEW,
    ),
    TeachingStrategy.SCALE_COMPARISON: (
        VisualTeachingMethod.COMPARISON_BOARD,
        VisualTeachingMethod.MACRO,
        VisualTeachingMethod.INFOGRAPHIC,
    ),
    TeachingStrategy.PROGRESSIVE_DISCLOSURE: (
        VisualTeachingMethod.TRANSPARENT_HOUSING,
        VisualTeachingMethod.EXPLODED_VIEW,
        VisualTeachingMethod.ANIMATION,
    ),
    TeachingStrategy.MYTH_BUSTING: (
        VisualTeachingMethod.COMPARISON_BOARD,
        VisualTeachingMethod.INFOGRAPHIC,
        VisualTeachingMethod.MACRO,
    ),
    TeachingStrategy.REAL_WORLD_EXAMPLE: (
        VisualTeachingMethod.MACRO,
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.CAD,
    ),
    TeachingStrategy.SIMULATION: (
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.STRESS_VISUALIZATION,
        VisualTeachingMethod.THERMAL_VISUALIZATION,
    ),
    TeachingStrategy.PROCESS_TIMELINE: (
        VisualTeachingMethod.TIMELINE,
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.EXPLODED_VIEW,
    ),
    TeachingStrategy.MANUFACTURING_SEQUENCE: (
        VisualTeachingMethod.EXPLODED_VIEW,
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.TIMELINE,
    ),
    TeachingStrategy.FORCE_FLOW: (
        VisualTeachingMethod.STRESS_VISUALIZATION,
        VisualTeachingMethod.DIAGRAM,
        VisualTeachingMethod.ANIMATION,
    ),
    TeachingStrategy.ENERGY_FLOW: (
        VisualTeachingMethod.THERMAL_VISUALIZATION,
        VisualTeachingMethod.DIAGRAM,
        VisualTeachingMethod.ANIMATION,
    ),
    TeachingStrategy.MATERIAL_TRANSFORMATION: (
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.MICROSCOPE,
        VisualTeachingMethod.MACRO,
    ),
}

_FALLBACK_METHODS = (
    VisualTeachingMethod.DIAGRAM,
    VisualTeachingMethod.ANIMATION,
    VisualTeachingMethod.EXPLODED_VIEW,
)

_REFINEMENTS: tuple[
    tuple[tuple[str, ...], tuple[VisualTeachingMethod, ...]], ...
] = (
    (
        ("planetary", "sun gear", "ring gear", "gear box", "epicyclic"),
        (
            VisualTeachingMethod.TRANSPARENT_HOUSING,
            VisualTeachingMethod.MOTION_VISUALIZATION,
            VisualTeachingMethod.EXPLODED_VIEW,
            VisualTeachingMethod.ANIMATION,
        ),
    ),
    (
        ("injection molding", "mold cavity", "ejector", "molded parts"),
        (
            VisualTeachingMethod.EXPLODED_VIEW,
            VisualTeachingMethod.ANIMATION,
            VisualTeachingMethod.THERMAL_VISUALIZATION,
            VisualTeachingMethod.TIMELINE,
        ),
    ),
    (
        ("infill", "gyroid", "isotropic"),
        (
            VisualTeachingMethod.COMPARISON_BOARD,
            VisualTeachingMethod.CROSS_SECTION,
            VisualTeachingMethod.STRESS_VISUALIZATION,
        ),
    ),
)


class VisualMethodSelector:
    """Deterministic selection of the visual teaching methods for a topic."""

    def select(
        self,
        strategy: TeachingStrategy,
        row: KnowledgeBaseRow,
    ) -> tuple[list[VisualTeachingMethod], str]:
        """Pick the ordered visual methods and justify the choice."""
        methods = _STRATEGY_METHODS.get(strategy, _FALLBACK_METHODS)
        text = " ".join(
            part
            for part in (
                row.topic,
                row.subcategory,
                " ".join(row.keywords),
                row.engineering_summary,
            )
            if part
        ).lower()

        for tokens, refined in _REFINEMENTS:
            if any(token in text for token in tokens):
                return list(refined), (
                    f"topic text matches {[t for t in tokens if t in text]}, which "
                    f"refines the {strategy.value} method list"
                )

        return list(methods), (
            f"the {strategy.value} strategy prescribes this method order"
        )