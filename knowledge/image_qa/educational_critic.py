"""Educational critic: did the render teach what the Educational Plan asked?

The EducationalPlan declares the visual methods, the cognitive stage, the
attention hook, and the failure mode to defend against. This critic checks the
render against those promises: the planned method is implemented, annotations
exist where the method needs them, a comparison axis is visible when the
strategy is a comparison, and the planned attention hook survives the render.
"""

from __future__ import annotations

from knowledge.educational_director.educational_models import TeachingStrategy
from knowledge.image_qa.engineering_critic import QAContext
from knowledge.image_qa.qa_models import (
    CriticVerdict,
    IssueSeverity,
    QACheck,
    QAIssue,
)

_METHODS_NEEDING_ANNOTATIONS = frozenset(
    {
        "diagram",
        "comparison board",
        "cross section",
        "infographic",
        "stress visualization",
        "thermal visualization",
        "annotated diagram",
    }
)

_COMPARISON_STRATEGIES = frozenset(
    {TeachingStrategy.COMPARISON, TeachingStrategy.BEFORE_AFTER, TeachingStrategy.SCALE_COMPARISON}
)


class EducationalCritic:
    """Judges whether the render fulfills the educational intent."""

    def assess(self, ctx: QAContext) -> CriticVerdict:
        plan = ctx.plan
        m = ctx.metadata

        checks: list[tuple[bool, str, IssueSeverity]] = [
            (
                m.method_implemented,
                f"the planned visual method ({plan.visual_teaching_method[0].value}) "
                "is not visible in the render",
                IssueSeverity.CRITICAL,
            ),
        ]

        method_names = {method.value for method in plan.visual_teaching_method}
        if method_names & _METHODS_NEEDING_ANNOTATIONS:
            checks.append(
                (
                    m.annotations_present,
                    "the method needs engineering annotations and none are visible",
                    IssueSeverity.MAJOR,
                )
            )
            if m.annotation_quality < 0.6:
                checks.append(
                    (
                        False,
                        f"annotation quality {m.annotation_quality:.2f} is below the 0.60 floor",
                        IssueSeverity.MAJOR,
                    )
                )

        if plan.teaching_strategy in _COMPARISON_STRATEGIES:
            checks.append(
                (
                    m.comparison_axis_present,
                    "a comparison strategy without a visible comparison axis cannot teach",
                    IssueSeverity.CRITICAL,
                )
            )

        issues = [
            QAIssue(check=QACheck.EDUCATIONAL_EFFECTIVENESS, severity=severity, message=msg)
            for ok, msg, severity in checks
            if not ok
        ]
        failures = sum(1 for ok, _, _ in checks if not ok)
        score = round(100.0 * (len(checks) - failures) / len(checks), 1)
        rationale = (
            f"render fulfills {len(checks) - failures}/{len(checks)} educational "
            f"promises of the {plan.teaching_strategy.value} strategy"
        )
        return CriticVerdict(
            check=QACheck.EDUCATIONAL_EFFECTIVENESS,
            score=score,
            issues=issues,
            rationale=rationale,
        )