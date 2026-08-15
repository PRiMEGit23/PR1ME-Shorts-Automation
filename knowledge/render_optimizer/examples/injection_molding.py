"""Worked example 3: injection molding - targeted fixes for a partial failure.

Scene S2 fails QA mostly on educational effectiveness (missing annotations)
and composition (clutter, off-rule framing). The optimizer's plan is
narrow: annotations, composition rule, workflow remains the default hero
profile - no overhaul of the scene.

Run:  python -m knowledge.render_optimizer.examples.injection_molding
"""

from __future__ import annotations

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.image_qa.examples._stack import RenderSpec, default_specs
from knowledge.render_optimizer.examples._stack import print_plan, run_example
from knowledge.visual_architecture import EngineeringDomain, Modality


def main() -> None:
    plan = EducationalDirector().direct_from_csv(INJECTION_ROW)
    result = run_example(
        INJECTION_ROW,
        domain=EngineeringDomain.INJECTION_MOLDING,
        modality=Modality.PHOTOREAL,
        specs=default_specs(plan),
        thumbnail_scene_id="S5",
        renders=[
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
            RenderSpec(scene_id="S5"),
        ],
        run_scene_ids=("S2",),
    )

    print(f"Render optimizer worked example: {result.topic}\n")
    report = result.get_report("S2")
    print(
        f"QA rejected S2: {report.pass_fail.value} overall {report.overall_score} "
        f"(educational {report.educational_score}, composition "
        f"{report.composition_score})\n"
    )
    print_plan("OptimizedRenderPlan for S2", result.get_plan("S2"))

    plan_result = result.get_plan("S2")
    checks = {a.check.value for a in plan_result.optimization_actions}
    assert "educational effectiveness" in checks, "annotations fix must be prescribed"
    assert "visual clutter" in checks, "clutter fix must be prescribed"
    print(
        "\nThe plan targets the two failed checks and leaves the passing "
        "scores untouched."
    )


if __name__ == "__main__":
    main()