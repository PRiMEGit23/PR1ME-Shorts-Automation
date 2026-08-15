"""Thumbnail strategy: the scene that stops the scroll.

Scores every scene on thumbnail pull (importance, emotion, motion,
diagram potential, hero bonus) with the recap scene excluded by rule, then
ranks the scenes so the storyboard can carry the pick. The recap can never
win: a summary frame is weak at 12px tall.
"""

from __future__ import annotations

from knowledge.ai_director.director_rules import thumbnail_score
from knowledge.ai_director.scene_prioritizer import SceneBlueprint
from knowledge.ai_director.visual_budget import VisualBudget
from knowledge.visual_intelligence.storyboard import ThumbnailPriority
from knowledge.visual_intelligence.visual_goal import VisualGoal


class ThumbnailStrategy:
    """Deterministic thumbnail pick and per-scene thumbnail priority."""

    def pick(
        self,
        blueprints: list[SceneBlueprint],
        importances: dict[int, int],
        emotions: dict[int, int],
        budgets: dict[int, VisualBudget],
        hero_index: int,
    ) -> tuple[int, dict[int, ThumbnailPriority]]:
        """(thumbnail index, per-scene ThumbnailPriority) - ties go earlier."""
        scores: dict[int, int] = {}
        for blueprint in blueprints:
            index = blueprint.index
            budget = budgets[index]
            scores[index] = thumbnail_score(
                importances[index],
                emotions[index],
                budget.motion_budget,
                budget.diagram_priority,
                is_hero=index == hero_index,
                is_recap=blueprint.goal is VisualGoal.SUMMARIZE,
            )

        best = max(scores.values())
        thumbnail = min(index for index, score in scores.items() if score == best)

        priorities: dict[int, ThumbnailPriority] = {}
        for index, score in scores.items():
            if index == thumbnail:
                priorities[index] = ThumbnailPriority(
                    score=score,
                    rank=1,
                    rationale=(
                        "strongest thumbnail pull: highest importance, emotion, "
                        "and hero bonus without recap weakness"
                    ),
                )
            else:
                priorities[index] = ThumbnailPriority(
                    score=score,
                    rank=2,
                    rationale="not the thumbnail pick",
                )
        return thumbnail, priorities
