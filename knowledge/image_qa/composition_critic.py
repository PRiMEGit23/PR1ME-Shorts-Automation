"""Composition critic: framing, clutter, and whether the eye lands correctly.

Checks: primary subject visibility (is the subject present, prominent, and
unoccluded), subject hierarchy (does the primary subject dominate as the
storyboard planned), composition quality (does the render follow the planned
rule), and visual clutter (is the frame clean enough for a 9:16 short).
"""

from __future__ import annotations

from knowledge.image_qa.engineering_critic import QAContext
from knowledge.image_qa.qa_models import (
    CriticVerdict,
    IssueSeverity,
    QACheck,
    QAIssue,
)


class CompositionCritic:
    """Judges framing quality, subject dominance, and visual cleanliness."""

    def assess(self, ctx: QAContext) -> list[CriticVerdict]:
        return [
            self._primary_subject(ctx),
            self._subject_hierarchy(ctx),
            self._composition(ctx),
            self._clutter(ctx),
        ]

    def _primary_subject(self, ctx: QAContext) -> CriticVerdict:
        m = ctx.metadata
        issues: list[QAIssue] = []
        if not m.subject_present:
            issues.append(
                QAIssue(
                    check=QACheck.PRIMARY_SUBJECT_VISIBILITY,
                    severity=IssueSeverity.CRITICAL,
                    message=(
                        f"the primary subject ({ctx.scene.primary_subject.entity}) "
                        "is absent from the render"
                    ),
                )
            )
        if m.subject_occluded:
            issues.append(
                QAIssue(
                    check=QACheck.PRIMARY_SUBJECT_VISIBILITY,
                    severity=IssueSeverity.CRITICAL,
                    message="the primary subject is occluded",
                )
            )
        if m.subject_prominence < 0.6:
            issues.append(
                QAIssue(
                    check=QACheck.PRIMARY_SUBJECT_VISIBILITY,
                    severity=IssueSeverity.MAJOR,
                    message=(
                        f"subject prominence {m.subject_prominence:.2f} is below the "
                        "0.60 floor"
                    ),
                )
            )
        ok = m.subject_present and not m.subject_occluded and m.subject_prominence >= 0.6
        score = 100.0 if ok else 0.0
        return CriticVerdict(
            check=QACheck.PRIMARY_SUBJECT_VISIBILITY,
            score=score,
            issues=issues,
            rationale="subject presence, occlusion, and prominence vs the storyboard",
        )

    def _subject_hierarchy(self, ctx: QAContext) -> CriticVerdict:
        m = ctx.metadata
        issues = (
            [
                QAIssue(
                    check=QACheck.SUBJECT_HIERARCHY,
                    severity=IssueSeverity.MAJOR,
                    message="the primary subject does not dominate the frame as planned",
                )
            ]
            if not m.hierarchy_clear
            else []
        )
        return CriticVerdict(
            check=QACheck.SUBJECT_HIERARCHY,
            score=100.0 if m.hierarchy_clear else 0.0,
            issues=issues,
            rationale="whether the primary subject leads the eye as directed",
        )

    def _composition(self, ctx: QAContext) -> CriticVerdict:
        m = ctx.metadata
        issues: list[QAIssue] = []
        if not m.composition_rule_matches:
            issues.append(
                QAIssue(
                    check=QACheck.COMPOSITION_QUALITY,
                    severity=IssueSeverity.MAJOR,
                    message=(
                        f"render does not follow the planned composition "
                        f"({ctx.scene.composition.rule.value})"
                    ),
                )
            )
        if m.composition_quality < 0.6:
            issues.append(
                QAIssue(
                    check=QACheck.COMPOSITION_QUALITY,
                    severity=IssueSeverity.MAJOR,
                    message=(
                        f"composition quality {m.composition_quality:.2f} is below "
                        "the 0.60 floor"
                    ),
                )
            )
        ok = m.composition_rule_matches and m.composition_quality >= 0.6
        return CriticVerdict(
            check=QACheck.COMPOSITION_QUALITY,
            score=100.0 if ok else 0.0,
            issues=issues,
            rationale="planned composition rule and observed composition quality",
        )

    def _clutter(self, ctx: QAContext) -> CriticVerdict:
        m = ctx.metadata
        issues = (
            [
                QAIssue(
                    check=QACheck.VISUAL_CLUTTER,
                    severity=IssueSeverity.MAJOR,
                    message=f"visual clutter level {m.clutter_level:.2f} exceeds 0.40",
                )
            ]
            if m.clutter_level > 0.4
            else []
        )
        score = round(100.0 * (1.0 - m.clutter_level), 1)
        return CriticVerdict(
            check=QACheck.VISUAL_CLUTTER,
            score=score,
            issues=issues,
            rationale="clutter is scored inversely: a clean frame scores 100",
        )