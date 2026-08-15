"""Learning objectives: a measurable viewer-facing outcome for the short.

The objective inherits the curatorial learning_objective field when present
(the curator already wrote it), and otherwise derives one from the concept.
Success verbs track the teaching strategy so the objective reads like a
checkable promise, not a topic label.
"""

from __future__ import annotations

from knowledge.educational_director.educational_models import (
    LearningObjective,
    TeachingStrategy,
)

_STRATEGY_VERBS: dict[TeachingStrategy, tuple[str, ...]] = {
    TeachingStrategy.COMPARISON: ("compare", "choose"),
    TeachingStrategy.BEFORE_AFTER: ("compare", "recognize"),
    TeachingStrategy.CAUSE_EFFECT: ("explain", "predict"),
    TeachingStrategy.PROBLEM_SOLUTION: ("diagnose", "apply"),
    TeachingStrategy.QUESTION_ANSWER: ("explain", "answer"),
    TeachingStrategy.LAYER_BY_LAYER_REVEAL: ("explain", "sequence"),
    TeachingStrategy.HIDDEN_GEOMETRY: ("describe", "recognize"),
    TeachingStrategy.FAILURE_ANALYSIS: ("diagnose", "avoid"),
    TeachingStrategy.MECHANICAL_BREAKDOWN: ("explain", "predict"),
    TeachingStrategy.ANIMATION_FIRST: ("see", "explain"),
    TeachingStrategy.DIAGRAM_FIRST: ("label", "explain"),
    TeachingStrategy.SCALE_COMPARISON: ("compare", "estimate"),
    TeachingStrategy.PROGRESSIVE_DISCLOSURE: ("explain", "predict"),
    TeachingStrategy.MYTH_BUSTING: ("refute", "recall"),
    TeachingStrategy.REAL_WORLD_EXAMPLE: ("apply", "recognize"),
    TeachingStrategy.SIMULATION: ("predict", "explain"),
    TeachingStrategy.PROCESS_TIMELINE: ("sequence", "explain"),
    TeachingStrategy.MANUFACTURING_SEQUENCE: ("sequence", "explain"),
    TeachingStrategy.FORCE_FLOW: ("trace", "predict"),
    TeachingStrategy.ENERGY_FLOW: ("trace", "explain"),
    TeachingStrategy.MATERIAL_TRANSFORMATION: ("explain", "predict"),
}

_DEFAULT_VERBS = ("explain", "apply")


def derive_learning_objective(
    *,
    curator_objective: str,
    concept: str,
    strategy: TeachingStrategy,
) -> LearningObjective:
    """Build the learning objective, deterministically."""
    verbs = _STRATEGY_VERBS.get(strategy, _DEFAULT_VERBS)
    statement = curator_objective or f"Understand {concept}."
    success_criteria = (
        f"The viewer can {verbs[0]} the key relationship in their own words and "
        f"apply it to a new part."
    )
    return LearningObjective(
        statement=statement,
        verbs=list(verbs),
        success_criteria=success_criteria,
    )