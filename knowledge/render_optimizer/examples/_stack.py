"""Shared optimizer example runner: QA stack + optimizer in one call.

Reuses the Image QA example stack (storyboard + compiled prompts + simulated
render metadata) and runs it through ImageCritic and OptimizationEngine, so
each worked example reads top to bottom: the render fails QA, the optimizer
prescribes fixes, and the plan shows predicted scores.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW
from knowledge.image_qa.examples._stack import (
    RenderSpec,
    SceneSpec,
    build_stack,
)
from knowledge.image_qa.image_critic import ImageCritic, QAContext
from knowledge.image_qa.qa_models import ImageQualityReport
from knowledge.render_optimizer import OptimizationEngine, OptimizedRenderPlan
from knowledge.visual_architecture import EngineeringDomain, Modality

_CRITIC = ImageCritic()
_ENGINE = OptimizationEngine()


@dataclass(frozen=True)
class OptimizerResult:
    """Everything one example run produces, in order."""

    topic: str
    plan: EducationalPlan
    storyboard: object
    prompts: dict[str, object]
    metadata: dict[str, object]
    reports: dict[str, ImageQualityReport]
    plans: dict[str, OptimizedRenderPlan]

    def get_report(self, scene_id: str) -> ImageQualityReport:
        return self.reports[scene_id]

    def get_plan(self, scene_id: str) -> OptimizedRenderPlan:
        return self.plans[scene_id]


def run_example(
    row: dict[str, str],
    *,
    domain: EngineeringDomain,
    modality: Modality,
    specs: list[SceneSpec],
    thumbnail_scene_id: str,
    renders: list[RenderSpec],
    run_scene_ids: tuple[str, ...],
) -> OptimizerResult:
    """Run QA then optimization for one topic; optimize the listed scenes."""
    plan = EducationalDirector().direct_from_csv(row)
    storyboard, prompts, metadata = build_stack(
        plan,
        domain=domain,
        modality=modality,
        specs=specs,
        thumbnail_scene_id=thumbnail_scene_id,
        renders=renders,
    )
    reports: dict[str, ImageQualityReport] = {}
    plans: dict[str, OptimizedRenderPlan] = {}
    for spec in renders:
        scene = next(s for s in storyboard.scenes if s.scene_id == spec.scene_id)
        ctx = QAContext(
            plan=plan,
            storyboard=storyboard,
            scene=scene,
            compiled_prompt=prompts["scenes"][spec.scene_id],
            metadata=metadata[spec.scene_id],
        )
        report = _CRITIC.assess(ctx, topic=plan.topic)
        reports[spec.scene_id] = report
        if spec.scene_id in run_scene_ids:
            plans[spec.scene_id] = _ENGINE.optimize(
                report,
                scene=scene,
                compiled_prompt=prompts["scenes"][spec.scene_id],
            )
    return OptimizerResult(
        topic=plan.topic,
        plan=plan,
        storyboard=storyboard,
        prompts=prompts,
        metadata=metadata,
        reports=reports,
        plans=plans,
    )


def print_plan(label: str, plan: OptimizedRenderPlan) -> None:
    """Compact, deterministic summary of one plan for the examples."""
    expected = plan.expected_score_improvement
    print(f"== {label} ==")
    print(
        f"  predicted overall {expected.overall:.1f} "
        f"(+{expected.improvement:.1f}) | predicted pass: {expected.predicted_pass}"
    )
    for action in plan.optimization_actions:
        print(
            f"  - [{action.kind.value}] {action.check.value}: {action.instruction} "
            f"(+{action.expected_gain:.0f} {action.target_score})"
        )
    for change in plan.workflow_changes:
        print(f"  * workflow: {change.profile.value}")
    for change in plan.visualization_changes:
        print(f"  * visualization: {change.type.value}")
    for change in plan.camera_changes:
        fields = change.model_dump(exclude={"rationale"})
        print(f"  * camera: {fields}")
    for change in plan.lighting_changes:
        fields = change.model_dump(exclude={"rationale"})
        print(f"  * lighting: {fields}")
    for change in plan.composition_changes:
        fields = change.model_dump(exclude={"rationale"})
        print(f"  * composition: {fields}")



EXAMPLE_ROWS = {
    "gyroid": GYROID_ROW,
    "planetary_gear": PLANETARY_ROW,
    "injection_molding": INJECTION_ROW,
}