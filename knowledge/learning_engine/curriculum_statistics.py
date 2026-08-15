"""Curriculum statistics: topic, retention, and educational leaderboards (Phase 11).

The teaching-side view of a history: which topics score, how predicted
retention behaves per transition, and the educational-quality / thumbnail
picture - everything the curriculum could learn from.
"""

from __future__ import annotations

from knowledge.learning_engine.learning_models import (
    LeaderboardRow,
    PipelineHistory,
)
from knowledge.learning_engine.quality_statistics import group_rows


def topic_leaderboard(history: PipelineHistory) -> tuple[LeaderboardRow, ...]:
    """Per topic: QA, retention, educational score, thumbnail priority."""
    rows: list[LeaderboardRow] = []
    for key, scenes in group_rows(history, "topic").items():
        count = len(scenes)
        scores = [scene.qa_score for scene in scenes]
        rows.append(
            LeaderboardRow(
                key=key,
                count=count,
                mean=round(sum(scores) / count, 1),
                minimum=round(min(scores), 1),
                maximum=round(max(scores), 1),
                pass_rate=round(
                    sum(1 for scene in scenes if scene.passed) / count, 3
                ),
                mean_retention=round(
                    sum(scene.retention_prediction for scene in scenes) / count, 1
                ),
                mean_educational=round(
                    sum(scene.educational_score for scene in scenes) / count, 1
                ),
                mean_thumbnail_priority=round(
                    sum(scene.thumbnail_priority for scene in scenes) / count, 2
                ),
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.mean, row.key)))


def retention_leaderboard(history: PipelineHistory) -> tuple[LeaderboardRow, ...]:
    """Per transition type: mean predicted retention (sorted, deterministic)."""
    rows: list[LeaderboardRow] = []
    for key, scenes in group_rows(history, "transition_type").items():
        count = len(scenes)
        retention = [scene.retention_prediction for scene in scenes]
        rows.append(
            LeaderboardRow(
                key=key,
                count=count,
                mean=round(sum(retention) / count, 1),
                minimum=round(min(retention), 1),
                maximum=round(max(retention), 1),
                pass_rate=round(
                    sum(1 for scene in scenes if scene.passed) / count, 3
                ),
                mean_attempts=round(
                    sum(scene.attempts for scene in scenes) / count, 2
                ),
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.mean, row.key)))


def educational_stats(history: PipelineHistory) -> dict[str, float]:
    """Mean educational score per cognitive step, and the step histogram."""
    from knowledge.learning_engine.quality_statistics import group_rows as _group

    result: dict[str, float] = {}
    for key, scenes in _group(history, "cognitive_step").items():
        count = len(scenes)
        result[key] = round(
            sum(scene.educational_score for scene in scenes) / count, 1
        )
    return dict(sorted(result.items()))
