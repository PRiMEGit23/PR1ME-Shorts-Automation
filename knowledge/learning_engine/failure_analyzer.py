"""Failure analyzer: why runs and scenes fail, deterministically (Phase 11).

Failure profiles aggregate the losing side of the history: which groups
failed QA, how many attempts they burned, whether the loop switched
models, and how much the optimizer had to prescribe. These numbers drive
the optimization proposals - never a guess, always the measured record.
"""

from __future__ import annotations

from knowledge.learning_engine.learning_models import (
    FailureProfile,
    PipelineHistory,
)
from knowledge.learning_engine.quality_statistics import group_rows

#: Dimensions the failure analyzer reports.
FAILURE_DIMENSIONS: tuple[str, ...] = (
    "image_model",
    "shot_type",
    "lens",
    "light_direction",
    "visualization_type",
    "render_profile",
    "topic",
)


def failure_profiles(history: PipelineHistory) -> tuple[FailureProfile, ...]:
    """One profile per (dimension, key) group with at least one failure."""
    profiles: list[FailureProfile] = []
    for dimension in FAILURE_DIMENSIONS:
        for key, scenes in group_rows(history, dimension).items():
            failed_scenes = [scene for scene in scenes if not scene.passed]
            if not failed_scenes:
                continue
            worst = min(failed_scenes, key=lambda scene: (scene.qa_score, scene.scene_id))
            profiles.append(
                FailureProfile(
                    dimension=dimension,
                    key=key,
                    failed=len(failed_scenes),
                    total=len(scenes),
                    failure_rate=round(len(failed_scenes) / len(scenes), 3),
                    mean_attempts=round(
                        sum(scene.attempts for scene in failed_scenes)
                        / len(failed_scenes),
                        2,
                    ),
                    total_switches=sum(scene.model_switches for scene in failed_scenes),
                    mean_mutations=round(
                        sum(scene.prompt_mutations for scene in failed_scenes)
                        / len(failed_scenes),
                        2,
                    ),
                    mean_actions=round(
                        sum(scene.optimization_actions for scene in failed_scenes)
                        / len(failed_scenes),
                        2,
                    ),
                    worst_qa=worst.qa_score,
                    worst_scene=worst.scene_id,
                    scene_ids=tuple(
                        sorted(f"{scene.run_id}:{scene.scene_id}" for scene in failed_scenes)
                    ),
                )
            )
    return tuple(
        sorted(
            profiles,
            key=lambda profile: (
                -profile.failure_rate,
                -profile.failed,
                profile.dimension,
                profile.key,
            ),
        )
    )


def failed_runs(history: PipelineHistory) -> list[str]:
    """The run ids that never completed (in caller-supplied run order)."""
    return [
        project.run_id
        for project in history.projects
        if project.status != "complete"
    ]
