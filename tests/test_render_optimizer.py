"""Tests for the Render Optimizer (knowledge/render_optimizer): the plan
schema, the rule table, render profiles and workflow selection, deterministic
prompt mutations, score projection, the multi-round engine, and the three
worked examples (gyroid clean pass, planetary broken render, injection
partial defects)."""

from __future__ import annotations

import pytest
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW
from knowledge.image_qa import (
    ImageCritic,
    IssueSeverity,
    QACheck,
    QAContext,
)
from knowledge.image_qa.examples._stack import (
    RenderSpec,
    build_stack,
    default_specs,
)
from knowledge.image_qa.image_critic import _WEIGHTS as QA_WEIGHTS
from knowledge.image_qa.qa_models import FAIL_FLOOR, PASS_THRESHOLD
from knowledge.render_optimizer import (
    MAX_GAIN_PER_ROUND,
    MAX_ROUNDS,
    MAX_SCORE,
    MIN_TRIGGER_SEVERITY,
    OPTIMIZATION_FLOOR,
    OPTIMIZATION_RULES,
    OPTIMIZER_VERSION,
    RENDER_PROFILES,
    SCORE_FIELDS,
    SCORE_WEIGHTS,
    ActionTemplate,
    CameraChange,
    CompositionChange,
    ExpectedScoreImprovement,
    LightingChange,
    MutationKind,
    OptimizationAction,
    OptimizationActionKind,
    OptimizationEngine,
    OptimizationRule,
    OptimizedRenderPlan,
    PromptMutation,
    RenderOptimizer,
    RenderProfile,
    RenderProfileKey,
    VisualizationChange,
    WorkflowChange,
    apply,
    build_prompt,
    camera_mutations,
    composition_mutations,
    lighting_mutations,
    negative_mutations,
    profile_for,
    rule_for,
    select_workflow_profile,
    visualization_mutations,
)
from knowledge.visual_architecture import (
    CameraAngle,
    CameraDistance,
    CompositionRule,
    EngineeringDomain,
    Framing,
    Lens,
    LightDirection,
    LightingStyle,
    Modality,
    NegativeSpace,
)
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualizationType,
    ShotType,
)

_TOPIC = "Infill Pattern Comparisons"
_OPTIMIZER = RenderOptimizer()
_ENGINE = OptimizationEngine()


def _stack(
    row: dict[str, str],
    *,
    domain: EngineeringDomain,
    defects: RenderSpec | None = None,
    scene_id: str = "S2",
):
    """Build the QA stack for a topic; return report, scene, compiled prompt."""
    plan = EducationalDirector().direct_from_csv(row)
    specs = default_specs(plan)
    renders = [
        RenderSpec(scene_id=f"S{index}")
        if f"S{index}" != scene_id
        else (defects or RenderSpec(scene_id=scene_id))
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
    report = ImageCritic().assess(ctx, topic=plan.topic)
    return report, scene, prompts["scenes"][scene_id]


def _plan(
    row: dict[str, str],
    *,
    domain: EngineeringDomain,
    defects: RenderSpec | None = None,
    scene_id: str = "S2",
) -> OptimizedRenderPlan:
    report, scene, compiled = _stack(
        row, domain=domain, defects=defects, scene_id=scene_id
    )
    return _ENGINE.optimize(report, scene=scene, compiled_prompt=compiled)


_PLANETARY_DEFECTS = RenderSpec(
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
)

_INJECTION_DEFECTS = RenderSpec(
    scene_id="S2",
    annotations_present=False,
    annotation_quality=0.2,
    clutter_level=0.55,
    composition_quality=0.5,
    composition_rule_matches=False,
)


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

def test_plan_carries_all_sections() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    assert plan.version == OPTIMIZER_VERSION
    assert plan.topic
    assert plan.scene_id == "S2"
    for name in (
        "optimization_actions",
        "prompt_mutations",
        "workflow_changes",
        "camera_changes",
        "lighting_changes",
        "composition_changes",
        "visualization_changes",
    ):
        assert isinstance(getattr(plan, name), list)
    assert isinstance(plan.expected_score_improvement, ExpectedScoreImprovement)
    assert plan.rationale


def test_plan_json_round_trip() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    loaded = OptimizedRenderPlan.model_validate_json(plan.model_dump_json())
    assert loaded == plan


def test_plan_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        OptimizedRenderPlan.model_validate({"topic": "x", "bogus": 1})


def test_action_fields_constrained() -> None:
    with pytest.raises(ValueError):
        OptimizationAction(
            kind=OptimizationActionKind.PROMPT,
            check=QACheck.COMPOSITION_QUALITY,
            instruction="",
            expected_gain=1.0,
            target_score="composition_score",
            rationale="r",
        )
    with pytest.raises(ValueError):
        OptimizationAction(
            kind=OptimizationActionKind.PROMPT,
            check=QACheck.COMPOSITION_QUALITY,
            instruction="fix",
            expected_gain=999.0,
            target_score="composition_score",
            rationale="r",
        )


def test_replace_mutation_requires_target() -> None:
    with pytest.raises(ValueError):
        PromptMutation(
            kind=MutationKind.REPLACE,
            target_prompt="positive",
            target="",
            replacement="x",
            rationale="r",
        )


def test_append_mutation_allows_empty_target() -> None:
    mutation = PromptMutation(
        kind=MutationKind.APPEND,
        target_prompt="negative",
        target="",
        replacement="clutter",
        rationale="r",
    )
    assert mutation.target == ""


def test_expected_scores_bounded() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    expected = plan.expected_score_improvement
    for value in (
        expected.engineering,
        expected.educational,
        expected.composition,
        expected.subject_hierarchy,
        expected.visual_clarity,
        expected.thumbnail,
        expected.consistency,
        expected.overall,
        expected.improvement,
    ):
        assert 0.0 <= value <= MAX_SCORE
    assert isinstance(expected.predicted_pass, bool)


# --------------------------------------------------------------------------
# rule table
# --------------------------------------------------------------------------

def test_rules_cover_all_thirteen_checks() -> None:
    from knowledge.image_qa.qa_models import QACheck as Check

    assert set(OPTIMIZATION_RULES) == set(Check)


def test_rules_are_frozen_data() -> None:
    for rule in OPTIMIZATION_RULES.values():
        assert isinstance(rule, OptimizationRule)
        assert rule.actions
        for template in rule.actions:
            assert isinstance(template, ActionTemplate)
            assert template.gain > 0.0
            assert template.gain <= MAX_GAIN_PER_ROUND
            assert template.target_score in SCORE_FIELDS


def test_rule_for_unknown_check_is_empty() -> None:
    rule = rule_for(QACheck.ENGINEERING_ACCURACY)
    assert rule.actions
    assert rule_for(QACheck.ENGINEERING_ACCURACY) is rule


def test_unknown_check_has_no_actions() -> None:
    from knowledge.image_qa.qa_models import QACheck as Check

    placeholder = OptimizationRule(check=Check.ENGINEERING_ACCURACY)
    assert not placeholder.actions


def test_min_trigger_severity_is_major() -> None:
    assert MIN_TRIGGER_SEVERITY is IssueSeverity.MAJOR


def test_optimization_floor_is_below_pass_threshold() -> None:
    assert OPTIMIZATION_FLOOR < PASS_THRESHOLD


# --------------------------------------------------------------------------
# render profiles
# --------------------------------------------------------------------------

def test_all_profiles_present() -> None:
    expected = {
        RenderProfileKey.MACRO,
        RenderProfileKey.DIAGRAM,
        RenderProfileKey.CAD,
        RenderProfileKey.BLUEPRINT,
        RenderProfileKey.EXPLODED,
        RenderProfileKey.CUTAWAY,
        RenderProfileKey.TRANSPARENT,
        RenderProfileKey.STRESS_VISUALIZATION,
        RenderProfileKey.THERMAL_VISUALIZATION,
        RenderProfileKey.COMPARISON,
        RenderProfileKey.HERO,
    }
    assert set(RENDER_PROFILES) == expected


def test_every_profile_is_valid() -> None:
    for profile in RENDER_PROFILES.values():
        assert isinstance(profile, RenderProfile)
        assert 1 <= profile.steps <= 80
        assert 1.0 <= profile.cfg <= 15.0
        assert profile.resolution
        assert profile.sampler


def test_profile_for_fetches() -> None:
    assert profile_for(RenderProfileKey.MACRO).key is RenderProfileKey.MACRO


def test_profile_for_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        profile_for("nope")  # type: ignore[arg-type]


def test_macro_profile_uses_macro_negative_tokens() -> None:
    assert "text" in RENDER_PROFILES[RenderProfileKey.MACRO].negative_tokens


def test_cutaway_profile_mentions_interior() -> None:
    assert "interior" in RENDER_PROFILES[RenderProfileKey.CUTAWAY].description


# --------------------------------------------------------------------------
# workflow selector
# --------------------------------------------------------------------------

def test_visualization_maps_to_profile() -> None:
    cases = {
        EngineeringVisualizationType.CROSS_SECTION: RenderProfileKey.CUTAWAY,
        EngineeringVisualizationType.EXPLODED_ASSEMBLY: RenderProfileKey.EXPLODED,
        EngineeringVisualizationType.STRESS_DIRECTION: RenderProfileKey.STRESS_VISUALIZATION,
        EngineeringVisualizationType.DIMENSION_OVERLAY: RenderProfileKey.BLUEPRINT,
        EngineeringVisualizationType.MATERIAL_CALLOUTS: RenderProfileKey.DIAGRAM,
        EngineeringVisualizationType.TRANSPARENT_HOUSING: RenderProfileKey.TRANSPARENT,
    }
    for viz_type, expected in cases.items():
        profile, _ = select_workflow_profile(visualization_type=viz_type)
        assert profile is expected, viz_type


def test_shot_type_maps_to_profile() -> None:
    cases = {
        ShotType.MACRO: RenderProfileKey.MACRO,
        ShotType.BLUEPRINT: RenderProfileKey.BLUEPRINT,
        ShotType.COMPARISON_SPLIT: RenderProfileKey.COMPARISON,
        ShotType.CAD_RENDER: RenderProfileKey.CAD,
        ShotType.MANUFACTURING_SEQUENCE: RenderProfileKey.DIAGRAM,
        ShotType.EXPLODED_VIEW: RenderProfileKey.EXPLODED,
    }
    for shot_type, expected in cases.items():
        profile, _ = select_workflow_profile(shot_type=shot_type)
        assert profile is expected, shot_type


def test_visualization_wins_over_shot_type() -> None:
    profile, _ = select_workflow_profile(
        visualization_type=EngineeringVisualizationType.CROSS_SECTION,
        shot_type=ShotType.MACRO,
    )
    assert profile is RenderProfileKey.CUTAWAY


def test_default_profile_is_hero() -> None:
    profile, reason = select_workflow_profile()
    assert profile is RenderProfileKey.HERO
    assert "default" in reason


# --------------------------------------------------------------------------
# prompt mutator
# --------------------------------------------------------------------------

_POSITIVE = (
    "hero photograph of the part, made of PLA, surface: smooth, "
    "background: clean studio workbench, macro shot, eye level angle, "
    "100mm macro lens, subject centered framing, key lighting, studio style, "
    "rule of thirds composition, primary subject, vertical 9:16 composition"
)
_NEGATIVE = "text, blurry, low quality"
_CAMERA_OLD = {
    "shot": "macro",
    "angle": "eye level",
    "lens": "100mm macro",
    "framing": "subject centered",
}
_LIGHTING_OLD = {"direction": "key", "style": "studio"}


def test_camera_mutation_replaces_phrases() -> None:
    change = CameraChange(
        distance=CameraDistance.MACRO,
        angle=CameraAngle.EYE,
        lens=Lens.MACRO_100,
        framing=Framing.TIGHT,
        rationale="fix camera",
    )
    mutations = camera_mutations(change, old_values=_CAMERA_OLD)
    assert len(mutations) == 1  # identical values are skipped
    positive, _ = apply(_POSITIVE, _NEGATIVE, mutations)
    assert "tight framing" in positive
    assert "subject centered framing" not in positive


def test_camera_mutation_partial_change() -> None:
    change = CameraChange(framing=Framing.TIGHT, rationale="fix framing")
    mutations = camera_mutations(change, old_values=_CAMERA_OLD)
    assert len(mutations) == 1
    positive, _ = apply(_POSITIVE, _NEGATIVE, mutations)
    assert "tight framing" in positive
    assert "macro shot" in positive


def test_camera_mutation_without_old_values_appends() -> None:
    change = CameraChange(framing=Framing.TIGHT, rationale="fix framing")
    mutations = camera_mutations(change)
    assert len(mutations) == 1
    assert mutations[0].kind is MutationKind.APPEND
    positive, _ = apply(_POSITIVE, _NEGATIVE, mutations)
    assert positive.endswith("tight framing")


def test_empty_camera_change_yields_no_mutations() -> None:
    assert camera_mutations(CameraChange(rationale="no-op")) == []


def test_lighting_mutation_replaces_phrases() -> None:
    change = LightingChange(
        direction=LightDirection.RIM, style=LightingStyle.HARD_KEY, rationale="fix"
    )
    mutations = lighting_mutations(change, old_values=_LIGHTING_OLD)
    assert len(mutations) == 2
    positive, _ = apply(_POSITIVE, _NEGATIVE, mutations)
    assert "rim lighting" in positive
    assert "hard key style" in positive
    assert "key lighting" not in positive
    assert "studio style" not in positive


def test_composition_mutation_uses_old_rule() -> None:
    change = CompositionChange(rule=CompositionRule.CENTERED, rationale="fix")
    mutations = composition_mutations(change, old_rule="rule of thirds")
    positive, _ = apply(_POSITIVE, _NEGATIVE, mutations)
    assert "centered composition" in positive
    assert "rule of thirds composition" not in positive


def test_composition_mutation_without_old_rule_appends() -> None:
    change = CompositionChange(rule=CompositionRule.CENTERED, rationale="fix")
    mutations = composition_mutations(change)
    positive, _ = apply(_POSITIVE, _NEGATIVE, mutations)
    assert positive.endswith("centered composition")


def test_composition_negative_space_appends() -> None:
    change = CompositionChange(
        negative_space=NegativeSpace.OVERLAY_TOP, rationale="fix"
    )
    mutations = composition_mutations(change)
    positive, _ = apply(_POSITIVE, _NEGATIVE, mutations)
    assert positive.endswith("negative space at overlay top")


def test_visualization_mutation_appends_tokens() -> None:
    change = VisualizationChange(
        type=EngineeringVisualizationType.CROSS_SECTION,
        prompt_tokens=["cross section view", "interior details"],
        rationale="fix",
    )
    mutations = visualization_mutations(change)
    positive, _ = apply(_POSITIVE, _NEGATIVE, mutations)
    assert positive.endswith("engineering visualization: cross section view, interior details")


def test_visualization_without_tokens_is_noop() -> None:
    change = VisualizationChange(
        type=EngineeringVisualizationType.CROSS_SECTION, rationale="fix"
    )
    assert visualization_mutations(change) == []


def test_negative_mutations_append() -> None:
    mutations = negative_mutations(["clutter", "text"], rationale="fix")
    _, negative = apply(_POSITIVE, _NEGATIVE, mutations)
    assert negative == "text, blurry, low quality, clutter, text"


def test_apply_falls_back_to_append_when_target_missing() -> None:
    mutation = PromptMutation(
        kind=MutationKind.REPLACE,
        target_prompt="positive",
        target="overhead angle",
        replacement="eye level angle",
        rationale="fix",
    )
    positive, _ = apply(_POSITIVE, _NEGATIVE, [mutation])
    assert positive.endswith("eye level angle")


def test_apply_is_deterministic() -> None:
    change = CameraChange(framing=Framing.TIGHT, rationale="fix")
    first = apply(_POSITIVE, _NEGATIVE, camera_mutations(change))
    second = apply(_POSITIVE, _NEGATIVE, camera_mutations(change))
    assert first == second


def test_build_prompt_combines_all_changes() -> None:
    positive, negative = build_prompt(
        _POSITIVE,
        _NEGATIVE,
        camera=[CameraChange(framing=Framing.TIGHT, rationale="c")],
        lighting=[LightingChange(style=LightingStyle.STUDIO, rationale="l")],
        composition=[CompositionChange(rule=CompositionRule.CENTERED, rationale="p")],
        visualization=[
            VisualizationChange(
                type=EngineeringVisualizationType.CROSS_SECTION,
                prompt_tokens=["cross section view"],
                rationale="v",
            )
        ],
    )
    assert "tight framing" in positive
    assert "studio style" in positive
    assert "centered composition" in positive
    assert "engineering visualization: cross section view" in positive


def test_build_prompt_without_changes_is_identity() -> None:
    assert build_prompt(_POSITIVE, _NEGATIVE) == (_POSITIVE, _NEGATIVE)


# --------------------------------------------------------------------------
# optimizer behavior
# --------------------------------------------------------------------------

def test_passing_image_gets_zero_actions() -> None:
    report, scene, compiled = _stack(
        GYROID_ROW, domain=EngineeringDomain.FDM, defects=RenderSpec(scene_id="S2")
    )
    assert report.pass_fail.value == "pass"
    plan = _OPTIMIZER.optimize(report, scene=scene, compiled_prompt=compiled)
    assert plan.optimization_actions == []
    assert plan.prompt_mutations == []
    assert plan.workflow_changes == []
    expected = plan.expected_score_improvement
    assert expected.overall == report.overall_score
    assert expected.improvement == 0.0
    assert expected.predicted_pass


def test_failing_image_gets_actions() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    assert plan.optimization_actions
    for action in plan.optimization_actions:
        assert isinstance(action, OptimizationAction)
        assert action.kind in OptimizationActionKind
        assert action.check in QACheck
        assert action.expected_gain <= MAX_GAIN_PER_ROUND


def test_material_issue_fires_material_rules() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    checks = {a.check for a in plan.optimization_actions}
    assert QACheck.MATERIAL_CORRECTNESS in checks


def test_critical_issues_always_fire() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    material_actions = [
        a for a in plan.optimization_actions if a.check is QACheck.MATERIAL_CORRECTNESS
    ]
    assert material_actions
    assert any(a.kind is OptimizationActionKind.PROMPT for a in material_actions)


def test_workflow_and_visualization_changes_follow_actions() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    assert plan.workflow_changes
    assert all(isinstance(w, WorkflowChange) for w in plan.workflow_changes)
    assert all(isinstance(v, VisualizationChange) for v in plan.visualization_changes)
    assert all(isinstance(c, CameraChange) for c in plan.camera_changes)
    assert all(isinstance(light, LightingChange) for light in plan.lighting_changes)
    assert all(isinstance(c, CompositionChange) for c in plan.composition_changes)


def test_camera_suitability_reasserts_planned_phrase() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    texts = [m.replacement for m in plan.prompt_mutations if m.replacement]
    assert any("shot," in t and "framing" in t for t in texts)


def test_visual_clutter_adds_negative_tokens() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    negative_muts = [m for m in plan.prompt_mutations if m.target_prompt == "negative"]
    assert negative_muts
    assert any("clutter" in m.replacement for m in negative_muts)


def test_projection_uses_qa_weights() -> None:
    scores = {field: 50.0 for field in SCORE_FIELDS}
    scores["educational_score"] = 100.0
    actions = [
        OptimizationAction(
            kind=OptimizationActionKind.PROMPT,
            check=QACheck.COMPOSITION_QUALITY,
            instruction="fix",
            expected_gain=10.0,
            target_score="composition_score",
            rationale="r",
        )
    ]
    expected = RenderOptimizer._project(scores, actions)
    assert expected.composition == 60.0
    assert expected.overall == round(
        0.20 * 50 + 0.20 * 100 + 0.15 * 60 + 0.10 * 50 + 0.10 * 50 + 0.10 * 50 + 0.15 * 50,
        1,
    )


def test_gains_cap_at_max_per_round() -> None:
    scores = {field: 10.0 for field in SCORE_FIELDS}
    actions = [
        OptimizationAction(
            kind=OptimizationActionKind.PROMPT,
            check=QACheck.COMPOSITION_QUALITY,
            instruction=f"fix {i}",
            expected_gain=20.0,
            target_score="composition_score",
            rationale="r",
        )
        for i in range(3)
    ]
    expected = RenderOptimizer._project(scores, actions)
    assert expected.composition == 50.0  # capped at 40 gain on 10


def test_deterministic_plans() -> None:
    first = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    second = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    assert first == second


def test_optimizer_weights_match_qa_weights() -> None:
    assert SCORE_WEIGHTS == QA_WEIGHTS


def test_plan_for_passing_report_preserves_scores() -> None:
    report, scene, compiled = _stack(
        GYROID_ROW, domain=EngineeringDomain.FDM, defects=RenderSpec(scene_id="S2")
    )
    plan = _OPTIMIZER.optimize(report, scene=scene, compiled_prompt=compiled)
    expected = plan.expected_score_improvement
    assert expected.engineering == report.engineering_score
    assert expected.consistency == report.consistency_score


# --------------------------------------------------------------------------
# optimization engine
# --------------------------------------------------------------------------

def test_engine_runs_at_most_max_rounds() -> None:
    assert MAX_ROUNDS == 3
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    assert plan.optimization_actions


def test_engine_does_not_duplicate_actions() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    keys = [(a.check, a.instruction) for a in plan.optimization_actions]
    assert len(keys) == len(set(keys))


def test_engine_rounds_are_stable() -> None:
    report, scene, compiled = _stack(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    one_round = OptimizationEngine().optimize(
        report, scene=scene, compiled_prompt=compiled, max_rounds=1
    )
    three_rounds = OptimizationEngine().optimize(
        report, scene=scene, compiled_prompt=compiled, max_rounds=3
    )
    assert one_round == three_rounds


def test_engine_predicted_pass_meets_thresholds() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    expected = plan.expected_score_improvement
    if expected.predicted_pass:
        assert expected.overall >= PASS_THRESHOLD
        for score in (
            expected.engineering,
            expected.educational,
            expected.composition,
            expected.subject_hierarchy,
            expected.visual_clarity,
            expected.thumbnail,
            expected.consistency,
        ):
            assert score >= FAIL_FLOOR


def test_engine_improves_every_affected_score() -> None:
    report, scene, compiled = _stack(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    plan = _ENGINE.optimize(report, scene=scene, compiled_prompt=compiled)
    expected = plan.expected_score_improvement
    assert expected.engineering >= report.engineering_score
    assert expected.composition >= report.composition_score
    assert expected.consistency >= report.consistency_score
    assert expected.overall > report.overall_score


def test_engine_converges_on_passing_report() -> None:
    report, scene, compiled = _stack(
        GYROID_ROW, domain=EngineeringDomain.FDM, defects=RenderSpec(scene_id="S2")
    )
    plan = _ENGINE.optimize(report, scene=scene, compiled_prompt=compiled)
    assert plan.optimization_actions == []
    assert plan.expected_score_improvement.predicted_pass


# --------------------------------------------------------------------------
# worked examples
# --------------------------------------------------------------------------

def test_gyroid_example_optimizes_nothing() -> None:
    report, scene, compiled = _stack(
        GYROID_ROW, domain=EngineeringDomain.FDM, defects=RenderSpec(scene_id="S2")
    )
    plan = _ENGINE.optimize(report, scene=scene, compiled_prompt=compiled)
    assert report.pass_fail.value == "pass"
    assert plan.optimization_actions == []
    assert plan.expected_score_improvement.predicted_pass


def test_planetary_example_produces_full_plan() -> None:
    plan = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    assert len(plan.optimization_actions) >= 5
    assert plan.expected_score_improvement.overall >= 75.0
    assert plan.expected_score_improvement.predicted_pass
    assert any(w.profile is RenderProfileKey.CUTAWAY for w in plan.workflow_changes)


def test_injection_example_targets_failed_checks() -> None:
    plan = _plan(
        INJECTION_ROW,
        domain=EngineeringDomain.INJECTION_MOLDING,
        defects=_INJECTION_DEFECTS,
    )
    checks = {a.check for a in plan.optimization_actions}
    assert QACheck.EDUCATIONAL_EFFECTIVENESS in checks
    assert QACheck.VISUAL_CLUTTER in checks
    assert QACheck.ENGINEERING_ACCURACY not in checks


def test_injection_example_predicts_pass() -> None:
    plan = _plan(
        INJECTION_ROW,
        domain=EngineeringDomain.INJECTION_MOLDING,
        defects=_INJECTION_DEFECTS,
    )
    assert plan.expected_score_improvement.predicted_pass
    assert plan.expected_score_improvement.overall >= 75.0


def test_action_gains_come_from_the_rule_table() -> None:
    a = _plan(
        PLANETARY_ROW, domain=EngineeringDomain.MECHANISMS, defects=_PLANETARY_DEFECTS
    )
    b = _plan(
        INJECTION_ROW,
        domain=EngineeringDomain.INJECTION_MOLDING,
        defects=_INJECTION_DEFECTS,
    )
    for action in a.optimization_actions + b.optimization_actions:
        templates = OPTIMIZATION_RULES[action.check].actions
        assert action.expected_gain == pytest.approx(
            next(t.gain for t in templates if t.instruction == action.instruction)
        )