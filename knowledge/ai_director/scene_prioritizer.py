"""Scene prioritizer: decide the arc and every scene's importance.

The AI Director's first decision is structural: how many scenes the film
needs (merge / keep / split), what each scene is for, and how important
each scene is. The arc mirrors the canonical five-beat documentary shape
(hook, reveal, process, compare, recap) and only diverges when the plan's
knowledge flow is short enough to merge or long enough to split.

No heuristics live here: the merge/split thresholds and the canonical shot
mapping come from director_rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.ai_director.director_rules import (
    COMPARISON_STRATEGIES,
    MACRO_REQUIRED_STRATEGIES,
    decide_scene_count,
    shot_for_method,
)
from knowledge.educational_director.educational_models import (
    EducationalPlan,
    VisualTeachingMethod,
)
from knowledge.visual_intelligence.storyboard import ShotType
from knowledge.visual_intelligence.visual_goal import VisualGoal

#: Shots that already deliver inspection-level detail; macro forcing skips them.
_MACRO_LIKE_SHOTS: frozenset[ShotType] = frozenset(
    {ShotType.MACRO, ShotType.EXTREME_MACRO, ShotType.MICROSCOPE}
)


@dataclass(frozen=True)
class SceneBlueprint:
    """One planned scene before the budgets are allocated."""

    index: int
    goal: VisualGoal
    shot_type: ShotType
    method: VisualTeachingMethod | None
    base_importance: int
    notes: tuple[str, ...] = ()


def _evidence_goal(plan: EducationalPlan) -> VisualGoal:
    """The split-arc evidence beat: difference-flavored or process-flavored."""
    compares = (
        plan.teaching_strategy in COMPARISON_STRATEGIES
        or any(
            m is VisualTeachingMethod.COMPARISON_BOARD
            for m in plan.visualization_priority
        )
    )
    return VisualGoal.HIGHLIGHT_DIFFERENCE if compares else VisualGoal.EXPLAIN_PROCESS


class ScenePrioritizer:
    """Deterministic arc planning: scene count, goals, shots, importance."""

    def plan(self, plan: EducationalPlan) -> tuple[list[SceneBlueprint], str]:
        """Plan the arc for one EducationalPlan; returns (blueprints, rationale)."""
        methods = plan.visualization_priority
        count, rationale = decide_scene_count(
            len(plan.knowledge_flow), plan.teaching_strategy, methods
        )

        method_at = lambda position: (  # noqa: E731 - position-aware method lookup
            methods[position] if position < len(methods) else None
        )
        blueprints: list[SceneBlueprint] = [
            SceneBlueprint(
                index=1,
                goal=VisualGoal.INTRODUCE_CONCEPT,
                shot_type=ShotType.HERO,
                method=method_at(0),
                base_importance=4,
            )
        ]
        if count >= 2:
            blueprints.append(
                SceneBlueprint(
                    index=2,
                    goal=VisualGoal.REVEAL_INTERNAL_GEOMETRY,
                    shot_type=shot_for_method(method_at(0)),
                    method=method_at(0),
                    base_importance=3,
                )
            )
        if count >= 3:
            blueprints.append(
                SceneBlueprint(
                    index=3,
                    goal=VisualGoal.EXPLAIN_PROCESS,
                    shot_type=shot_for_method(method_at(1)),
                    method=method_at(1),
                    base_importance=3,
                )
            )
        if count >= 5:
            blueprints.append(
                SceneBlueprint(
                    index=4,
                    goal=VisualGoal.COMPARE,
                    shot_type=shot_for_method(method_at(2)),
                    method=method_at(2),
                    base_importance=3,
                )
            )
        if count >= 6:
            blueprints.append(
                SceneBlueprint(
                    index=5,
                    goal=_evidence_goal(plan),
                    shot_type=shot_for_method(method_at(3)),
                    method=method_at(3),
                    base_importance=3,
                )
            )
        blueprints.append(
            SceneBlueprint(
                index=count,
                goal=VisualGoal.SUMMARIZE,
                shot_type=ShotType.HERO,
                method=method_at(0),
                base_importance=4,
            )
        )
        return self._apply_macro_inspection(blueprints, plan), rationale

    @staticmethod
    def _apply_macro_inspection(
        blueprints: list[SceneBlueprint], plan: EducationalPlan
    ) -> list[SceneBlueprint]:
        """Force macro inspection on the beats that need it.

        Strategies whose teaching vehicle is close inspection (scale
        comparison, failure analysis) get a macro shot on the reveal beat
        unless the method already chooses an inspection-level shot. This is
        the director's "where are macro shots required" decision.
        """
        if plan.teaching_strategy not in MACRO_REQUIRED_STRATEGIES:
            return blueprints
        forced: list[SceneBlueprint] = []
        for blueprint in blueprints:
            if blueprint.index == 2 and blueprint.shot_type not in _MACRO_LIKE_SHOTS:
                blueprint = SceneBlueprint(
                    index=blueprint.index,
                    goal=blueprint.goal,
                    shot_type=ShotType.MACRO,
                    method=blueprint.method,
                    base_importance=blueprint.base_importance,
                    notes=blueprint.notes + ("macro inspection required",),
                )
            forced.append(blueprint)
        return forced
