"""Improvement generator: patterns + statistics -> reviewable proposals (Phase 11).

Every pattern becomes a typed proposal (model / director / compiler /
workflow / knowledge); measured failure drives optimizer proposals; and
measured-vs-predicted QA gaps drive calibration knowledge proposals.
Nothing here writes to the knowledge base - every proposal is
reviewable, evidence-backed, and deterministically ordered.
"""

from __future__ import annotations

from knowledge.learning_engine.learning_models import (
    FailureProfile,
    ImprovementProposal,
    PatternObservation,
    PipelineHistory,
    Proposal,
    QualitySummary,
    SuccessProfile,
)
from knowledge.learning_engine.learning_rules import (
    AFFECTED_MODULES,
    CALIBRATION_ATTENUATION,
    MAX_EVIDENCE_SCENES,
    MAX_PROPOSALS,
    MIN_CALIBRATION_DELTA_QA,
    MIN_CONFIDENCE,
    MIN_FAILED_FOR_OPTIMIZER,
    MIN_GROUP_SAMPLES,
    OPTIMIZER_SUGGESTIONS,
)
from knowledge.model_director.model_registry import REGISTRY
from knowledge.model_director.quality_predictor import axis_for_shot


def generate_proposals(
    history: PipelineHistory,
    patterns: tuple[PatternObservation, ...],
    failure_profiles: tuple[FailureProfile, ...],
    success_profiles: tuple[SuccessProfile, ...],
    overall: QualitySummary,
) -> tuple[Proposal, ...]:
    """Every deterministic proposal the history supports, capped and sorted."""
    del success_profiles, overall  # reserved inputs; proposals need patterns only
    proposals: list[ImprovementProposal] = []
    proposals.extend(_calibration_proposals(history))
    proposals.extend(_pattern_proposals(patterns))
    proposals.extend(_optimizer_proposals(failure_profiles))
    return _order(_dedupe(proposals))


def _pattern_proposals(patterns: tuple[PatternObservation, ...]) -> list[ImprovementProposal]:
    """One proposal per pattern, typed by its dimension."""
    from knowledge.learning_engine.learning_models import (
        CompilerRecommendation,
        DirectorRecommendation,
        KnowledgeProposal,
        ModelRecommendation,
        WorkflowRecommendation,
    )

    proposals: list[ImprovementProposal] = []
    for pattern in patterns:
        if pattern.confidence < MIN_CONFIDENCE:
            continue
        modules = AFFECTED_MODULES.get(pattern.dimension, ())
        scope = "across topics"
        evidence = pattern.evidence_scenes
        gain = (
            f"+{pattern.delta:.1f} mean {pattern.metric} "
            f"over {pattern.winner_count} scenes"
        )
        if pattern.dimension in ("image_model", "video_model"):
            proposals.append(
                ModelRecommendation(
                    title=f"Adopt {pattern.winner} for {scope}",
                    summary=pattern.description,
                    confidence=pattern.confidence,
                    evidence=evidence,
                    affected_modules=modules,
                    predicted_improvement=gain,
                    reason=(
                        f"measured {pattern.metric} lead of {pattern.delta:.2f} "
                        f"({pattern.winner_count} samples)"
                    ),
                    scope_key=scope,
                    from_model="(all others)",
                    to_model=pattern.winner,
                    predicted_qa_gain=round(max(0.0, pattern.delta), 2),
                )
            )
        elif pattern.dimension == "render_profile":
            proposals.append(
                WorkflowRecommendation(
                    title=f"Prefer the {pattern.winner} render profile for {scope}",
                    summary=pattern.description,
                    confidence=pattern.confidence,
                    evidence=evidence,
                    affected_modules=modules,
                    predicted_improvement=gain,
                    reason=(
                        f"measured {pattern.metric} lead of {pattern.delta:.2f} "
                        f"({pattern.winner_count} samples)"
                    ),
                    scope_key=scope,
                    current_profile="(all others)",
                    suggested_profile=pattern.winner,
                    predicted_qa_gain=round(max(0.0, pattern.delta), 2),
                )
            )
        elif pattern.dimension == "negative_tokens":
            proposals.append(
                CompilerRecommendation(
                    title=f"Adopt the winning negative-token pattern {pattern.winner!r}",
                    summary=pattern.description,
                    confidence=pattern.confidence,
                    evidence=evidence,
                    affected_modules=modules,
                    predicted_improvement=gain,
                    reason=(
                        f"measured {pattern.metric} lead of {pattern.delta:.2f} "
                        f"({pattern.winner_count} samples)"
                    ),
                    prompt_field="negative",
                    token=pattern.winner,
                    context="across topics",
                )
            )
        elif pattern.dimension == "topic":
            proposals.append(
                KnowledgeProposal(
                    title=f"Benchmark topic {pattern.winner!r} as a top performer",
                    summary=pattern.description,
                    confidence=pattern.confidence,
                    evidence=evidence,
                    affected_modules=modules,
                    predicted_improvement=gain,
                    reason=(
                        f"measured {pattern.metric} lead of {pattern.delta:.2f} "
                        f"({pattern.winner_count} samples)"
                    ),
                    knowledge_table="assets/knowledge_base.csv",
                    entry_key=pattern.winner,
                    field="qa_benchmark",
                    before="<unmeasured>",
                    after=f"{pattern.rest_mean + pattern.delta:.1f}",
                )
            )
        else:
            area = {
                "shot_type": "shot selection",
                "lens": "lens",
                "light_direction": "lighting",
                "transition_type": "transition",
                "visualization_type": "engineering visualization",
                "camera_distance": "camera distance",
                "camera_angle": "camera angle",
                "framing": "framing",
            }[pattern.dimension]
            proposals.append(
                DirectorRecommendation(
                    title=f"Prefer {pattern.winner} ({area}) for {scope}",
                    summary=pattern.description,
                    confidence=pattern.confidence,
                    evidence=evidence,
                    affected_modules=modules,
                    predicted_improvement=gain,
                    reason=(
                        f"measured {pattern.metric} lead of {pattern.delta:.2f} "
                        f"({pattern.winner_count} samples)"
                    ),
                    area=area,
                    scope_key=scope,
                    current_value="(all others)",
                    suggested_value=pattern.winner,
                )
            )
    return proposals


def _calibration_proposals(history: PipelineHistory) -> list[ImprovementProposal]:
    """Calibrate registry capabilities when observed QA diverges from predicted.

    For every (image model, shot type) pair with enough samples and a gap
    of at least ``MIN_CALIBRATION_DELTA_QA``, propose moving the axis the
    shot leans on half-way toward the observed reality - attenuated so a
    small sample never overcorrects.
    """
    from knowledge.learning_engine.learning_models import KnowledgeProposal
    from knowledge.learning_engine.quality_statistics import group_rows

    proposals: list[ImprovementProposal] = []
    for model_key, scenes in group_rows(history, "image_model").items():
        if len(scenes) < MIN_GROUP_SAMPLES:
            continue
        per_shot: dict[str, list] = {}
        for scene in scenes:
            per_shot.setdefault(scene.shot_type.value, []).append(scene)
        for shot_scenes in per_shot.values():
            if len(shot_scenes) < MIN_GROUP_SAMPLES:
                continue
            observed = sum(scene.qa_score for scene in shot_scenes) / len(shot_scenes)
            predicted = sum(scene.predicted_qa for scene in shot_scenes) / len(
                shot_scenes
            )
            residual = observed - predicted
            if abs(residual) < MIN_CALIBRATION_DELTA_QA:
                continue
            shot_type = shot_scenes[0].shot_type
            axis = axis_for_shot(shot_type)
            spec = REGISTRY.get(model_key)
            current = getattr(spec, axis)
            adjusted = round(
                min(100.0, max(0.0, current + CALIBRATION_ATTENUATION * residual)), 1
            )
            evidence = sorted(
                f"{scene.run_id}:{scene.scene_id}" for scene in shot_scenes
            )[:MAX_EVIDENCE_SCENES]
            proposals.append(
                KnowledgeProposal(
                    title=(
                        f"Recalibrate {model_key} {axis} from observed "
                        f"{shot_type.value} QA"
                    ),
                    summary=(
                        f"Observed QA for {shot_type.value} scenes on {model_key} "
                        f"averages {observed:.1f} vs {predicted:.1f} predicted "
                        f"({residual:+.1f}) over {len(shot_scenes)} scenes."
                    ),
                    confidence=round(
                        min(0.9, 0.5 + max(0, len(shot_scenes) - 3) * 0.05), 2
                    ),
                    evidence=tuple(evidence),
                    affected_modules=(
                        "knowledge/model_director/model_registry.py",
                    ),
                    predicted_improvement=(
                        f"closes {residual:+.1f} QA gap "
                        f"(attenuated x{CALIBRATION_ATTENUATION})"
                    ),
                    reason=(
                        f"predicted {predicted:.1f}, observed {observed:.1f} "
                        f"over {len(shot_scenes)} scenes"
                    ),
                    knowledge_table="model_registry",
                    entry_key=model_key,
                    field=axis,
                    before=f"{current:.1f}",
                    after=f"{adjusted:.1f}",
                )
            )
    return proposals


def _optimizer_proposals(failure_profiles: tuple) -> list[ImprovementProposal]:
    """Failure-driven optimizer proposals (never guessed, always measured)."""
    from knowledge.learning_engine.learning_models import OptimizationRecommendation

    proposals: list[ImprovementProposal] = []
    for profile in failure_profiles:
        if profile.failed < MIN_FAILED_FOR_OPTIMIZER:
            continue
        if profile.total_switches > 0:
            key, current, suggested = OPTIMIZER_SUGGESTIONS[0]
            trigger = (
                f"{profile.total_switches} model switches in "
                f"{profile.failed} failed {profile.dimension} scenes "
                f"({profile.key})"
            )
        else:
            key, current, suggested = OPTIMIZER_SUGGESTIONS[1]
            trigger = (
                f"{profile.failed} failed {profile.dimension} scenes "
                f"({profile.key}) with no model switch"
            )
        proposals.append(
            OptimizationRecommendation(
                title=f"{suggested} ({profile.dimension}: {profile.key})",
                summary=(
                    f"{profile.failed}/{profile.total} {profile.key} scenes "
                    f"failed QA ({profile.failure_rate:.0%}), averaging "
                    f"{profile.mean_attempts} attempts"
                ),
                confidence=round(
                    min(0.9, 0.5 + max(0, profile.failed - 3) * 0.05), 2
                ),
                evidence=profile.scene_ids,
                affected_modules=("runtime/render_loop.py",),
                predicted_improvement=(
                    f"recovers up to {profile.failure_rate:.0%} of "
                    f"{profile.failed} failing scenes"
                ),
                reason=f"measured failure profile: {trigger}",
                trigger=trigger,
                optimizer_rule=key,
                current_value=current,
                suggested_value=suggested,
            )
        )
    return proposals


def _dedupe(proposals: list[ImprovementProposal]) -> list[ImprovementProposal]:
    seen: set[tuple] = set()
    unique: list[ImprovementProposal] = []
    for proposal in proposals:
        signature = (proposal.kind.value, proposal.title)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(proposal)
    return unique


def _order(proposals: list[ImprovementProposal]) -> tuple[Proposal, ...]:
    from typing import cast

    return cast(
        tuple[Proposal, ...],
        tuple(
            sorted(
                proposals,
                key=lambda proposal: (
                    -proposal.confidence,
                    proposal.kind.value,
                    proposal.title,
                ),
            )
        )[:MAX_PROPOSALS],
    )
