"""Pattern detector: deterministic winner-vs-rest comparisons (Phase 11).

For every configured (metric, dimension) pair the detector splits the
history into groups, then compares each group against the aggregate of
all other groups. A group becomes a pattern when it has enough samples
and clears the metric's minimum delta. Confidence is a pure function of
sample coverage and effect size - the same history always yields the
same patterns, in the same order.
"""

from __future__ import annotations

from knowledge.learning_engine.learning_models import PatternObservation, PipelineHistory
from knowledge.learning_engine.learning_rules import (
    CONFIDENCE_BASE,
    CONFIDENCE_DELTA_CAP,
    CONFIDENCE_DELTA_SCALE_ATTEMPTS,
    CONFIDENCE_DELTA_SCALE_QA,
    CONFIDENCE_DELTA_SCALE_RETENTION,
    CONFIDENCE_MAX,
    CONFIDENCE_PER_SAMPLE,
    CONFIDENCE_SAMPLE_CAP,
    MAX_EVIDENCE_SCENES,
    MAX_PATTERNS,
    MIN_DELTA_ATTEMPTS,
    MIN_DELTA_QA,
    MIN_DELTA_RETENTION,
    MIN_GROUP_SAMPLES,
    PATTERN_DIMENSIONS,
)
from knowledge.learning_engine.quality_statistics import group_rows

#: Which metric a dimension's values are compared on.
_METRIC_ATTRIBUTE = {
    "qa": "qa_score",
    "attempts": "attempts",
    "retention": "retention_prediction",
}


def _delta_scale(metric: str) -> float:
    if metric == "attempts":
        return CONFIDENCE_DELTA_SCALE_ATTEMPTS
    if metric == "retention":
        return CONFIDENCE_DELTA_SCALE_RETENTION
    return CONFIDENCE_DELTA_SCALE_QA


def _min_delta(metric: str) -> float:
    if metric == "attempts":
        return MIN_DELTA_ATTEMPTS
    if metric == "retention":
        return MIN_DELTA_RETENTION
    return MIN_DELTA_QA


def _confidence(count: int, delta: float, metric: str) -> float:
    sample_bonus = min(
        CONFIDENCE_SAMPLE_CAP,
        max(0, count - MIN_GROUP_SAMPLES) * CONFIDENCE_PER_SAMPLE,
    )
    delta_bonus = min(CONFIDENCE_DELTA_CAP, abs(delta) / _delta_scale(metric))
    return round(
        min(CONFIDENCE_MAX, CONFIDENCE_BASE + sample_bonus + delta_bonus), 2
    )


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value.lower())


def detect_patterns(history: PipelineHistory) -> tuple[PatternObservation, ...]:
    """All deterministic winner-vs-rest patterns for the history.

    Linear in the scene count: totals are aggregated once per (metric,
    dimension), so the winner-vs-rest comparison is O(1) per group.
    """
    observations: list[PatternObservation] = []
    all_scenes = [
        scene for project in history.projects for scene in project.scenes
    ]
    rest_total = len(all_scenes)
    for metric, dimensions in PATTERN_DIMENSIONS.items():
        better_when_lower = metric == "attempts"
        attribute = _METRIC_ATTRIBUTE[metric]
        for dimension in dimensions:
            groups = group_rows(history, dimension)
            total_sum = sum(getattr(scene, attribute) for scene in all_scenes)
            for key in sorted(groups):
                winner_scenes = groups[key]
                count = len(winner_scenes)
                if count < MIN_GROUP_SAMPLES:
                    continue
                winner_sum = sum(
                    getattr(scene, attribute) for scene in winner_scenes
                )
                winner_mean = winner_sum / count
                rest_count = rest_total - count
                if rest_count < MIN_GROUP_SAMPLES:
                    continue
                rest_mean = (total_sum - winner_sum) / rest_count
                delta = winner_mean - rest_mean
                if better_when_lower:
                    delta = -delta
                if delta < _min_delta(metric):
                    continue
                evidence = tuple(
                    sorted(f"{scene.run_id}:{scene.scene_id}" for scene in winner_scenes)
                )[:MAX_EVIDENCE_SCENES]
                direction = "fewer attempts" if better_when_lower else f"higher {metric}"
                observations.append(
                    PatternObservation(
                        pattern_id=f"{metric}-{dimension}-{_slug(key)}",
                        metric=metric,
                        dimension=dimension,
                        winner=key,
                        rest_mean=round(rest_mean, 1),
                        delta=round(delta, 2),
                        winner_count=count,
                        rest_count=rest_count,
                        confidence=_confidence(count, delta, metric),
                        better_when_lower=better_when_lower,
                        evidence_scenes=evidence,
                        description=(
                            f"{key} {direction} than the rest "
                            f"({winner_mean:.1f} vs {rest_mean:.1f} over "
                            f"{count} scenes)"
                        ),
                    )
                )
    return tuple(
        sorted(
            observations,
            key=lambda observation: (
                -observation.confidence,
                -observation.delta,
                observation.pattern_id,
            ),
        )
    )[:MAX_PATTERNS]
