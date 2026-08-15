"""Worked example 1: gyroid - a clean render needs no optimization.

The vision pipeline reports a perfect image. QA passes, so the optimizer
prescribes zero actions and predicts the scores stay exactly where they are.
This is the closed-loop happy path: no changes, no workflow switches.

Run:  python -m knowledge.render_optimizer.examples.gyroid
"""

from __future__ import annotations

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.image_qa.examples._stack import RenderSpec, default_specs
from knowledge.render_optimizer.examples._stack import run_example
from knowledge.visual_architecture import EngineeringDomain, Modality


def main() -> None:
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    result = run_example(
        GYROID_ROW,
        domain=EngineeringDomain.FDM,
        modality=Modality.PHOTOREAL,
        specs=default_specs(plan),
        thumbnail_scene_id="S5",
        renders=[RenderSpec(scene_id=f"S{i}") for i in range(1, 6)],
        run_scene_ids=("S1", "S2", "S5"),
    )

    print(f"Render optimizer worked example: {result.topic} (all scenes pass QA)\n")
    for scene_id in ("S1", "S2", "S5"):
        report = result.get_report(scene_id)
        plan = result.get_plan(scene_id)
        print(
            f"scene {scene_id}: QA {report.pass_fail.value} "
            f"({report.overall_score:.1f}) | actions: "
            f"{len(plan.optimization_actions)} | predicted pass: "
            f"{plan.expected_score_improvement.predicted_pass}"
        )
    assert all(
        not result.get_plan(s).optimization_actions for s in ("S1", "S2", "S5")
    ), "a passing image must not be optimized"
    print("\nThe optimizer prescribes nothing for passing images.")


if __name__ == "__main__":
    main()