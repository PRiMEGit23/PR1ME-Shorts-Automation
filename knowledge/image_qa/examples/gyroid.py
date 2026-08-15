"""Worked example 1: gyroid infill - a clean render passes QA.

Full stack: EducationalPlan from the curated CSV row, storyboard + compiled
prompts from the shared builder, and a vision report describing a faithful
render. Every score should be high and the image should PASS.

Run:  python -m knowledge.image_qa.examples.gyroid
"""

from __future__ import annotations

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.image_qa.examples._stack import (
    RenderSpec,
    build_stack,
    default_specs,
)
from knowledge.image_qa.image_critic import ImageCritic, QAContext
from knowledge.visual_architecture import EngineeringDomain, Modality

_TOPIC = "Infill Pattern Comparisons"


def main() -> None:
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    specs = default_specs(plan)
    renders = [
        RenderSpec(scene_id="S1"),
        RenderSpec(
            scene_id="S2",
            subject_prominence=0.95,
            annotation_quality=0.9,
        ),
        RenderSpec(scene_id="S3", annotations_present=True),
        RenderSpec(
            scene_id="S4",
            comparison_axis_present=True,
            composition_rule_matches=True,
        ),
        RenderSpec(
            scene_id="S5",
            thumbnail_contrast=0.9,
            thumbnail_focus=0.9,
            thumbnail_negative_space=True,
        ),
    ]
    storyboard, prompts, metadata = build_stack(
        plan,
        domain=EngineeringDomain.FDM,
        modality=Modality.PHOTOREAL,
        specs=specs,
        thumbnail_scene_id="S5",
        renders=renders,
    )

    critic = ImageCritic()
    print(f"Image QA worked example: {_TOPIC}\n")
    for scene in storyboard.scenes:
        ctx = QAContext(
            plan=plan,
            storyboard=storyboard,
            scene=scene,
            metadata=metadata[scene.scene_id],
            compiled_prompt=prompts["scenes"][scene.scene_id],
        )
        report = critic.assess(ctx, topic=_TOPIC)
        print(f"--- Scene {report.scene_id} ---")
        print(
            f"  overall={report.overall_score:>5}  eng={report.engineering_score:>5}  "
            f"edu={report.educational_score:>5}  comp={report.composition_score:>5}  "
            f"hier={report.subject_hierarchy_score:>5}  clarity={report.visual_clarity_score:>5}  "
            f"thumb={report.thumbnail_score:>5}  cons={report.consistency_score:>5}  "
            f"verdict={report.pass_fail.value}"
        )


if __name__ == "__main__":
    main()