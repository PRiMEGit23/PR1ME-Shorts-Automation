"""Hero scene selector: the showpiece of the film.

The hero is the highest-scoring non-recap scene: importance and emotion
carry the score, and reveal-style strategies add a payoff bonus so the
withheld reveal becomes the hero moment. Ties go to the earlier scene so
the result is stable for any input.
"""

from __future__ import annotations

from knowledge.ai_director.director_rules import REVEAL_STRATEGIES
from knowledge.ai_director.scene_prioritizer import SceneBlueprint
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.visual_intelligence.visual_goal import VisualGoal


class HeroSceneSelector:
    """Deterministic hero selection for one plan."""

    def pick(
        self,
        blueprints: list[SceneBlueprint],
        importances: dict[int, int],
        emotions: dict[int, int],
        plan: EducationalPlan,
    ) -> int:
        """The 1-based index of the hero scene (never the recap scene)."""
        payoff_bonus = plan.teaching_strategy in REVEAL_STRATEGIES
        hero: int | None = None
        best = -1
        for blueprint in blueprints:
            index = blueprint.index
            if blueprint.goal is VisualGoal.SUMMARIZE:
                continue
            score = importances[index] * 2 + emotions[index]
            if (
                payoff_bonus
                and blueprint.goal
                in {VisualGoal.REVEAL_INTERNAL_GEOMETRY, VisualGoal.HIGHLIGHT_DIFFERENCE}
            ):
                score += 2
            if score > best:
                best = score
                hero = index
        assert hero is not None  # every arc has at least one non-recap scene
        return hero
