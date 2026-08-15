"""Success analyzer: what the winning groups look like (Phase 11).

Success profiles are the evidence behind every pattern: for each
dimension (model, shot, lens, light, visualization, profile), how often
a group passed QA and how well it scored. Deterministic - the analyzer
never reorders a group or samples a subset.
"""

from __future__ import annotations

from knowledge.learning_engine.learning_models import (
    PipelineHistory,
    SuccessProfile,
)
from knowledge.learning_engine.quality_statistics import group_rows

#: Dimensions the success analyzer reports.
SUCCESS_DIMENSIONS: tuple[str, ...] = (
    "image_model",
    "shot_type",
    "lens",
    "light_direction",
    "visualization_type",
    "render_profile",
    "topic",
)


def success_profiles(history: PipelineHistory) -> tuple[SuccessProfile, ...]:
    """One profile per (dimension, key) group with enough samples."""
    profiles: list[SuccessProfile] = []
    for dimension in SUCCESS_DIMENSIONS:
        for key, scenes in group_rows(history, dimension).items():
            if not scenes:
                continue
            passed = sum(1 for scene in scenes if scene.passed)
            profiles.append(
                SuccessProfile(
                    dimension=dimension,
                    key=key,
                    passed=passed,
                    total=len(scenes),
                    pass_rate=round(passed / len(scenes), 3),
                    mean_qa=round(
                        sum(scene.qa_score for scene in scenes) / len(scenes), 1
                    ),
                    mean_educational=round(
                        sum(scene.educational_score for scene in scenes)
                        / len(scenes),
                        1,
                    ),
                    scene_ids=tuple(
                        sorted(f"{scene.run_id}:{scene.scene_id}" for scene in scenes)
                    ),
                )
            )
    return tuple(
        sorted(profiles, key=lambda profile: (-profile.pass_rate, -profile.mean_qa, profile.dimension, profile.key))
    )
