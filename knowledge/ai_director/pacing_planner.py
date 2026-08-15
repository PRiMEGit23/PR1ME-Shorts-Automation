"""Pacing planner: information density and shot rhythm per scene.

Each scene gets a pacing score (1-10) from its goal's natural density,
corrected for difficulty (advanced topics breathe slower - the
cognitive-overload guard) and boosted when the comparison beat carries the
arc. The profile names the film's rhythm: fast-open-slow-close,
accelerating, or steady.
"""

from __future__ import annotations

from knowledge.ai_director.director_rules import (
    DIFFICULTY_PACING_MOD,
    PACING_BY_GOAL,
    clamp,
)
from knowledge.ai_director.scene_prioritizer import SceneBlueprint
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.visual_intelligence.visual_goal import VisualGoal


class PacingPlanner:
    """Deterministic pacing allocation for one plan."""

    def plan(
        self,
        blueprints: list[SceneBlueprint],
        plan: EducationalPlan,
        comparison_emphasis: dict[int, int],
    ) -> dict[int, int]:
        """Pacing (1-10) per scene index."""
        difficulty_mod = DIFFICULTY_PACING_MOD[plan.difficulty_level]
        pacing: dict[int, int] = {}
        for blueprint in blueprints:
            score = PACING_BY_GOAL[blueprint.goal] + difficulty_mod
            if (
                blueprint.goal is VisualGoal.COMPARE
                and comparison_emphasis.get(blueprint.index, 0) >= 8
            ):
                score += 1
            pacing[blueprint.index] = clamp(score)
        return pacing

    def profile(self, pacing: dict[int, int]) -> str:
        """Name the film's pacing profile from the first / middle / last beats."""
        first = pacing[1]
        last = pacing[max(pacing)]
        middles = [value for index, value in pacing.items() if 1 < index < max(pacing)]
        if first >= 7 and last <= 5:
            return "fast-open-slow-close"
        if middles and all(
            middle <= first for middle in middles
        ) and last <= first:
            return "fast-open-slow-close"
        if all(
            pacing[index] <= pacing[index + 1]
            for index in range(1, max(pacing))
        ):
            return "accelerating"
        return "steady"
