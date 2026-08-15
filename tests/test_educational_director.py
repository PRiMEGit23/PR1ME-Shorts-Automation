"""Tests for the Educational Director (knowledge/educational_director):
taxonomy coverage, KnowledgeDirector extraction, strategy selection (word
boundaries, rule priority), visual method selection, cognitive flows,
animation requirements, the full gyroid / planetary / injection worked
examples, determinism, and schema serialization."""

from __future__ import annotations

import json

import pytest
from knowledge.educational_director import (
    EDUCATIONAL_PLAN_VERSION,
    AnimationRequirement,
    CognitiveFlowBuilder,
    CognitiveStep,
    DifficultyLevel,
    EducationalDirector,
    EducationalPlan,
    EngineeringDomainHint,
    FailureMode,
    KnowledgeDirector,
    KnowledgeFlowStep,
    RetentionMethod,
    StrategySelector,
    TeachingStrategy,
    VisualMethodSelector,
    VisualTeachingMethod,
    derive_learning_objective,
    infer_domain,
)
from knowledge.visual_intelligence import KnowledgeBaseRow

DIRECTOR = EducationalDirector()

GYROID_ROW: dict[str, str] = {
    "topic": "Infill Pattern Comparisons",
    "difficulty": "B",
    "category": "Slicer & Print Settings",
    "subcategory": "Infill",
    "keywords": '["infill patterns","gyroid","cubic","grid infill","honeycomb"]',
    "search_intent": "what infill pattern is strongest",
    "viewer_level": "Intermediate",
    "learning_objective": (
        "The viewer can compare gyroid, cubic, grid, and line patterns by "
        "strength, isotropy, and speed, and pick for the load."
    ),
    "engineering_summary": (
        "Infill patterns differ in strength per gram, directionality, and print "
        "speed. Gyroid is the engineering favorite: a triply periodic surface "
        "with no flat layers, giving near-isotropic strength, good energy "
        "absorption, and even stress distribution - at a small speed cost. "
        "Cubic builds stacked cubes for strong vertical structure but leaves "
        "45-degree weak zones and takes time. Grid is fast, but its crossing "
        "lines create stress concentration at intersections and strong "
        "directional anisotropy. Lines and triangles are cheap and fine for "
        "light duty. Rule of thumb: gyroid for structural parts and impact, "
        "cubic for tall columns, grid for speed and low-load parts."
    ),
    "common_misconceptions": (
        '["The strongest pattern is strongest everywhere (patterns are '
        'directional; gyroid is the isotropic exception)","Dense infill removes '
        'pattern differences (pattern matters most at 20-40% where parts '
        'actually print)","Pattern choice is cosmetic (strength, energy '
        'absorption, and printing time all change)"]'
    ),
    "scene_count": "5",
}

PLANETARY_ROW: dict[str, str] = {
    "topic": "Planetary Gears",
    "difficulty": "A",
    "category": "Mechanical Engineering",
    "subcategory": "Gears",
    "keywords": '["planetary gear","epicyclic","sun gear","gear box"]',
    "search_intent": "how planetary gears work",
    "viewer_level": "Advanced",
    "learning_objective": (
        "The viewer understands the sun, ring, and carrier, and why planetary "
        "gears carry more load."
    ),
    "engineering_summary": (
        "A planetary gearset puts a sun gear, a ring gear, and planets spinning "
        "between them. Power can enter the sun, the ring, or the carrier, and "
        "each input gives a different ratio, including reverse and direct "
        "drive. That compactness is why planetary gears live in drills, "
        "automatic transmissions, and robot joints. The load splits across "
        "several planet teeth, so the set carries more torque than a pair of "
        "gears the same size. Staging several sets multiplies the ratios. When "
        "a mechanism needs a big reduction in a small space, planetary gears "
        "are usually the answer."
    ),
    "common_misconceptions": (
        '["Planetary gears need more space (they pack the most reduction per '
        'volume)","There is one fixed ratio (every input and output choice '
        'gives a new ratio)","Planet gears carry the load alone (the load '
        'spreads across all planet teeth)"]'
    ),
    "scene_count": "5",
}

INJECTION_ROW: dict[str, str] = {
    "topic": "Injection Molding",
    "difficulty": "B",
    "category": "Manufacturing Processes",
    "subcategory": "Molding",
    "keywords": '["injection molding","mold","plastic molding","molded parts"]',
    "search_intent": "how injection molding works",
    "viewer_level": "Beginner",
    "learning_objective": (
        "The viewer can explain the molding cycle and why the tooling cost "
        "forces high production volumes."
    ),
    "engineering_summary": (
        "Injection molding melts polymer pellets and injects them under high "
        "pressure (thousands of psi) into a closed steel mold cavity. The part "
        "cools, the mold opens along the parting line, ejector pins push the "
        "part out, and the cycle repeats in seconds. The mold is "
        "precision-machined steel costing tens of thousands of dollars, so "
        "per-part cost collapses only at high volumes. Break-even analysis "
        "decides when a part should be molded instead of printed or machined."
    ),
    "common_misconceptions": (
        '["Molding is always cheaper (tooling dominates until volume pays it '
        'back)","Molded parts are weaker than printed parts (they are typically '
        'stronger with no layer interfaces)","Any geometry can be molded '
        '(undercuts need slides, and draft angles are mandatory)"]'
    ),
    "scene_count": "5",
}


def _row(csv_row: dict[str, str]) -> KnowledgeBaseRow:
    return KnowledgeBaseRow.from_csv_row(csv_row)


# --------------------------------------------------------------------------
# taxonomy coverage
# --------------------------------------------------------------------------

def test_educational_plan_has_all_required_fields() -> None:
    plan = DIRECTOR.direct_from_csv(GYROID_ROW)
    assert plan.version == EDUCATIONAL_PLAN_VERSION
    required = (
        "topic", "learning_objective", "core_misconception", "teaching_strategy",
        "visual_teaching_method", "cognitive_sequence", "attention_hook",
        "knowledge_flow", "retention_method", "difficulty_level",
        "expected_mental_model", "comparison_strategy", "analogy_strategy",
        "animation_requirement", "visualization_priority", "failure_mode",
        "final_takeaway",
    )
    for field in required:
        assert getattr(plan, field) is not None


def test_strategy_taxonomy_complete() -> None:
    expected = {
        "comparison", "before/after", "cause to effect", "problem to solution",
        "question to answer", "layer-by-layer reveal", "hidden geometry",
        "failure analysis", "mechanical breakdown", "animation first",
        "diagram first", "scale comparison", "progressive disclosure",
        "myth busting", "real-world example", "simulation",
        "process timeline", "manufacturing sequence", "force flow",
        "energy flow", "material transformation",
    }
    assert {s.value for s in TeachingStrategy} == expected


def test_visual_method_taxonomy_complete() -> None:
    expected = {
        "diagram", "animation", "CAD", "exploded view", "cross section",
        "transparent housing", "stress visualization", "thermal visualization",
        "motion visualization", "assembly sequence", "section view",
        "infographic", "timeline", "macro", "microscope", "X-ray", "cutaway",
        "comparison board",
    }
    assert {m.value for m in VisualTeachingMethod} == expected


def test_retention_and_failure_taxonomies() -> None:
    assert {r.value for r in RetentionMethod} == {
        "visual anchor", "concrete reference", "mental model", "recap",
        "chunking", "mnemonic",
    }
    assert FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR in FailureMode
    assert FailureMode.COMPARISON_WITHOUT_CONTEXT in FailureMode


def test_cognitive_step_sequence_well_formed() -> None:
    members = list(CognitiveStep)
    assert members[0] is CognitiveStep.HOOK
    assert members[-1] is CognitiveStep.CONCLUSION
    assert "summary" not in {s.value for s in CognitiveStep}


# --------------------------------------------------------------------------
# KnowledgeDirector
# --------------------------------------------------------------------------

def test_knowledge_director_extraction_gyroid() -> None:
    knowledge = KnowledgeDirector().analyze(_row(GYROID_ROW), csv_row=GYROID_ROW)
    assert knowledge.topic == "Infill Pattern Comparisons"
    assert knowledge.domain_hint is EngineeringDomainHint.FDM_PRINTING
    assert knowledge.difficult_visualization == "stress distribution inside the volume"
    assert knowledge.key_phenomenon == "stress distribution through a lattice"
    assert "triply periodic" in knowledge.most_important_concept
    assert "Rule of thumb" not in knowledge.critical_takeaway
    assert "gyroid for structural parts" in knowledge.critical_takeaway


def test_knowledge_director_extraction_planetary() -> None:
    knowledge = KnowledgeDirector().analyze(_row(PLANETARY_ROW), csv_row=PLANETARY_ROW)
    assert knowledge.domain_hint is EngineeringDomainHint.MECHANISMS
    assert knowledge.difficult_visualization == (
        "sun, ring, and planets moving simultaneously"
    )
    assert knowledge.key_phenomenon == "load sharing across planet teeth"
    assert "big reduction in a small space" in knowledge.critical_takeaway


def test_knowledge_director_extraction_injection() -> None:
    knowledge = KnowledgeDirector().analyze(_row(INJECTION_ROW), csv_row=INJECTION_ROW)
    assert knowledge.domain_hint is EngineeringDomainHint.INJECTION_MOLDING
    assert knowledge.difficult_visualization == "the sequence inside a closed steel mold"
    assert knowledge.key_phenomenon == "the injection molding cycle"
    assert knowledge.common_misconception.startswith("Molding is always cheaper")
    assert knowledge.primary_objective == INJECTION_ROW["learning_objective"]
    assert knowledge.required_prior_knowledge  # non-empty


def test_knowledge_director_csv_row_optional() -> None:
    knowledge = KnowledgeDirector().analyze(_row(GYROID_ROW))
    # without the raw record, heuristics stand in for the unmodeled fields
    assert knowledge.common_misconception.startswith("Rule of thumb")
    assert knowledge.primary_objective.startswith("Understand ")


def test_infer_domain_fallbacks() -> None:
    assert infer_domain("Workshop", "Rigging", ()) is EngineeringDomainHint.WORKSHOP
    assert infer_domain("Unseen Category", "Odd", ()) is EngineeringDomainHint.DESIGN_CAD


# --------------------------------------------------------------------------
# strategy selection
# --------------------------------------------------------------------------

def test_strategy_gyroid_comparison() -> None:
    strategy, rationale = StrategySelector().select(_row(GYROID_ROW), csv_row=GYROID_ROW)
    assert strategy is TeachingStrategy.COMPARISON
    assert "differ" in rationale


def test_strategy_planetary_progressive_disclosure_not_comparison() -> None:
    strategy, rationale = StrategySelector().select(
        _row(PLANETARY_ROW), csv_row=PLANETARY_ROW
    )
    assert strategy is TeachingStrategy.PROGRESSIVE_DISCLOSURE
    # "a different ratio" must NOT match the "differ" comparison token
    assert "comparison" not in strategy.value


def test_strategy_injection_manufacturing_sequence_not_failure() -> None:
    strategy, rationale = StrategySelector().select(
        _row(INJECTION_ROW), csv_row=INJECTION_ROW
    )
    assert strategy is TeachingStrategy.MANUFACTURING_SEQUENCE
    # "Break-even analysis" must NOT match a failure-analysis "break" token
    assert "failure" not in strategy.value


def test_strategy_vs_beats_injection_tokens() -> None:
    row = dict(INJECTION_ROW)
    row["topic"] = "AM vs Injection Molding"
    strategy, _ = StrategySelector().select(_row(row), csv_row=row)
    assert strategy is TeachingStrategy.COMPARISON


def test_strategy_word_boundary_matching() -> None:
    row = dict(PLANETARY_ROW)
    row["engineering_summary"] = "The ratios differ between the two builds."
    strategy, _ = StrategySelector().select(_row(row), csv_row=row)
    assert strategy is TeachingStrategy.COMPARISON


def test_strategy_never_random() -> None:
    for _ in range(3):
        strategy, rationale = StrategySelector().select(
            _row(GYROID_ROW), csv_row=GYROID_ROW
        )
        assert strategy is TeachingStrategy.COMPARISON
        assert rationale == rationale


# --------------------------------------------------------------------------
# visual methods + objectives
# --------------------------------------------------------------------------

def test_visual_methods_gyroid_refined() -> None:
    methods, _ = VisualMethodSelector().select(
        TeachingStrategy.COMPARISON, _row(GYROID_ROW)
    )
    assert {m.value for m in methods} == {
        "comparison board", "cross section", "stress visualization",
    }


def test_visual_methods_planetary_refined() -> None:
    methods, _ = VisualMethodSelector().select(
        TeachingStrategy.PROGRESSIVE_DISCLOSURE, _row(PLANETARY_ROW)
    )
    assert {m.value for m in methods} == {
        "transparent housing", "motion visualization", "exploded view",
        "animation",
    }


def test_visual_methods_injection_refined() -> None:
    methods, _ = VisualMethodSelector().select(
        TeachingStrategy.MANUFACTURING_SEQUENCE, _row(INJECTION_ROW)
    )
    assert {m.value for m in methods} == {
        "exploded view", "animation", "thermal visualization", "timeline",
    }


def test_visual_methods_generic_strategy_default() -> None:
    row = _row(PLANETARY_ROW)
    methods, _ = VisualMethodSelector().select(TeachingStrategy.QUESTION_ANSWER, row)
    assert methods  # every strategy maps to at least one method


def test_learning_objective_verbs() -> None:
    objective = derive_learning_objective(
        curator_objective="The viewer can compare A and B.",
        concept="comparison",
        strategy=TeachingStrategy.COMPARISON,
    )
    assert objective.verbs == ["compare", "choose"]


# --------------------------------------------------------------------------
# cognitive flow
# --------------------------------------------------------------------------

def test_cognitive_sequence_bookends() -> None:
    plan = DIRECTOR.direct_from_csv(GYROID_ROW)
    assert plan.cognitive_sequence[0] is CognitiveStep.HOOK
    assert plan.cognitive_sequence[-1] is CognitiveStep.CONCLUSION
    assert plan.attention_hook == "Three cubes, same size, three different strengths."


def test_knowledge_flow_matches_sequence_and_methods() -> None:
    plan = DIRECTOR.direct_from_csv(GYROID_ROW)
    assert len(plan.knowledge_flow) == len(plan.cognitive_sequence)
    assert [s.stage for s in plan.knowledge_flow] == list(plan.cognitive_sequence)
    used = {s.visual_method for s in plan.knowledge_flow}
    assert used <= set(plan.visual_teaching_method)
    assert all(s.concept for s in plan.knowledge_flow)


def test_cognitive_flow_uses_problem_step_for_injection() -> None:
    plan = DIRECTOR.direct_from_csv(INJECTION_ROW)
    assert CognitiveStep.PROBLEM in plan.cognitive_sequence
    assert plan.knowledge_flow[1].stage is CognitiveStep.PROBLEM
    assert plan.knowledge_flow[1].visual_method is VisualTeachingMethod.ANIMATION


def test_animation_requirement() -> None:
    assert DIRECTOR.direct_from_csv(GYROID_ROW).animation_requirement is (
        AnimationRequirement.YES
    )
    assert DIRECTOR.direct_from_csv(PLANETARY_ROW).animation_requirement is (
        AnimationRequirement.YES
    )
    assert DIRECTOR.direct_from_csv(INJECTION_ROW).animation_requirement is (
        AnimationRequirement.YES
    )


def test_difficulty_mapping() -> None:
    assert DIRECTOR.direct_from_csv(GYROID_ROW).difficulty_level is (
        DifficultyLevel.INTERMEDIATE
    )
    assert DIRECTOR.direct_from_csv(PLANETARY_ROW).difficulty_level is (
        DifficultyLevel.ADVANCED
    )
    assert DIRECTOR.direct_from_csv(INJECTION_ROW).difficulty_level is (
        DifficultyLevel.BEGINNER
    )


def test_visualization_priority_justified() -> None:
    plan = DIRECTOR.direct_from_csv(PLANETARY_ROW)
    assert plan.visualization_priority
    for method in plan.visualization_priority:
        assert method in plan.visual_teaching_method
    assert "refines" in plan.method_rationale


def test_takeaways_are_curated() -> None:
    assert "gyroid for structural parts" in DIRECTOR.direct_from_csv(
        GYROID_ROW
    ).final_takeaway
    assert "big reduction in a small space" in DIRECTOR.direct_from_csv(
        PLANETARY_ROW
    ).final_takeaway
    assert "Break-even analysis" in DIRECTOR.direct_from_csv(
        INJECTION_ROW
    ).final_takeaway


# --------------------------------------------------------------------------
# determinism + schema
# --------------------------------------------------------------------------

def test_deterministic_plans() -> None:
    first = DIRECTOR.direct_from_csv(GYROID_ROW)
    second = DIRECTOR.direct_from_csv(GYROID_ROW)
    assert first == second


def test_plan_json_round_trip() -> None:
    plan = DIRECTOR.direct_from_csv(PLANETARY_ROW)
    loaded = EducationalPlan.model_validate_json(plan.model_dump_json())
    assert loaded == plan
    payload = json.loads(plan.model_dump_json())
    assert payload["teaching_strategy"] == "progressive disclosure"
    assert len(payload["knowledge_flow"]) == len(payload["cognitive_sequence"])


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValueError):
        EducationalPlan.model_validate({"topic": "x", "bogus": 1})


def test_flow_builder_supports_all_strategies() -> None:
    builder = CognitiveFlowBuilder()
    row = _row(GYROID_ROW)
    knowledge = KnowledgeDirector().analyze(row, csv_row=GYROID_ROW)
    for strategy in TeachingStrategy:
        methods, _ = VisualMethodSelector().select(strategy, row)
        steps = builder.sequence_for(strategy)
        assert steps[0] is CognitiveStep.HOOK
        assert steps[-1] is CognitiveStep.CONCLUSION
        assert methods  # every strategy has visuals
        flow, _ = builder.build_knowledge_flow(strategy, methods, knowledge)
        assert len(flow) == len(steps)
        assert all(isinstance(s, KnowledgeFlowStep) for s in flow)
