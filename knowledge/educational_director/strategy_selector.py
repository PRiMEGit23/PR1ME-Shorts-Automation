"""Teaching strategy selection: how humans best acquire this concept.

A priority-ordered rule table over the row's curated text (topic, keywords,
engineering summary) picks one primary strategy. Comparison signals win
because "X differs from Y" is the most common knowledge-base pattern; more
specific signals (myth, failure, manufacturing, mechanism) outrank generic
ones. Every choice carries a rationale so nothing is ever random.
"""

from __future__ import annotations

import re

from knowledge.educational_director.educational_models import TeachingStrategy
from knowledge.visual_intelligence.visual_intelligence import KnowledgeBaseRow

_STRATEGY_RULES: tuple[tuple[tuple[str, ...], TeachingStrategy], ...] = (
    (("vs", "versus", "compare", "compared", "comparison", "differ", "difference",
      "side-by-side"),
     TeachingStrategy.COMPARISON),
    (("myth", "misconception", "wrong belief", "actually"), TeachingStrategy.MYTH_BUSTING),
    (("fail", "fails", "failed", "crack", "cracks", "warp", "warping", "fracture",
      "snag", "defect"),
     TeachingStrategy.FAILURE_ANALYSIS),
    (("injection molding", "injection mold", "mold cavity", "ejector"),
     TeachingStrategy.MANUFACTURING_SEQUENCE),
    (("planetary", "epicyclic", "sun gear", "ring gear", "carrier"),
     TeachingStrategy.PROGRESSIVE_DISCLOSURE),
    (("how it is made", "how it's made", "manufactur", "extrude", "machining process"),
     TeachingStrategy.PROCESS_TIMELINE),
    (("inside", "internal", "hidden", "cut open", "expose", "cutaway"),
     TeachingStrategy.HIDDEN_GEOMETRY),
    (("gear", "mechanism", "linkage", "cam", "transmission"),
     TeachingStrategy.MECHANICAL_BREAKDOWN),
    (("heat", "thermal", "temperature", "warm", "cooling"),
     TeachingStrategy.ENERGY_FLOW),
    (("force", "stress", "load", "torque", "tension", "compression"),
     TeachingStrategy.FORCE_FLOW),
    (("scale", "size", "micron", "dimension", "proportion"),
     TeachingStrategy.SCALE_COMPARISON),
    (("material", "property", "filament", "alloy", "polymer"),
     TeachingStrategy.MATERIAL_TRANSFORMATION),
    (("motion", "moves", "rotation", "animation"),
     TeachingStrategy.ANIMATION_FIRST),
    (("before", "after"), TeachingStrategy.BEFORE_AFTER),
    (("cause", "because", "why does"), TeachingStrategy.CAUSE_EFFECT),
    (("problem", "why is"), TeachingStrategy.PROBLEM_SOLUTION),
    (("question", "how does"), TeachingStrategy.QUESTION_ANSWER),
    (("diagram", "schematic"), TeachingStrategy.DIAGRAM_FIRST),
    (("layer", "stack", "build up"), TeachingStrategy.LAYER_BY_LAYER_REVEAL),
)

_FALLBACK_STRATEGY = TeachingStrategy.PROGRESSIVE_DISCLOSURE


def _matches_token(text: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", text) is not None


class StrategySelector:
    """Deterministic teaching-strategy selection for a curated row."""

    def select(
        self,
        row: KnowledgeBaseRow,
        *,
        csv_row: dict[str, str] | None = None,
    ) -> tuple[TeachingStrategy, str]:
        """Pick the primary teaching strategy and justify it."""
        text = " ".join(
            part
            for part in (
                row.topic,
                row.category,
                row.subcategory,
                " ".join(row.keywords),
                row.engineering_summary,
            )
            if part
        ).lower()

        for tokens, strategy in _STRATEGY_RULES:
            for token in tokens:
                if _matches_token(text, token):
                    return strategy, (
                        f"curated text contains '{token}', which matches the "
                        f"{strategy.value} strategy"
                    )
        return _FALLBACK_STRATEGY, (
            f"no signal matched; the {_FALLBACK_STRATEGY.value} strategy is the "
            f"default for unknown shapes"
        )