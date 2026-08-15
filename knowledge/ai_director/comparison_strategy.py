"""Comparison strategy: where and how hard the film compares.

Decides the comparison emphasis per scene (1-10): the comparison beat is
the strongest when the strategy lives on differences, and when the arc
merged (4 scenes) the comparison emphasis lands on the process scene
instead of its own beat.
"""

from __future__ import annotations

from knowledge.ai_director.director_rules import (
    COMPARISON_STRATEGIES,
    clamp,
)
from knowledge.ai_director.scene_prioritizer import SceneBlueprint
from knowledge.educational_director.educational_models import (
    EducationalPlan,
    VisualTeachingMethod,
)
from knowledge.visual_intelligence.visual_goal import VisualGoal


class ComparisonStrategy:
    """Deterministic comparison emphasis allocation per scene."""

    def plan(
        self,
        blueprints: list[SceneBlueprint],
        plan: EducationalPlan,
        *,
        merged_arc: bool,
    ) -> dict[int, int]:
        """Comparison emphasis (1-10) keyed by 1-based scene index."""
        strategy_compares = plan.teaching_strategy in COMPARISON_STRATEGIES
        has_comparison_board = any(
            m is VisualTeachingMethod.COMPARISON_BOARD
            for m in plan.visualization_priority
        )
        emphasis: dict[int, int] = {}
        for blueprint in blueprints:
            index = blueprint.index
            if blueprint.goal is VisualGoal.COMPARE:
                score = 8
            elif blueprint.goal is VisualGoal.HIGHLIGHT_DIFFERENCE:
                score = 7
            elif merged_arc and index == 3 and strategy_compares:
                score = 7
            else:
                score = 3
                if strategy_compares:
                    score += 2
                if has_comparison_board and blueprint.method is not None:
                    score += 1
            emphasis[index] = clamp(score)
        return emphasis
