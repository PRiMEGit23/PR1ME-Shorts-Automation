"""Render statistics: retries, switches, duration, VRAM leaderboards (Phase 11).

The render-side view of a history: how many attempts every scene needed,
how often the loop switched models, how long and how heavy the renders
were - grouped deterministically, with the render leaderboard keyed by
video model.
"""

from __future__ import annotations

from knowledge.learning_engine.learning_models import (
    LeaderboardRow,
    PipelineHistory,
    SceneObservation,
)
from knowledge.learning_engine.quality_statistics import group_rows


def render_leaderboard(history: PipelineHistory) -> tuple[LeaderboardRow, ...]:
    """Per video model: QA, attempts, duration, VRAM - sorted by mean QA."""
    rows: list[LeaderboardRow] = []
    for key, scenes in group_rows(history, "video_model").items():
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
                mean_duration_ms=round(
                    sum(scene.render_duration_ms for scene in scenes) / count, 1
                ),
                mean_vram_mb=round(sum(scene.vram_mb for scene in scenes) / count),
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.mean, row.key)))


def retry_stats(history: PipelineHistory) -> dict[str, int]:
    """How many scenes needed 1, 2, 3... attempts (deterministic histogram)."""
    histogram: dict[str, int] = {}
    for project in history.projects:
        for scene in project.scenes:
            bucket = f"attempts_{min(scene.attempts, 5)}+"
            histogram[bucket] = histogram.get(bucket, 0) + 1
    return dict(sorted(histogram.items()))


def switch_stats(history: PipelineHistory) -> dict[str, int]:
    """Total model switches per image model (deterministic histogram)."""
    totals: dict[str, int] = {}
    for project in history.projects:
        for scene in project.scenes:
            if scene.model_switches:
                totals[scene.image_model] = (
                    totals.get(scene.image_model, 0) + scene.model_switches
                )
    return dict(sorted(totals.items()))


def mutation_stats(history: PipelineHistory) -> dict[str, float]:
    """Mean prompt mutations and optimization actions per render profile."""
    from knowledge.learning_engine.quality_statistics import group_rows as _group

    result: dict[str, float] = {}
    for key, scenes in _group(history, "render_profile").items():
        count = len(scenes)
        result[f"mutations_{key}"] = round(
            sum(scene.prompt_mutations for scene in scenes) / count, 2
        )
        result[f"actions_{key}"] = round(
            sum(scene.optimization_actions for scene in scenes) / count, 2
        )
    return dict(sorted(result.items()))


def _all_scenes(history: PipelineHistory) -> list[SceneObservation]:
    return [scene for project in history.projects for scene in project.scenes]
