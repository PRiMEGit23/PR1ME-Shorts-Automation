"""Transition planning: deterministic cut rhythm into each scene.

The opening scene has no transition, summaries fade out, side-by-side
comparisons wipe, flow explanations dissolve, and everything else cuts. An
explicit non-default transition hint in the specification wins, so a curator
can overrule the rhythm without breaking determinism.
"""

from __future__ import annotations

from collections.abc import Sequence

from knowledge.visual_architecture import Scene, TransitionType
from knowledge.visual_intelligence.storyboard import ShotType, Transition
from knowledge.visual_intelligence.visual_goal import VisualGoal

_COMPARISON_SHOTS = frozenset({ShotType.COMPARISON_SPLIT, ShotType.BEFORE_AFTER})
_FLOW_GOALS = frozenset({VisualGoal.EXPLAIN_FORCE_FLOW, VisualGoal.EXPLAIN_HEAT_FLOW})


def _planned_transition(goal: VisualGoal, shot: ShotType, index: int) -> Transition:
    if index == 0:
        return Transition(type=TransitionType.NONE, rationale="opening scene")
    if goal is VisualGoal.SUMMARIZE:
        return Transition(type=TransitionType.FADE, rationale="summary fades out")
    if shot in _COMPARISON_SHOTS:
        return Transition(
            type=TransitionType.WIPE,
            direction="horizontal",
            rationale="comparison wipes between options",
        )
    if goal in _FLOW_GOALS:
        return Transition(type=TransitionType.DISSOLVE, rationale="flow dissolves between states")
    return Transition(type=TransitionType.CUT, rationale="direct cut keeps the rhythm tight")


def plan_transitions(
    scenes: Sequence[Scene],
    goals: Sequence[VisualGoal],
    shots: Sequence[ShotType],
) -> list[Transition]:
    """Choose the transition into every scene, deterministically."""
    if not (len(scenes) == len(goals) == len(shots)):
        raise ValueError("scenes, goals, and shots must have equal length")

    transitions: list[Transition] = []
    previous: VisualGoal | None = None
    for index, (scene, goal, shot) in enumerate(zip(scenes, goals, shots, strict=True)):
        hint = scene.transition_hint
        if hint.type not in (TransitionType.CUT, TransitionType.NONE) and index > 0:
            transitions.append(
                Transition(
                    type=hint.type,
                    direction=hint.direction,
                    rationale="explicit transition hint from the specification",
                )
            )
            previous = goal
            continue
        if previous == goal and goal in _FLOW_GOALS:
            transitions.append(
                Transition(type=TransitionType.DISSOLVE, rationale="repeated flow dissolves")
            )
        else:
            transitions.append(_planned_transition(goal, shot, index))
        previous = goal
    return transitions