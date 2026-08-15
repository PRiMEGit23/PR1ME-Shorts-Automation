"""Image QA engine: aggregate the critics into one accept/reject decision.

The ImageCritic runs every critic over the same QAContext, collects the
verdicts, aggregates the eight scores with fixed weights, applies the
pass/fail thresholds, and asks the RenderRepairEngine for deterministic
repair instructions. Pure and deterministic: the same inputs always produce
the same report, and nothing is re-rendered automatically.
"""

from __future__ import annotations

from knowledge.image_qa.composition_critic import CompositionCritic
from knowledge.image_qa.consistency_critic import ConsistencyCritic
from knowledge.image_qa.educational_critic import EducationalCritic
from knowledge.image_qa.engineering_critic import EngineeringCritic, QAContext
from knowledge.image_qa.qa_models import (
    FAIL_FLOOR,
    PASS_THRESHOLD,
    CriticVerdict,
    GeneratedImageMetadata,
    ImageQualityReport,
    IssueSeverity,
    PassFail,
    QACheck,
)
from knowledge.image_qa.render_repair import RenderRepairEngine
from knowledge.image_qa.thumbnail_critic import ThumbnailCritic

#: The eight report scores, from the verdicts they aggregate over.
_ENGINEERING_CHECKS = (
    QACheck.ENGINEERING_ACCURACY,
    QACheck.GEOMETRY_CORRECTNESS,
    QACheck.MATERIAL_CORRECTNESS,
    QACheck.CAMERA_SUITABILITY,
    QACheck.LIGHTING_SUITABILITY,
)
_COMPOSITION_CHECKS = (
    QACheck.PRIMARY_SUBJECT_VISIBILITY,
    QACheck.SUBJECT_HIERARCHY,
    QACheck.COMPOSITION_QUALITY,
    QACheck.VISUAL_CLUTTER,
)

_WEIGHTS = {
    "engineering": 0.20,
    "educational": 0.20,
    "composition": 0.15,
    "subject_hierarchy": 0.10,
    "visual_clarity": 0.10,
    "thumbnail": 0.10,
    "consistency": 0.15,
}


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 1)


class ImageCritic:
    """The orchestrator: run all critics, aggregate, decide, suggest repairs."""

    def __init__(
        self,
        *,
        engineering: EngineeringCritic | None = None,
        educational: EducationalCritic | None = None,
        composition: CompositionCritic | None = None,
        consistency: ConsistencyCritic | None = None,
        thumbnail: ThumbnailCritic | None = None,
        repairs: RenderRepairEngine | None = None,
    ) -> None:
        self._engineering = engineering or EngineeringCritic()
        self._educational = educational or EducationalCritic()
        self._composition = composition or CompositionCritic()
        self._consistency = consistency or ConsistencyCritic()
        self._thumbnail = thumbnail or ThumbnailCritic()
        self._repairs = repairs or RenderRepairEngine()

    def assess(
        self,
        ctx: QAContext,
        *,
        topic: str,
    ) -> ImageQualityReport:
        """Produce the full QA report for one generated image."""
        verdicts = self._verdicts(ctx)

        def score_of(check: QACheck) -> float:
            return next(v.score for v in verdicts if v.check is check)

        engineering = _mean([score_of(c) for c in _ENGINEERING_CHECKS])
        educational = score_of(QACheck.EDUCATIONAL_EFFECTIVENESS)
        composition = _mean([score_of(c) for c in _COMPOSITION_CHECKS])
        subject_hierarchy = score_of(QACheck.SUBJECT_HIERARCHY)
        visual_clarity = round(ctx.metadata.visual_clarity * 100.0, 1)
        thumbnail = score_of(QACheck.THUMBNAIL_STRENGTH)
        consistency = _mean(
            [
                score_of(QACheck.SCENE_CONSISTENCY),
                score_of(QACheck.PROMPT_CONSISTENCY),
            ]
        )

        overall = round(
            _WEIGHTS["engineering"] * engineering
            + _WEIGHTS["educational"] * educational
            + _WEIGHTS["composition"] * composition
            + _WEIGHTS["subject_hierarchy"] * subject_hierarchy
            + _WEIGHTS["visual_clarity"] * visual_clarity
            + _WEIGHTS["thumbnail"] * thumbnail
            + _WEIGHTS["consistency"] * consistency,
            1,
        )

        issues = [issue for v in verdicts for issue in v.issues]
        failed = overall < PASS_THRESHOLD or any(
            score < FAIL_FLOOR
            for score in (
                engineering,
                educational,
                composition,
                subject_hierarchy,
                visual_clarity,
                thumbnail,
                consistency,
            )
        ) or any(issue.severity is IssueSeverity.CRITICAL for issue in issues)
        pass_fail = PassFail.FAIL if failed else PassFail.PASS

        return ImageQualityReport(
            topic=topic,
            scene_id=ctx.scene.scene_id,
            overall_score=overall,
            engineering_score=engineering,
            educational_score=educational,
            composition_score=composition,
            subject_hierarchy_score=subject_hierarchy,
            visual_clarity_score=visual_clarity,
            thumbnail_score=thumbnail,
            consistency_score=consistency,
            pass_fail=pass_fail,
            issues=issues,
            repair_suggestions=self._repairs.suggest(issues),
        )

    def _verdicts(self, ctx: QAContext) -> list[CriticVerdict]:
        return [
            *self._engineering.assess(ctx),
            self._educational.assess(ctx),
            *self._composition.assess(ctx),
            *self._consistency.assess(ctx),
            self._thumbnail.assess(ctx),
        ]


__all__ = ["ImageCritic", "QAContext", "GeneratedImageMetadata"]