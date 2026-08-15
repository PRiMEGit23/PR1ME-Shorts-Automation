"""Thumbnail critic: would this image earn the click?

The storyboard already picked the thumbnail scene by score; this critic
checks that the actual render of that scene delivers what a thumbnail needs:
strong contrast, clear focus, and breathing room for the overlay title. A
scene that is not the thumbnail candidate is judged neutrally (100) so it
never drags down a report it does not belong to.
"""

from __future__ import annotations

from knowledge.image_qa.engineering_critic import QAContext
from knowledge.image_qa.qa_models import (
    CriticVerdict,
    IssueSeverity,
    QACheck,
    QAIssue,
)

_CONTRAST_FLOOR = 0.7
_FOCUS_FLOOR = 0.7


class ThumbnailCritic:
    """Judges thumbnail strength for the storyboard's chosen candidate scene."""

    def assess(self, ctx: QAContext) -> CriticVerdict:
        if ctx.scene.scene_id != ctx.storyboard.thumbnail_scene_id:
            return CriticVerdict(
                check=QACheck.THUMBNAIL_STRENGTH,
                score=100.0,
                issues=[],
                rationale="not the thumbnail candidate; judged neutrally",
            )

        m = ctx.metadata
        issues: list[QAIssue] = []
        if m.thumbnail_contrast < _CONTRAST_FLOOR:
            issues.append(
                QAIssue(
                    check=QACheck.THUMBNAIL_STRENGTH,
                    severity=IssueSeverity.MAJOR,
                    message=(
                        f"thumbnail contrast {m.thumbnail_contrast:.2f} is below "
                        f"the {_CONTRAST_FLOOR:.2f} floor"
                    ),
                )
            )
        if m.thumbnail_focus < _FOCUS_FLOOR:
            issues.append(
                QAIssue(
                    check=QACheck.THUMBNAIL_STRENGTH,
                    severity=IssueSeverity.MAJOR,
                    message=(
                        f"thumbnail focus {m.thumbnail_focus:.2f} is below the "
                        f"{_FOCUS_FLOOR:.2f} floor"
                    ),
                )
            )
        if not m.thumbnail_negative_space:
            issues.append(
                QAIssue(
                    check=QACheck.THUMBNAIL_STRENGTH,
                    severity=IssueSeverity.MAJOR,
                    message="no negative space left for the overlay title",
                )
            )

        scores = [
            m.thumbnail_contrast,
            m.thumbnail_focus,
            1.0 if m.thumbnail_negative_space else 0.0,
        ]
        score = round(sum(scores) / len(scores) * 100.0, 1)
        return CriticVerdict(
            check=QACheck.THUMBNAIL_STRENGTH,
            score=score,
            issues=issues,
            rationale="contrast, focus, and title negative space for the candidate",
        )