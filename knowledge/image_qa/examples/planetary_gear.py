"""Worked example 2: planetary gears - a broken render fails QA with repairs.

The Educational Director asked for a transparent housing, but the vision
pipeline reports: subject occluded, wrong material (aluminium instead of
steel), a mismatched camera, and clutter. The report must FAIL and the repair
engine must name deterministic fixes - without re-rendering anything.

Run:  python -m knowledge.image_qa.examples.planetary_gear
"""

from __future__ import annotations

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW
from knowledge.image_qa.examples._stack import (
    RenderSpec,
    build_stack,
    default_specs,
)
from knowledge.image_qa.image_critic import ImageCritic, QAContext
from knowledge.visual_architecture import EngineeringDomain, Modality

_TOPIC = "Planetary Gears"


def main() -> None:
    plan = EducationalDirector().direct_from_csv(PLANETARY_ROW)
    specs = default_specs(plan)
    renders = [
        RenderSpec(scene_id="S1"),
        RenderSpec(
            scene_id="S2",
            subject_occluded=True,
            subject_prominence=0.4,
            material_correct=False,
            material_quality=0.3,
            camera_distance_matches=False,
            lens_matches=False,
            clutter_level=0.7,
            composition_quality=0.5,
            composition_rule_matches=False,
            lighting_direction_matches=False,
            scene_consistency=0.6,
            consistency_violations=["housing changed from steel to aluminium"],
        ),
        RenderSpec(scene_id="S3"),
        RenderSpec(scene_id="S4"),
        RenderSpec(
            scene_id="S5",
            thumbnail_contrast=0.5,
            thumbnail_focus=0.6,
            thumbnail_negative_space=False,
        ),
    ]
    storyboard, prompts, metadata = build_stack(
        plan,
        domain=EngineeringDomain.MECHANISMS,
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

    print(f"Image QA worked example: {_TOPIC} (scene S2, broken render)\n")
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