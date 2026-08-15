"""Engineering critic: does the render get the engineering right?

Five checks: engineering accuracy, geometry correctness, material
correctness, camera suitability, and lighting suitability. The camera and
lighting checks compare the observed render against the storyboard's Camera
and Lighting plans; the correctness checks weigh the observed quality fields
the vision pipeline reported.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.image_qa.qa_models import (
    CriticVerdict,
    GeneratedImageMetadata,
    IssueSeverity,
    QACheck,
    QAIssue,
)
from knowledge.visual_intelligence.storyboard import StoryboardScene, VisualStoryboard


@dataclass(frozen=True)
class QAContext:
    """Everything the critics need to judge one generated image."""

    plan: EducationalPlan
    storyboard: VisualStoryboard
    scene: StoryboardScene
    metadata: GeneratedImageMetadata
    compiled_prompt: CompiledPrompt | None = None


def _scaled(
    check: QACheck,
    value: float,
    *,
    rationale: str,
    floor: float = 0.6,
) -> CriticVerdict:
    score = round(value * 100.0, 1)
    issues: list[QAIssue] = []
    if value < floor:
        issues.append(
            QAIssue(
                check=check,
                severity=IssueSeverity.CRITICAL if value < 0.35 else IssueSeverity.MAJOR,
                message=f"{check.value}: observed quality {value:.2f} is below the "
                f"{floor:.2f} floor",
            )
        )
    return CriticVerdict(check=check, score=score, issues=issues, rationale=rationale)


def _binary(
    check: QACheck,
    ok: bool,
    *,
    rationale: str,
    failure: str,
    severity: IssueSeverity = IssueSeverity.CRITICAL,
) -> CriticVerdict:
    issues = [QAIssue(check=check, severity=severity, message=failure)] if not ok else []
    return CriticVerdict(
        check=check,
        score=100.0 if ok else 0.0,
        issues=issues,
        rationale=rationale,
    )


class EngineeringCritic:
    """Judges the engineering honesty of a generated image."""

    def assess(self, ctx: QAContext) -> list[CriticVerdict]:
        m = ctx.metadata
        return [
            _scaled(
                QACheck.ENGINEERING_ACCURACY,
                m.engineering_accuracy,
                rationale="engineering accuracy as reported by the vision pipeline",
            ),
            _scaled(
                QACheck.GEOMETRY_CORRECTNESS,
                m.geometry_quality if m.geometry_correct else 0.0,
                rationale="geometry quality, zeroed when the render is geometrically wrong",
            ),
            _scaled(
                QACheck.MATERIAL_CORRECTNESS,
                m.material_quality if m.material_correct else 0.0,
                rationale="material plausibility, zeroed when the material is wrong",
            ),
            self._camera(ctx),
            self._lighting(ctx),
        ]

    def _camera(self, ctx: QAContext) -> CriticVerdict:
        m = ctx.metadata
        plan = ctx.scene.camera
        matches = (
            m.camera_distance_matches,
            m.camera_angle_matches,
            m.lens_matches,
        )
        issues = [
            QAIssue(
                check=QACheck.CAMERA_SUITABILITY,
                severity=IssueSeverity.MAJOR,
                message=(
                    f"render camera does not match the plan ({plan.distance.value} / "
                    f"{plan.angle.value} / {plan.lens.value})"
                ),
            )
            for ok, _ in zip(matches, range(3), strict=True)
            if not ok
        ]
        score = round(sum(100.0 if ok else 0.0 for ok in matches) / len(matches), 1)
        return CriticVerdict(
            check=QACheck.CAMERA_SUITABILITY,
            score=score,
            issues=issues,
            rationale="observed camera distance/angle/lens vs the storyboard CameraPlan",
        )

    def _lighting(self, ctx: QAContext) -> CriticVerdict:
        m = ctx.metadata
        plan = ctx.scene.lighting
        matches = (m.lighting_direction_matches, m.lighting_style_matches)
        issues = [
            QAIssue(
                check=QACheck.LIGHTING_SUITABILITY,
                severity=IssueSeverity.MAJOR,
                message=(
                    f"render lighting does not match the plan ({plan.direction.value} / "
                    f"{plan.style.value})"
                ),
            )
            for ok, _ in zip(matches, range(2), strict=True)
            if not ok
        ]
        score = round(sum(100.0 if ok else 0.0 for ok in matches) / len(matches), 1)
        return CriticVerdict(
            check=QACheck.LIGHTING_SUITABILITY,
            score=score,
            issues=issues,
            rationale="observed lighting direction/style vs the storyboard LightingPlan",
        )