"""Worked example 3: injection molding - partial defects get targeted repairs.

The manufacturing-sequence method was implemented, but the thermal
visualization lacks annotations and the frame is cluttered, so the report
must FAIL at the educational check and return the exact deterministic repairs.

Run:  python -m knowledge.image_qa.examples.injection_molding
"""

from __future__ import annotations

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.image_qa.examples._stack import (
    RenderSpec,
    build_stack,
    default_specs,
)
from knowledge.image_qa.image_critic import ImageCritic, QAContext
from knowledge.visual_architecture import EngineeringDomain, Modality

_TOPIC = "Injection Molding"


def main() -> None:
    plan = EducationalDirector().direct_from_csv(INJECTION_ROW)
    specs = default_specs(plan)
    renders = [
        RenderSpec(scene_id="S1"),
        RenderSpec(
            scene_id="S2",
            annotations_present=False,
            annotation_quality=0.2,
            clutter_level=0.55,
            composition_quality=0.5,
            composition_rule_matches=False,
        ),
        RenderSpec(scene_id="S3"),
        RenderSpec(scene_id="S4"),
        RenderSpec(
            scene_id="S5",
            thumbnail_contrast=0.85,
            thumbnail_focus=0.8,
            thumbnail_negative_space=True,
        ),
    ]
    storyboard, prompts, metadata = build_stack(
        plan,
        domain=EngineeringDomain.INJECTION_MOLDING,
        modality=Modality.PHOTOREAL,
        specs=specs,
        thumbnail_scene_id="S5",
        renders=renders,
    )

    critic = ImageCritic()
    scene = next(s for s in storyboard.scenes if s.scene_id == "S2")
    ctx = QAContext(
        plan=plan,
        storyboard=storyboard,
        scene=scene,
        metadata=metadata["S2"],
        compiled_prompt=prompts["scenes"]["S2"],
    )
    report = critic.assess(ctx, topic=_TOPIC)

    print(f"Image QA worked example: {_TOPIC} (scene S2, annotation/clutter defects)\n")
    print(f"overall score : {report.overall_score}")
    print(f"engineering   : {report.engineering_score}")
    print(f"educational   : {report.educational_score}")
    print(f"composition   : {report.composition_score}")
    print(f"hierarchy     : {report.subject_hierarchy_score}")
    print(f"clarity       : {report.visual_clarity_score}")
    print(f"thumbnail     : {report.thumbnail_score}")
    print(f"consistency   : {report.consistency_score}")
    print(f"verdict       : {report.pass_fail.value}")
    print("\nIssues:")
    for issue in report.issues:
        print(f"  [{issue.severity.value}] {issue.check.value}: {issue.message}")
    print("\nRepair suggestions (deterministic, no auto re-render):")
    for suggestion in report.repair_suggestions:
        print(f"  - {suggestion}")


if __name__ == "__main__":
    main()