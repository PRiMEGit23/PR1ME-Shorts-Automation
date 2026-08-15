"""Tests for the Image QA Engine (knowledge/image_qa): the schema, the five
critics, deterministic repair instructions, score aggregation, pass/fail
thresholds, consistency with the report schema, and the three worked
examples (gyroid clean pass, planetary broken render, injection partial
defects)."""

from __future__ import annotations

import pytest
from knowledge.compiler import compile_for_storyboard
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW
from knowledge.image_qa import (
    IMAGE_QA_VERSION,
    GeneratedImageMetadata,
    ImageCritic,
    ImageQualityReport,
    IssueSeverity,
    PassFail,
    QACheck,
    QAContext,
    QAIssue,
    RenderRepairEngine,
)
from knowledge.image_qa.composition_critic import CompositionCritic
from knowledge.image_qa.consistency_critic import ConsistencyCritic
from knowledge.image_qa.educational_critic import EducationalCritic
from knowledge.image_qa.engineering_critic import EngineeringCritic
from knowledge.image_qa.examples._stack import (
    RenderSpec,
    build_stack,
    default_specs,
)
from knowledge.image_qa.qa_models import FAIL_FLOOR, PASS_THRESHOLD
from knowledge.image_qa.thumbnail_critic import ThumbnailCritic
from knowledge.visual_architecture import EngineeringDomain, Modality

_TOPIC = "Infill Pattern Comparisons"
_CRITIC = ImageCritic()


def _context(
    *,
    scene_id: str = "S1",
    metadata: GeneratedImageMetadata | None = None,
    compiled: bool = True,
) -> tuple[QAContext, object]:
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    specs = default_specs(plan)
    renders = [
        RenderSpec(scene_id=f"S{index}") for index, _ in enumerate(specs, start=1)
    ]
    storyboard, prompts, metadata_map = build_stack(
        plan,
        domain=EngineeringDomain.FDM,
        modality=Modality.PHOTOREAL,
        specs=specs,
        thumbnail_scene_id="S5",
        renders=renders,
    )
    scene = next(s for s in storyboard.scenes if s.scene_id == scene_id)
    ctx = QAContext(
        plan=plan,
        storyboard=storyboard,
        scene=scene,
        metadata=metadata or metadata_map[scene_id],
        compiled_prompt=prompts["scenes"][scene_id] if compiled else None,
    )
    return ctx, prompts


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

def test_report_has_all_required_scores() -> None:
    ctx, _ = _context()
    report = _CRITIC.assess(ctx, topic=_TOPIC)
    assert report.version == IMAGE_QA_VERSION
    assert isinstance(report.overall_score, float)
    for name in (
        "engineering_score", "educational_score", "composition_score",
        "subject_hierarchy_score", "visual_clarity_score", "thumbnail_score",
        "consistency_score",
    ):
        value = getattr(report, name)
        assert 0.0 <= value <= 100.0, name
    assert report.pass_fail in PassFail
    assert isinstance(report.repair_suggestions, list)


def test_report_json_round_trip() -> None:
    ctx, _ = _context()
    report = _CRITIC.assess(ctx, topic=_TOPIC)
    loaded = ImageQualityReport.model_validate_json(report.model_dump_json())
    assert loaded == report


def test_metadata_rejects_inconsistent_clutter() -> None:
    with pytest.raises(ValueError):
        GeneratedImageMetadata(
            scene_id="S1", clutter_level=0.8, composition_quality=0.9
        )


def test_metadata_allows_high_clutter_with_bad_composition() -> None:
    m = GeneratedImageMetadata(
        scene_id="S1", clutter_level=0.8, composition_quality=0.4
    )
    assert m.clutter_level == 0.8


def test_metadata_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        GeneratedImageMetadata(scene_id="S1", subject_prominence=1.5)


# --------------------------------------------------------------------------
# engineering critic
# --------------------------------------------------------------------------

def test_engineering_perfect() -> None:
    ctx, _ = _context()
    verdicts = EngineeringCritic().assess(ctx)
    assert all(v.score == 100.0 for v in verdicts)
    assert all(not v.issues for v in verdicts)


def test_engineering_accuracy_scaled() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(scene_id="S1", engineering_accuracy=0.5)
    )
    verdict = EngineeringCritic().assess(ctx)[0]
    assert verdict.score == 50.0
    assert verdict.issues[0].severity is IssueSeverity.MAJOR


def test_geometry_wrong_zeroes_score() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(scene_id="S1", geometry_correct=False)
    )
    verdict = EngineeringCritic().assess(ctx)[1]
    assert verdict.score == 0.0
    assert verdict.issues[0].severity is IssueSeverity.CRITICAL


def test_camera_mismatch_scores_half() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(
            scene_id="S1", camera_distance_matches=False
        )
    )
    verdict = EngineeringCritic().assess(ctx)[3]
    assert verdict.score == round(100.0 * 2 / 3, 1)
    assert verdict.issues[0].check is QACheck.CAMERA_SUITABILITY


def test_lighting_mismatch_scores_half() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(
            scene_id="S1", lighting_style_matches=False
        )
    )
    verdict = EngineeringCritic().assess(ctx)[4]
    assert verdict.score == 50.0


# --------------------------------------------------------------------------
# educational critic
# --------------------------------------------------------------------------

def test_educational_perfect() -> None:
    ctx, _ = _context()
    verdict = EducationalCritic().assess(ctx)
    assert verdict.score == 100.0


def test_educational_missing_method_is_critical() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(scene_id="S1", method_implemented=False)
    )
    verdict = EducationalCritic().assess(ctx)
    assert verdict.score < 100.0
    assert verdict.issues[0].severity is IssueSeverity.CRITICAL


def test_educational_needs_annotations_for_comparison_methods() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(
            scene_id="S2", annotations_present=False
        )
    )
    verdict = EducationalCritic().assess(ctx)
    assert verdict.score < 100.0
    assert any(
        "annotations" in issue.message for issue in verdict.issues
    )


def test_educational_comparison_needs_axis() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(
            scene_id="S4", comparison_axis_present=False
        )
    )
    verdict = EducationalCritic().assess(ctx)
    assert verdict.score < 100.0
    assert verdict.issues[0].severity is IssueSeverity.CRITICAL


# --------------------------------------------------------------------------
# composition critic
# --------------------------------------------------------------------------

def test_composition_perfect() -> None:
    ctx, _ = _context()
    verdicts = CompositionCritic().assess(ctx)
    assert all(v.score == 100.0 for v in verdicts)


def test_absent_subject_critical() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(scene_id="S1", subject_present=False)
    )
    verdict = CompositionCritic().assess(ctx)[0]
    assert verdict.score == 0.0
    assert verdict.issues[0].severity is IssueSeverity.CRITICAL


def test_occluded_subject_critical() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(scene_id="S1", subject_occluded=True)
    )
    verdict = CompositionCritic().assess(ctx)[0]
    assert verdict.score == 0.0


def test_low_prominence_major() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(scene_id="S1", subject_prominence=0.5)
    )
    verdict = CompositionCritic().assess(ctx)[0]
    assert verdict.issues[0].severity is IssueSeverity.MAJOR


def test_clutter_scored_inversely() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(scene_id="S1", clutter_level=0.3)
    )
    verdict = CompositionCritic().assess(ctx)[3]
    assert verdict.score == 70.0
    assert not verdict.issues


def test_hierarchy_mismatch() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(scene_id="S1", hierarchy_clear=False)
    )
    verdict = CompositionCritic().assess(ctx)[1]
    assert verdict.score == 0.0


# --------------------------------------------------------------------------
# consistency critic
# --------------------------------------------------------------------------

def test_consistency_perfect() -> None:
    ctx, _ = _context()
    verdicts = ConsistencyCritic().assess(ctx)
    assert all(v.score == 100.0 for v in verdicts)


def test_consistency_violation_reported() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(
            scene_id="S1", consistency_violations=["palette changed"]
        )
    )
    verdict = ConsistencyCritic().assess(ctx)[0]
    assert verdict.score < 100.0
    assert "palette changed" in verdict.issues[0].message


def test_prompt_consistency_neutral_without_prompt() -> None:
    ctx, _ = _context(compiled=False)
    verdict = ConsistencyCritic().assess(ctx)[1]
    assert verdict.score == 100.0
    assert "neutral" in verdict.rationale


def test_prompt_consistency_requires_shot_terms() -> None:
    ctx, _ = _context(scene_id="S2")
    verdict = ConsistencyCritic().assess(ctx)[1]
    assert verdict.score == 100.0  # the compiled prompt carries the terms


# --------------------------------------------------------------------------
# thumbnail critic
# --------------------------------------------------------------------------

def test_thumbnail_neutral_for_non_candidate() -> None:
    ctx, _ = _context(scene_id="S1")
    verdict = ThumbnailCritic().assess(ctx)
    assert verdict.score == 100.0
    assert "neutral" in verdict.rationale


def test_thumbnail_candidate_scored() -> None:
    ctx, _ = _context(scene_id="S5")
    verdict = ThumbnailCritic().assess(ctx)
    assert verdict.score == 100.0


def test_thumbnail_weak_render_scored() -> None:
    ctx, _ = _context(
        scene_id="S5",
        metadata=GeneratedImageMetadata(
            scene_id="S5",
            thumbnail_contrast=0.4,
            thumbnail_focus=0.5,
            thumbnail_negative_space=False,
        ),
    )
    verdict = ThumbnailCritic().assess(ctx)
    assert verdict.score < 100.0
    assert len(verdict.issues) == 3


# --------------------------------------------------------------------------
# repair engine
# --------------------------------------------------------------------------

def test_repair_table_deterministic() -> None:
    issues = [
        QAIssue(
            check=QACheck.VISUAL_CLUTTER,
            severity=IssueSeverity.MAJOR,
            message="clutter",
        ),
        QAIssue(
            check=QACheck.VISUAL_CLUTTER,
            severity=IssueSeverity.MAJOR,
            message="more clutter",
        ),
    ]
    engine = RenderRepairEngine()
    assert engine.suggest(issues) == ["Remove distracting background"]
    assert engine.suggest_all(issues)[0] == "Remove distracting background"


def test_repair_instructions_cover_spec_examples() -> None:
    engine = RenderRepairEngine()
    examples = {
        "Increase subject prominence": QACheck.PRIMARY_SUBJECT_VISIBILITY,
        "Switch to macro shot": QACheck.CAMERA_SUITABILITY,
        "Remove distracting background": QACheck.VISUAL_CLUTTER,
        "Improve lighting direction": QACheck.LIGHTING_SUITABILITY,
        "Increase engineering annotations": QACheck.EDUCATIONAL_EFFECTIVENESS,
        "Improve comparison framing": QACheck.COMPOSITION_QUALITY,
    }
    for instruction, check in examples.items():
        issues = [
            QAIssue(check=check, severity=IssueSeverity.CRITICAL, message="x")
        ]
        assert instruction in engine.suggest_all(issues), check


def test_repair_never_rerenders() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(
            scene_id="S1",
            subject_present=False,
            engineering_accuracy=0.2,
        )
    )
    report = _CRITIC.assess(ctx, topic=_TOPIC)
    assert report.repair_suggestions  # instructions only
    assert all(isinstance(s, str) for s in report.repair_suggestions)


# --------------------------------------------------------------------------
# aggregation + pass/fail
# --------------------------------------------------------------------------

def test_perfect_render_passes() -> None:
    ctx, _ = _context()
    report = _CRITIC.assess(ctx, topic=_TOPIC)
    assert report.overall_score >= PASS_THRESHOLD
    assert report.pass_fail is PassFail.PASS


def test_critical_issue_fails_even_with_high_overall() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(scene_id="S1", subject_present=False)
    )
    report = _CRITIC.assess(ctx, topic=_TOPIC)
    assert report.pass_fail is PassFail.FAIL
    assert any(
        issue.severity is IssueSeverity.CRITICAL for issue in report.issues
    )


def test_sub_score_below_floor_fails() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(
            scene_id="S1",
            engineering_accuracy=0.1,
            geometry_correct=False,
            material_correct=False,
        )
    )
    report = _CRITIC.assess(ctx, topic=_TOPIC)
    assert report.engineering_score < FAIL_FLOOR
    assert report.pass_fail is PassFail.FAIL


def test_aggregation_weights_apply() -> None:
    ctx, _ = _context(
        metadata=GeneratedImageMetadata(
            scene_id="S1",
            engineering_accuracy=0.5,
            subject_present=False,
        )
    )
    report = _CRITIC.assess(ctx, topic=_TOPIC)
    # engineering = mean(50, 100, 100, 100, 100) = 90
    # composition = mean(0, 100, 100, 100) = 75
    expected = round(
        0.20 * 90.0
        + 0.20 * 100.0
        + 0.15 * 75.0
        + 0.10 * 100.0
        + 0.10 * 100.0
        + 0.10 * 100.0
        + 0.15 * 100.0,
        1,
    )
    assert report.overall_score == expected


def test_deterministic_reports() -> None:
    ctx, _ = _context()
    first = _CRITIC.assess(ctx, topic=_TOPIC)
    second = _CRITIC.assess(ctx, topic=_TOPIC)
    assert first == second


def test_report_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        ImageQualityReport.model_validate({"topic": "x", "bogus": 1})


# --------------------------------------------------------------------------
# worked examples
# --------------------------------------------------------------------------

def _example_report(
    row: dict[str, str],
    *,
    domain: EngineeringDomain,
    scene_id: str,
    defects: RenderSpec,
) -> ImageQualityReport:
    plan = EducationalDirector().direct_from_csv(row)
    specs = default_specs(plan)
    renders = [
        RenderSpec(scene_id=f"S{index}")
        if f"S{index}" != scene_id
        else defects
        for index, _ in enumerate(specs, start=1)
    ]
    storyboard, prompts, metadata = build_stack(
        plan,
        domain=domain,
        modality=Modality.PHOTOREAL,
        specs=specs,
        thumbnail_scene_id="S5",
        renders=renders,
    )
    scene = next(s for s in storyboard.scenes if s.scene_id == scene_id)
    ctx = QAContext(
        plan=plan,
        storyboard=storyboard,
        scene=scene,
        metadata=metadata[scene_id],
        compiled_prompt=prompts["scenes"][scene_id],
    )
    return _CRITIC.assess(ctx, topic=plan.topic)


def test_gyroid_example_all_scenes_pass() -> None:
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    specs = default_specs(plan)
    renders = [
        RenderSpec(scene_id=f"S{index}") for index, _ in enumerate(specs, start=1)
    ]
    storyboard, prompts, metadata = build_stack(
        plan,
        domain=EngineeringDomain.FDM,
        modality=Modality.PHOTOREAL,
        specs=specs,
        thumbnail_scene_id="S5",
        renders=renders,
    )
    for scene in storyboard.scenes:
        ctx = QAContext(
            plan=plan,
            storyboard=storyboard,
            scene=scene,
            metadata=metadata[scene.scene_id],
            compiled_prompt=prompts["scenes"][scene.scene_id],
        )
        report = _CRITIC.assess(ctx, topic=_TOPIC)
        assert report.pass_fail is PassFail.PASS, scene.scene_id


def test_planetary_example_fails_with_repairs() -> None:
    report = _example_report(
        PLANETARY_ROW,
        domain=EngineeringDomain.MECHANISMS,
        scene_id="S2",
        defects=RenderSpec(
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
    )
    assert report.pass_fail is PassFail.FAIL
    assert any(
        issue.severity is IssueSeverity.CRITICAL for issue in report.issues
    )
    assert "Increase subject prominence" in report.repair_suggestions
    assert "Switch to macro shot" in report.repair_suggestions
    assert "Remove distracting background" in report.repair_suggestions


def test_injection_example_fails_on_educational_and_clutter() -> None:
    report = _example_report(
        INJECTION_ROW,
        domain=EngineeringDomain.INJECTION_MOLDING,
        scene_id="S2",
        defects=RenderSpec(
            scene_id="S2",
            annotations_present=False,
            annotation_quality=0.2,
            clutter_level=0.55,
            composition_quality=0.5,
            composition_rule_matches=False,
        ),
    )
    assert report.pass_fail is PassFail.FAIL
    assert report.educational_score < FAIL_FLOOR
    assert "Increase engineering annotations" in report.repair_suggestions
    assert "Remove distracting background" in report.repair_suggestions


def test_example_stack_compiles_real_prompts() -> None:
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    specs = default_specs(plan)
    renders = [
        RenderSpec(scene_id=f"S{index}") for index, _ in enumerate(specs, start=1)
    ]
    storyboard, prompts, _ = build_stack(
        plan,
        domain=EngineeringDomain.FDM,
        modality=Modality.PHOTOREAL,
        specs=specs,
        thumbnail_scene_id="S5",
        renders=renders,
    )
    compiled = compile_for_storyboard(storyboard, "sdxl", topic=plan.topic)
    assert compiled.thumbnail.prompt
    assert prompts["scenes"]["S1"].prompt == compiled.scenes["S1"].prompt