"""Prompt statistics: the prompt-pattern leaderboard and mutation view (Phase 11).

What the winning prompts have in common: the negative-token signatures
that correlate with QA, and the mutation / optimization load per profile.
The "prompt leaderboard" groups by the exact negative-token signature of
the winning prompt (sorted, joined) - the deterministic, replayable
representation of a prompt pattern.
"""

from __future__ import annotations

from knowledge.learning_engine.learning_models import (
    LeaderboardRow,
    PipelineHistory,
)
from knowledge.learning_engine.quality_statistics import group_rows


def prompt_leaderboard(history: PipelineHistory) -> tuple[LeaderboardRow, ...]:
    """Negative-token signatures ranked by mean QA (sorted by mean, then key)."""
    rows: list[LeaderboardRow] = []
    for key, scenes in group_rows(history, "negative_tokens").items():
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
                mean_attempts=round(
                    sum(scene.attempts for scene in scenes) / count, 2
                ),
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.mean, row.key)))


def mutation_summary(history: PipelineHistory) -> dict[str, float]:
    """Total mutations / actions / retries across the history."""
    totals: dict[str, float] = {
        "prompt_mutations": 0.0,
        "optimization_actions": 0.0,
        "attempts": 0.0,
    }
    for project in history.projects:
        for scene in project.scenes:
            totals["prompt_mutations"] += scene.prompt_mutations
            totals["optimization_actions"] += scene.optimization_actions
            totals["attempts"] += scene.attempts
    return totals
