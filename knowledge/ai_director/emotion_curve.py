"""Emotion curve: the emotional pacing of the whole film.

Maps every scene to its emotional intensity (1-10) from the cognitive beat
it represents, applies the strategy's payoff boost, and names the arc shape
(hook-peak / build-to-peak / climax-close / steady) so downstream modules
share one vocabulary.
"""

from __future__ import annotations

from knowledge.ai_director.director_rules import (
    EMOTION_BOOST_GOALS,
    EMOTION_BOOST_STRATEGIES,
    EMOTION_BY_STAGE,
    GOAL_DOMINANT_STAGE,
    clamp,
)
from knowledge.ai_director.scene_prioritizer import SceneBlueprint
from knowledge.educational_director.educational_models import EducationalPlan


class EmotionCurve:
    """Deterministic emotional arc for one plan."""

    def curve(
        self, blueprints: list[SceneBlueprint], plan: EducationalPlan
    ) -> dict[int, int]:
        """Emotion (1-10) per scene index, plus the arc label via :meth:`label`."""
        boost = plan.teaching_strategy in EMOTION_BOOST_STRATEGIES
        emotions: dict[int, int] = {}
        for blueprint in blueprints:
            stage = GOAL_DOMINANT_STAGE[blueprint.goal]
            score = EMOTION_BY_STAGE[stage]
            if boost and blueprint.goal in EMOTION_BOOST_GOALS:
                score += 1
            emotions[blueprint.index] = clamp(score)
        return emotions

    def label(self, emotions: dict[int, int]) -> str:
        """Name the arc shape from the peak's position (ties go to the first)."""
        peaks = [index for index, value in emotions.items() if value == max(emotions.values())]
        if len(peaks) == len(emotions):
            return "steady"
        peak = min(peaks)
        last = max(emotions)
        if peak == 1:
            return "hook-peak"
        if peak == last:
            return "climax-close"
        return "build-to-peak"
