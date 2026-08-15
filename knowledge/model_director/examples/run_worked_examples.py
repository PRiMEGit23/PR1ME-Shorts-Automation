"""Run all Model Director worked examples.

``python -m knowledge.model_director.examples.run_worked_examples``
"""

from __future__ import annotations

from knowledge.model_director.model_profiles import ModelOutput


def direct_all() -> dict[str, ModelOutput]:
    """Direct every worked-example film; returns topic-keyed ModelOutputs."""
    from knowledge.ai_director import AIDirector
    from knowledge.educational_director import EducationalDirector
    from knowledge.educational_director.examples.gyroid import GYROID_ROW
    from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
    from knowledge.educational_director.examples.planetary_gear import (
        PLANETARY_ROW,
    )
    from knowledge.model_director import ModelDirector

    ed, ad, md = EducationalDirector(), AIDirector(), ModelDirector()
    source_rows = {
        "gyroid": GYROID_ROW,
        "planetary_gear": PLANETARY_ROW,
        "injection_molding": INJECTION_ROW,
    }
    outputs: dict[str, ModelOutput] = {}
    for key, row in source_rows.items():
        outputs[key] = md.direct(ad.direct(ed.direct_from_csv(row)))
    return outputs


def main() -> None:
    for key, output in direct_all().items():
        print(f"== {key} ==")
        print(f"  {output.summary}")
        for plan in output.scene_plans:
            profile = plan.model_profile
            print(
                f"  {plan.scene_id}: {profile.image_model} "
                f"{profile.render_profile.value} qa={plan.expected_qa_score}"
            )


if __name__ == "__main__":
    main()
