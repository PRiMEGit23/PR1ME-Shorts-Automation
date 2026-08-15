"""Thumbnail director: deterministic ranking of scenes as thumbnail candidates.

Scoring is a weighted, fully deterministic formula:
    importance * 2
    + shot-type bonus (hero 3, macro 2, cross-section 2, comparison split 2,
      exploded 2, annotated 1, blueprint 1)
    + goal bonus (reveal 2, compare 2, highlight 1, summarize 1)
    + 3 when the scene is an explicit thumbnail candidate
    - 1 when the shot is diagram-like (diagrams read poorly at small size)
Ties break on earlier scene index.
"""

from __future__ import annotations

from collections.abc import Sequence

from knowledge.visual_intelligence.shot_selector import is_diagram_like
from knowledge.visual_intelligence.storyboard import StoryboardScene, ThumbnailPriority
from knowledge.visual_intelligence.visual_goal import VisualGoal

_SHOT_BONUS: dict[str, int] = {
    "hero shot": 3,
    "macro shot": 2,
    "extreme macro shot": 2,
    "cross-section": 2,
    "comparison split": 2,
    "exploded view": 2,
    "annotated diagram": 1,
    "blueprint": 1,
}

_GOAL_BONUS: dict[VisualGoal, int] = {
    VisualGoal.REVEAL_INTERNAL_GEOMETRY: 2,
    VisualGoal.COMPARE: 2,
    VisualGoal.HIGHLIGHT_DIFFERENCE: 1,
    VisualGoal.SUMMARIZE: 1,
}

_CANDIDATE_BONUS = 3
_DIAGRAM_PENALTY = -1


def _score(scene: StoryboardScene) -> tuple[int, str]:
    shot_bonus = _SHOT_BONUS.get(scene.intent.shot_type.value, 0)
    goal_bonus = _GOAL_BONUS.get(scene.intent.goal, 0)
    candidate_bonus = _CANDIDATE_BONUS if scene.thumbnail_candidate else 0
    diagram_penalty = _DIAGRAM_PENALTY if is_diagram_like(scene.intent.shot_type) else 0
    score = (
        scene.scene_importance * 2
        + shot_bonus
        + goal_bonus
        + candidate_bonus
        + diagram_penalty
    )
    rationale = (
        f"score {score} = importance {scene.scene_importance}*2 + shot {shot_bonus} "
        f"+ goal {goal_bonus} + candidate {candidate_bonus} + diagram {diagram_penalty}"
    )
    return score, rationale


def rank_thumbnail_candidates(
    scenes: Sequence[StoryboardScene],
) -> dict[str, ThumbnailPriority]:
    """Rank every scene as a thumbnail candidate; rank 1 is the winner."""
    scored = [(scene.scene_id, _score(scene)) for scene in scenes]
    ordered = sorted(scored, key=lambda item: (-item[1][0], int(item[0][1:])))
    return {
        scene_id: ThumbnailPriority(
            score=score,
            rank=rank,
            rationale=rationale,
        )
        for rank, (scene_id, (score, rationale)) in enumerate(ordered, start=1)
    }


def pick_thumbnail_scene(scenes: Sequence[StoryboardScene]) -> StoryboardScene:
    """Return the scene with thumbnail rank 1."""
    priorities = rank_thumbnail_candidates(scenes)
    winner_id = next(
        scene_id for scene_id, priority in priorities.items() if priority.rank == 1
    )
    return next(scene for scene in scenes if scene.scene_id == winner_id)