"""Quality statistics: overall health and the QA-side leaderboards (Phase 11).

One deterministic view of a run history: overall summary, the shared
grouping helper every statistics module uses, and the QA leaderboards
(by model, workflow, scene position, topic, shot strategy, and
engineering visualization).
"""

from __future__ import annotations

from knowledge.learning_engine.learning_models import (
    LeaderboardRow,
    PipelineHistory,
    QualitySummary,
    SceneObservation,
)

#: The observation attribute each leaderboard dimension reads.
_DIMENSION_ATTRIBUTE: dict[str, str] = {
    "image_model": "image_model",
    "render_profile": "render_profile",
    "scene_id": "scene_id",
    "topic": "topic",
    "shot_type": "shot_type",
    "visualization_type": "visualization_type",
}


def group_rows(
    history: PipelineHistory,
    dimension: str,
) -> dict[str, list[SceneObservation]]:
    """Group every scene observation by one dimension (stable insertion).

    Dimensions with list values (negative tokens) group by the joined
    signature; ``visualization_type`` groups scenes without a
    visualization under the literal key ``"(none)"``.
    """
    attribute = _DIMENSION_ATTRIBUTE.get(dimension, dimension)
    groups: dict[str, list[SceneObservation]] = {}
    for project in history.projects:
        for scene in project.scenes:
            if attribute == "visualization_type":
                key = scene.visualization_type.value if scene.visualization_type else "(none)"
            else:
                value = getattr(scene, attribute)
                if isinstance(value, tuple):
                    key = "+".join(value) if value else "(empty)"
                else:
                    key = value.value if hasattr(value, "value") else str(value)
            groups.setdefault(key, []).append(scene)
    return groups


def _row(key: str, scenes: list[SceneObservation]) -> LeaderboardRow:
    count = len(scenes)
    scores = [scene.qa_score for scene in scenes]
    passed = sum(1 for scene in scenes if scene.passed)
    return LeaderboardRow(
        key=key,
        count=count,
        mean=round(sum(scores) / count, 1),
        minimum=round(min(scores), 1),
        maximum=round(max(scores), 1),
        pass_rate=round(passed / count, 3),
    )


def qa_leaderboard(history: PipelineHistory, dimension: str) -> tuple[LeaderboardRow, ...]:
    """One QA leaderboard: rows sorted by mean QA, then key, deterministic."""
    rows = [_row(key, scenes) for key, scenes in group_rows(history, dimension).items()]
    return tuple(sorted(rows, key=lambda row: (-row.mean, row.key)))


def all_qa_leaderboards(
    history: PipelineHistory,
) -> dict[str, tuple[LeaderboardRow, ...]]:
    """The six QA-side leaderboards (model, workflow, prompt, qa, topic,
    visual strategy, engineering visualization = seven)."""
    return {
        "model": qa_leaderboard(history, "image_model"),
        "workflow": qa_leaderboard(history, "render_profile"),
        "prompt": qa_leaderboard(history, "negative_tokens"),
        "qa": qa_leaderboard(history, "scene_id"),
        "topic": qa_leaderboard(history, "topic"),
        "visual_strategy": qa_leaderboard(history, "shot_type"),
        "engineering_visualization": qa_leaderboard(history, "visualization_type"),
    }


def overall_stats(history: PipelineHistory) -> QualitySummary:
    """The overall deterministic health summary of a run history."""
    scenes = [scene for project in history.projects for scene in project.scenes]
    count = len(scenes)
    passed = sum(1 for scene in scenes if scene.passed)
    qa = [scene.qa_score for scene in scenes]
    educational = [scene.educational_score for scene in scenes]
    attempts = [scene.attempts for scene in scenes]
    durations = [scene.render_duration_ms for scene in scenes]
    vram = [scene.vram_mb for scene in scenes]
    retention = [scene.retention_prediction for scene in scenes]
    switches = sum(scene.model_switches for scene in scenes)
    return QualitySummary(
        scene_count=count,
        passed_scenes=passed,
        failed_scenes=count - passed,
        pass_rate=round(passed / count, 3) if count else 0.0,
        mean_qa=round(sum(qa) / count, 1) if count else 0.0,
        mean_educational=round(sum(educational) / count, 1) if count else 0.0,
        mean_attempts=round(sum(attempts) / count, 2) if count else 0.0,
        total_switches=switches,
        mean_duration_ms=round(sum(durations) / count, 1) if count else 0.0,
        mean_vram_mb=round(sum(vram) / count) if count else 0,
        mean_retention=round(sum(retention) / count, 1) if count else 0.0,
    )
