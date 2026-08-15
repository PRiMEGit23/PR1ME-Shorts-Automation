"""Fallback strategy: deterministic model switching on repeated failure.

The video-QA feedback contract: the render loop may switch the image
model when (a) the current model has failed QA ``SWITCH_AFTER_ATTEMPTS``
times in a row and (b) the fallback's predicted QA is at least
``MIN_IMPROVEMENT`` points higher. The predictions come from the quality
predictor - no LLM, no runtime guessing.

The fallback chain is a fixed deterministic order: the preferred model
first, then the registry order of every other image model.
"""

from __future__ import annotations

from knowledge.model_director.backend_rules import default_model_key
from knowledge.model_director.model_registry import REGISTRY, ModelKind
from knowledge.model_director.quality_predictor import expected_qa_score
from knowledge.visual_intelligence.storyboard import ShotType

#: Failures on the current model before a switch is even considered.
SWITCH_AFTER_ATTEMPTS = 2

#: Minimum predicted-QA gain required to justify a switch.
MIN_IMPROVEMENT = 3.0


def fallback_chain(preferred: str | None = None) -> tuple[str, ...]:
    """The ordered chain: preferred first, then the registry image order."""
    chain: list[str] = []
    if preferred is not None:
        try:
            spec = REGISTRY.get(preferred)
        except KeyError:
            spec = None
        if spec is not None and spec.kind is ModelKind.IMAGE:
            chain.append(preferred)
    for spec in REGISTRY.of_kind(ModelKind.IMAGE):
        if spec.key not in chain:
            chain.append(spec.key)
    return tuple(chain)


def next_fallback(current: str, preferred: str | None = None) -> str | None:
    """The next image model after ``current`` in the chain (or None)."""
    chain = fallback_chain(preferred)
    try:
        index = chain.index(current)
    except ValueError:
        return chain[0]
    if index + 1 >= len(chain):
        return None
    return chain[index + 1]


def should_switch_model(
    current: str,
    fallback: str,
    shot_type: ShotType,
    *,
    consecutive_failures: int,
    current_qa: float | None = None,
) -> tuple[bool, str]:
    """The deterministic switch verdict for one failure checkpoint.

    Switches only when the current model has failed enough times in a row
    AND the fallback is predicted to score meaningfully better.
    """
    if consecutive_failures < SWITCH_AFTER_ATTEMPTS:
        return False, (
            f"switch not considered before {SWITCH_AFTER_ATTEMPTS} "
            f"consecutive failures ({consecutive_failures} so far)"
        )
    current_predicted = (
        current_qa if current_qa is not None else expected_qa_score(current, shot_type)
    )
    fallback_predicted = expected_qa_score(fallback, shot_type)
    if fallback_predicted < current_predicted + MIN_IMPROVEMENT:
        return False, (
            f"fallback {fallback} predicts {fallback_predicted} vs "
            f"{current_predicted}; below the {MIN_IMPROVEMENT} improvement bar"
        )
    return True, (
        f"{consecutive_failures} consecutive failures; {fallback} predicts "
        f"{fallback_predicted} vs {current_predicted} - switching"
    )


def chain_exhausted(current: str, preferred: str | None = None) -> bool:
    """True when ``current`` is the last model in the chain."""
    return next_fallback(current, preferred) is None


def default_image_model() -> str:
    return default_model_key()
