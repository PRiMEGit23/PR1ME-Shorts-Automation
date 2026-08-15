"""Reveal planner: when each scene's information becomes visible.

Strategies that earn their payoff by withholding (layer-by-layer reveal,
hidden geometry, progressive disclosure, myth busting, ...) get a staggered
reveal: the reveal scene is pushed after the comparison beat so the viewer
sees the context before the payoff. Everything else reveals sequentially.
"""

from __future__ import annotations

from knowledge.ai_director.director_rules import REVEAL_STRATEGIES
from knowledge.ai_director.scene_prioritizer import SceneBlueprint
from knowledge.educational_director.educational_models import EducationalPlan


class RevealPlanner:
    """Deterministic reveal ordering for one plan."""

    def plan(
        self, blueprints: list[SceneBlueprint], plan: EducationalPlan
    ) -> tuple[dict[int, int], str]:
        """Reveal order per scene index, plus the reveal-plan label."""
        order = {blueprint.index: blueprint.index for blueprint in blueprints}
        label = "sequential reveal"
        if plan.teaching_strategy in REVEAL_STRATEGIES and len(order) >= 4:
            reveal_index = 2
            swap_index = reveal_index + 2
            if swap_index in order:
                order[reveal_index], order[swap_index] = (
                    order[swap_index],
                    order[reveal_index],
                )
                label = "staggered reveal"
        return order, label
