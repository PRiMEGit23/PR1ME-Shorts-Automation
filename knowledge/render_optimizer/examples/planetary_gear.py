"""Worked example 2: planetary gears - a broken render gets a full plan.

The Image QA example left scene S2 failing at 76.7 (engineering 56.7,
composition 32.5, consistency 70.0). The optimizer closes the loop: it names
the camera, lighting, composition, visualization and workflow changes, the
exact prompt mutations, and projects the scores after the fixes.

Run:  python -m knowledge.render_optimizer.examples.planetary_gear
"""

from __future__ import annotations

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW
from knowledge.image_qa.examples._stack import RenderSpec, default_specs
from knowledge.render_optimizer.examples._stack import print_plan, run_example
from knowledge.visual_architecture import EngineeringDomain, Modality


def main() -> None:
    plan = EducationalDirector().direct_from_csv(PLANETARY_ROW)
    result = run_example(
        PLANETARY_ROW,
        domain=EngineeringDomain.MECHANISMS,
        modality=Modality.PHOTOREAL,
        specs=default_specs(plan),
        thumbnail_scene_id="S5",
        renders=[
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
            RenderSpec(scene_id="S5"),
        ],
        run_scene_ids=("S2",),
    )

    print(f"Render optimizer worked example: {result.topic}\n")
    report = result.get_report("S2")
    print(
        f"QA rejected S2: {report.pass_fail.value} overall {report.overall_score} "
        f"(engineering {report.engineering_score}, composition "
        f"{report.composition_score}, consistency {report.consistency_score})\n"
    )
    print_plan("OptimizedRenderPlan for S2", result.get_plan("S2"))

    plan_result = result.get_plan("S2")
    expected = plan_result.expected_score_improvement
    assert not expected.predicted_pass or expected.overall >= 75.0
    assert len(plan_result.optimization_actions) >= 5
    assert any(w.profile.value == "cutaway" for w in plan_result.workflow_changes)
    print(
        "\nThe optimizer projects S2 at "
        f"{expected.overall:.1f} (+{expected.improvement:.1f}) - "
        f"predicted pass: {expected.predicted_pass}."
    )


if __name__ == "__main__":
    main()