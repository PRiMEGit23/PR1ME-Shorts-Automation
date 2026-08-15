"""Visual budget allocator: how much visual power each scene deserves.

Converts the educational intent into the per-scene budgets every downstream
module reads: visual budget (overall richness), animation budget, motion
budget, diagram priority (diagram vs photorealism), engineering emphasis,
and the engineering overlays the scene may carry. Every budget is a pure
function of the plan and the scene blueprint - no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.ai_director.director_rules import (
    ANIMATED_METHODS,
    ANIMATION_BUDGET_BY_REQUIREMENT,
    DIAGRAM_PREFERRED_STRATEGIES,
    ENGINEERING_EMPHASIS_METHODS,
    clamp,
    visualization_for,
)
from knowledge.ai_director.scene_prioritizer import SceneBlueprint
from knowledge.educational_director.educational_models import (
    EducationalPlan,
    TeachingStrategy,
    VisualTeachingMethod,
)
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualization,
    EngineeringVisualizationType,
)
from knowledge.visual_intelligence.visual_goal import VisualGoal

_DIAGRAM_LIKE_METHODS: frozenset[VisualTeachingMethod] = frozenset(
    {
        VisualTeachingMethod.DIAGRAM,
        VisualTeachingMethod.TIMELINE,
        VisualTeachingMethod.INFOGRAPHIC,
        VisualTeachingMethod.STRESS_VISUALIZATION,
        VisualTeachingMethod.THERMAL_VISUALIZATION,
        VisualTeachingMethod.CROSS_SECTION,
        VisualTeachingMethod.SECTION_VIEW,
        VisualTeachingMethod.XRAY,
        VisualTeachingMethod.TRANSPARENT_HOUSING,
    }
)

_ANIMATION_FIRST_STRATEGIES: frozenset[TeachingStrategy] = frozenset(
    {TeachingStrategy.ANIMATION_FIRST, TeachingStrategy.SIMULATION}
)


@dataclass(frozen=True)
class VisualBudget:
    """The allocated creative budget for one scene."""

    visual_budget: int
    animation_budget: int
    motion_budget: int
    diagram_priority: int
    engineering_emphasis: int
    visualizations: tuple[EngineeringVisualization, ...] = ()


class VisualBudgetAllocator:
    """Allocates the plan's visual budget across the scene blueprints."""

    def allocate(
        self,
        blueprints: list[SceneBlueprint],
        plan: EducationalPlan,
    ) -> dict[int, VisualBudget]:
        """Allocate budgets; keyed by 1-based scene index."""
        reveal_index = 2 if len(blueprints) >= 2 else 1
        budgets: dict[int, VisualBudget] = {}
        for blueprint in blueprints:
            index = blueprint.index
            is_reveal = index == reveal_index

            diagram_priority = self._diagram_priority(blueprint, plan)
            engineering_emphasis = self._engineering_emphasis(blueprint, plan)
            visual_budget = self._visual_budget(blueprint, plan)
            animation_budget = self._animation_budget(plan)
            motion_budget = clamp(
                round(2 + blueprint.base_importance + (2 if animation_budget >= 8 else 0))
            )

            visualizations: list[EngineeringVisualization] = []
            if is_reveal:
                visualizations.append(
                    EngineeringVisualization(
                        type=EngineeringVisualizationType.CROSS_SECTION,
                        prompt_tokens=["cutaway cross-section view"],
                        rationale="planned by the AI Director for the reveal beat",
                    )
                )
            if diagram_priority >= 9 and len(visualizations) < 2:
                visualizations.append(
                    visualization_for(
                        EngineeringVisualizationType.WIREFRAME_OVERLAY,
                        "diagram-first strategy earns a wireframe overlay",
                    )
                )
            if engineering_emphasis >= 9 and len(visualizations) < 2:
                visualizations.append(
                    visualization_for(
                        EngineeringVisualizationType.DIMENSION_OVERLAY,
                        "high engineering emphasis earns dimension callouts",
                    )
                )

            budgets[index] = VisualBudget(
                visual_budget=visual_budget,
                animation_budget=animation_budget,
                motion_budget=motion_budget,
                diagram_priority=diagram_priority,
                engineering_emphasis=engineering_emphasis,
                visualizations=tuple(visualizations),
            )
        return budgets

    def _diagram_priority(
        self, blueprint: SceneBlueprint, plan: EducationalPlan
    ) -> int:
        """Diagram beats photorealism when the strategy is diagram-first."""
        if plan.teaching_strategy in DIAGRAM_PREFERRED_STRATEGIES:
            return 9
        method = blueprint.method
        if method is not None and method in _DIAGRAM_LIKE_METHODS:
            return 7
        return 3

    def _engineering_emphasis(
        self, blueprint: SceneBlueprint, plan: EducationalPlan
    ) -> int:
        """Engineering overlays matter most for accuracy-driven scenes."""
        emphasis = 3
        method = blueprint.method
        if method is not None and method in ENGINEERING_EMPHASIS_METHODS:
            emphasis += 4
        if plan.teaching_strategy in DIAGRAM_PREFERRED_STRATEGIES:
            emphasis += 1
        return clamp(emphasis)

    def _visual_budget(
        self, blueprint: SceneBlueprint, plan: EducationalPlan
    ) -> int:
        """Overall visual richness: importance plus strategy and method boosts."""
        budget = 2 + blueprint.base_importance
        if blueprint.goal is VisualGoal.SUMMARIZE:
            budget += 1
        if plan.teaching_strategy in DIAGRAM_PREFERRED_STRATEGIES:
            budget += 1
        if plan.animation_requirement.value != "no":
            budget += 1
        return clamp(budget)

    def _animation_budget(self, plan: EducationalPlan) -> int:
        """Animation budget from the plan's animation requirement and methods."""
        budget = ANIMATION_BUDGET_BY_REQUIREMENT[plan.animation_requirement]
        if any(m in ANIMATED_METHODS for m in plan.visualization_priority):
            budget += 2
        if plan.teaching_strategy in _ANIMATION_FIRST_STRATEGIES:
            budget += 1
        return clamp(budget)
