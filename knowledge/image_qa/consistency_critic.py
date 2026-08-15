"""Consistency critic: scene continuity and prompt fidelity.

Two checks: scene consistency (the render must not contradict the scene's
world, palette, or consistency tags - reported by the vision pipeline as
violations) and prompt consistency (the compiled prompt must carry the
storyboard's subject and shot intent, checked here deterministically by
matching required terms against the compiled prompt).
"""

from __future__ import annotations

from knowledge.image_qa.engineering_critic import QAContext
from knowledge.image_qa.qa_models import (
    CriticVerdict,
    IssueSeverity,
    QACheck,
    QAIssue,
)

_SCENE_CONSISTENCY_FLOOR = 0.75


def _normalize(text: str) -> str:
    """Collapse hyphen/space variants so 'cross-section' matches 'cross section'."""
    return text.lower().replace("-", " ").replace("_", " ")


class ConsistencyCritic:
    """Judges continuity within the scene and fidelity to the compiled prompt."""

    def assess(self, ctx: QAContext) -> list[CriticVerdict]:
        return [self._scene_consistency(ctx), self._prompt_consistency(ctx)]

    def _scene_consistency(self, ctx: QAContext) -> CriticVerdict:
        m = ctx.metadata
        issues: list[QAIssue] = [
            QAIssue(
                check=QACheck.SCENE_CONSISTENCY,
                severity=IssueSeverity.MAJOR,
                message=f"consistency violation: {violation}",
            )
            for violation in m.consistency_violations
        ]
        if m.scene_consistency < _SCENE_CONSISTENCY_FLOOR:
            issues.append(
                QAIssue(
                    check=QACheck.SCENE_CONSISTENCY,
                    severity=IssueSeverity.MAJOR,
                    message=(
                        f"scene consistency {m.scene_consistency:.2f} is below the "
                        f"{_SCENE_CONSISTENCY_FLOOR:.2f} floor"
                    ),
                )
            )
        penalty = 20.0 * len(m.consistency_violations)
        score = round(max(0.0, m.scene_consistency * 100.0 - penalty), 1)
        return CriticVerdict(
            check=QACheck.SCENE_CONSISTENCY,
            score=score,
            issues=issues,
            rationale="render continuity vs the scene's world, palette, and tags",
        )

    def _prompt_consistency(self, ctx: QAContext) -> CriticVerdict:
        if ctx.compiled_prompt is None:
            return CriticVerdict(
                check=QACheck.PROMPT_CONSISTENCY,
                score=100.0,
                issues=[],
                rationale="no compiled prompt supplied; prompt consistency is neutral",
            )
        # The shot type's first token survives compilation ("hero shot" becomes
        # "hero photograph of"); the full phrase does not, so match the token.
        required = {
            ctx.scene.primary_subject.entity.lower(),
            ctx.scene.intent.shot_type.value.split()[0].lower(),
        }
        for viz in ctx.scene.intent.engineering_visualizations:
            required.add(viz.type.value.lower())
        prompt = _normalize(ctx.compiled_prompt.prompt)
        missing = sorted(term for term in required if _normalize(term) not in prompt)
        issues = (
            [
                QAIssue(
                    check=QACheck.PROMPT_CONSISTENCY,
                    severity=IssueSeverity.MAJOR,
                    message=(
                        f"compiled prompt misses required terms: "
                        f"{', '.join(missing)}"
                    ),
                )
            ]
            if missing
            else []
        )
        score = round(100.0 * (len(required) - len(missing)) / len(required), 1)
        return CriticVerdict(
            check=QACheck.PROMPT_CONSISTENCY,
            score=score,
            issues=issues,
            rationale="required subject/shot/visualization terms present in the prompt",
        )