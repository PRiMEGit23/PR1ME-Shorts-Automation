"""Tests for the Visual Intelligence Engine (knowledge/visual_intelligence):
goal classification, shot selection, camera/lighting/composition planning,
engineering visualizations, transitions, thumbnail ranking, the storyboard
schema, storyboard compilation, and the gyroid full-stack example."""

from __future__ import annotations

import pytest
from knowledge.compiler import compile_for_model, compile_for_storyboard
from knowledge.compiler.examples.gyroid_v2 import TOPIC, build_gyroid_architecture
from knowledge.compiler.prompt_compiler import CompileError
from knowledge.visual_architecture import (
    CameraAngle,
    CameraDistance,
    CameraHeight,
    CompositionRule,
    EngineeringDomain,
    Framing,
    Lens,
    LightDirection,
    LightingStyle,
    Material,
    Modality,
    NegativeSpace,
    TransitionType,
)
from knowledge.visual_intelligence import (
    KnowledgeBaseRow,
    ShotDirector,
    VisualIntelligenceEngine,
    VisualStoryboard,
)
from knowledge.visual_intelligence.engineering_visuals import (
    select_engineering_visualizations,
)
from knowledge.visual_intelligence.shot_selector import (
    DIAGRAM_LIKE_SHOTS,
    SHOT_PREFIXES,
    select_shot_type,
)
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualizationType,
    ShotType,
)
from knowledge.visual_intelligence.thumbnail_director import pick_thumbnail_scene
from knowledge.visual_intelligence.transition_planner import plan_transitions
from knowledge.visual_intelligence.visual_goal import VisualGoal, classify_visual_goal

from test_knowledge_visual_architecture import architecture, scene

ENGINE = VisualIntelligenceEngine()


def test_classify_first_scene_introduces() -> None:
    arch = architecture()
    goal = classify_visual_goal(
        arch.scenes[0], scene_index=1, scene_count=4, keywords=(), summary=""
    )
    assert goal is VisualGoal.INTRODUCE_CONCEPT


def test_classify_last_scene_summarizes() -> None:
    arch = architecture()
    goal = classify_visual_goal(
        arch.scenes[3], scene_index=4, scene_count=4, keywords=(), summary=""
    )
    assert goal is VisualGoal.SUMMARIZE


def test_classify_keyword_beats_position() -> None:
    arch = architecture()
    goal = classify_visual_goal(
        arch.scenes[0], scene_index=1, scene_count=4, keywords=(), summary=""
    )
    assert goal is VisualGoal.INTRODUCE_CONCEPT
    load_scene = arch.scenes[0].model_copy(update={"engineering_goal": "load paths"})
    goal = classify_visual_goal(
        load_scene, scene_index=1, scene_count=4, keywords=(), summary=""
    )
    assert goal is VisualGoal.EXPLAIN_FORCE_FLOW


def test_classify_uses_topic_keywords() -> None:
    arch = architecture()
    goal = classify_visual_goal(
        arch.scenes[1], scene_index=2, scene_count=4, keywords=["gyroid infill"], summary=""
    )
    assert goal is VisualGoal.REVEAL_INTERNAL_GEOMETRY


def test_classify_modality_fallback() -> None:
    arch = architecture()
    explode = arch.scenes[1].model_copy(update={"modality": Modality.EXPLODED_VIEW})
    goal = classify_visual_goal(
        explode, scene_index=2, scene_count=4, keywords=(), summary=""
    )
    assert goal is VisualGoal.EXPLAIN_ASSEMBLY


def test_shot_director_dedupes_repeated_explain_goals() -> None:
    arch = architecture()
    scenes = [
        scene(1, engineering_goal="load path"),
        scene(2, engineering_goal="load path"),
        scene(3, engineering_goal="thermal flow"),
        scene(4, engineering_goal="thermal flow"),
    ]
    arch = arch.model_copy(update={"scenes": scenes})
    goals = ShotDirector().classify_goals(arch)
    assert goals == [
        VisualGoal.EXPLAIN_FORCE_FLOW,
        VisualGoal.HIGHLIGHT_DIFFERENCE,
        VisualGoal.EXPLAIN_HEAT_FLOW,
        VisualGoal.HIGHLIGHT_DIFFERENCE,
    ]


def test_shot_director_leaves_first_position_default() -> None:
    arch = architecture()
    goals = ShotDirector().classify_goals(arch)
    assert goals[0] is VisualGoal.INTRODUCE_CONCEPT
    assert goals[-1] is VisualGoal.SUMMARIZE


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        (VisualGoal.INTRODUCE_CONCEPT, ShotType.HERO),
        (VisualGoal.COMPARE, ShotType.COMPARISON_SPLIT),
        (VisualGoal.REVEAL_INTERNAL_GEOMETRY, ShotType.CROSS_SECTION),
        (VisualGoal.EXPLAIN_PROCESS, ShotType.PROCESS_SEQUENCE),
        (VisualGoal.EXPLAIN_FORCE_FLOW, ShotType.ANNOTATED_DIAGRAM),
        (VisualGoal.EXPLAIN_ASSEMBLY, ShotType.EXPLODED_VIEW),
        (VisualGoal.EXPLAIN_MANUFACTURING, ShotType.MANUFACTURING_SEQUENCE),
        (VisualGoal.EXPLAIN_OPTIMIZATION, ShotType.CAD_RENDER),
        (VisualGoal.HIGHLIGHT_DIFFERENCE, ShotType.BEFORE_AFTER),
        (VisualGoal.SUMMARIZE, ShotType.HERO),
    ],
)
def test_goal_to_shot_table(goal: VisualGoal, expected: ShotType) -> None:
    arch = architecture()
    photoreal = arch.scenes[0].model_copy(update={"modality": Modality.PHOTOREAL})
    shot = select_shot_type(goal, photoreal)
    assert shot is expected


def test_modality_forces_shot() -> None:
    arch = architecture()
    s = arch.scenes[0].model_copy(update={"modality": Modality.EXPLODED_VIEW})
    assert select_shot_type(VisualGoal.INTRODUCE_CONCEPT, s) is ShotType.EXPLODED_VIEW


def test_reveal_with_secondary_subjects_becomes_transparent() -> None:
    arch = architecture()
    secondary = arch.scenes[0].primary_subject.model_copy(update={"entity": "inner rotor"})
    s = arch.scenes[0].model_copy(
        update={
            "modality": Modality.PHOTOREAL,
            "secondary_subjects": [secondary],
            "subject_hierarchy": arch.scenes[0].subject_hierarchy.model_copy(
                update={"secondary": ["inner rotor"], "focus_object": "inner rotor"}
            ),
        },
    )
    shot = select_shot_type(VisualGoal.REVEAL_INTERNAL_GEOMETRY, s)
    assert shot is ShotType.TRANSPARENT


def test_every_shot_type_has_a_prefix() -> None:
    assert set(SHOT_PREFIXES) == set(ShotType)
    assert ShotType.ANNOTATED_DIAGRAM in DIAGRAM_LIKE_SHOTS
    assert ShotType.MACRO not in DIAGRAM_LIKE_SHOTS


def test_engineering_visualization_selection() -> None:
    force = select_engineering_visualizations(
        VisualGoal.EXPLAIN_FORCE_FLOW, ShotType.ANNOTATED_DIAGRAM, domain=EngineeringDomain.FDM
    )
    assert len(force) == 1
    assert force[0].type is EngineeringVisualizationType.FORCE_ARROWS
    assert "white force arrows showing load paths" in force[0].prompt_tokens

    heat = select_engineering_visualizations(
        VisualGoal.EXPLAIN_HEAT_FLOW, ShotType.ANNOTATED_DIAGRAM, domain=EngineeringDomain.FDM
    )
    assert heat[0].type is EngineeringVisualizationType.HEAT_MAP

    none = select_engineering_visualizations(
        VisualGoal.SUMMARIZE, ShotType.HERO, domain=EngineeringDomain.FDM
    )
    assert none == []


def test_engineering_visualization_respects_domain() -> None:
    process = select_engineering_visualizations(
        VisualGoal.EXPLAIN_PROCESS, ShotType.PROCESS_SEQUENCE, domain=EngineeringDomain.FDM
    )
    assert process[0].type is EngineeringVisualizationType.LAYER_PRINT
    molded = select_engineering_visualizations(
        VisualGoal.EXPLAIN_PROCESS, ShotType.PROCESS_SEQUENCE, domain=EngineeringDomain.INJECTION_MOLDING
    )
    assert molded == []


def test_camera_plan_mirrors_arch_field_names() -> None:
    arch = architecture()
    photoreal = [s.model_copy(update={"modality": Modality.PHOTOREAL}) for s in arch.scenes]
    arch = arch.model_copy(update={"scenes": photoreal})
    storyboard = ENGINE.plan_storyboard(arch, topic="Test Topic")
    camera = storyboard.scenes[0].camera
    assert storyboard.scenes[0].intent.shot_type is ShotType.HERO
    for field in ("distance", "angle", "lens", "framing", "height"):
        assert hasattr(camera, field)
    assert camera.distance is CameraDistance.WIDE
    assert camera.angle is CameraAngle.SLIGHTLY_LOW
    assert camera.lens is Lens.STANDARD_35
    assert camera.framing is Framing.LOOSE
    assert camera.height is CameraHeight.EYE_LEVEL


def test_lighting_metal_gets_hard_key() -> None:
    arch = architecture()
    metal = arch.scenes[0].primary_subject.model_copy(update={"materials": [Material.STEEL]})
    s = arch.scenes[0].model_copy(update={"primary_subject": metal})
    from knowledge.visual_intelligence.lighting_planner import plan_lighting

    plan = plan_lighting(ShotType.MACRO, s)
    assert plan.style is LightingStyle.HARD_KEY
    assert plan.direction is LightDirection.KEY


def test_lighting_diagram_stays_studio() -> None:
    arch = architecture()
    metal = arch.scenes[0].primary_subject.model_copy(update={"materials": [Material.STEEL]})
    s = arch.scenes[0].model_copy(update={"primary_subject": metal})
    from knowledge.visual_intelligence.lighting_planner import plan_lighting

    plan = plan_lighting(ShotType.ANNOTATED_DIAGRAM, s)
    assert plan.style is LightingStyle.STUDIO
    assert plan.direction is LightDirection.KEY


def test_composition_row_shots_center_row() -> None:
    arch = architecture()
    process = arch.scenes[1].model_copy(
        update={"modality": Modality.PHOTOREAL, "engineering_goal": "process steps in order"}
    )
    arch = arch.model_copy(update={"scenes": [arch.scenes[0], process, *arch.scenes[2:]]})
    storyboard = ENGINE.plan_storyboard(arch, topic="Test Topic")
    row_scene = storyboard.scenes[1]
    assert row_scene.intent.shot_type is ShotType.PROCESS_SEQUENCE
    assert row_scene.composition.rule is CompositionRule.CENTER_ROW
    assert row_scene.composition.negative_space is NegativeSpace.OVERLAY_TOP


def test_transitions_rhythm() -> None:
    arch = architecture()
    goals = [VisualGoal.EXPLAIN_FORCE_FLOW] * 4
    shots = [ShotType.ANNOTATED_DIAGRAM] * 4
    transitions = plan_transitions(arch.scenes, goals, shots)
    assert transitions[0].type is TransitionType.NONE
    assert transitions[1].type is TransitionType.DISSOLVE
    assert transitions[2].type is TransitionType.DISSOLVE  # repeated flow


def test_thumbnail_scoring_prioritizes_candidates() -> None:
    arch = architecture()
    s5 = scene(
        5,
        scene_importance=5,
        thumbnail_candidate=True,
        engineering_goal="Takeaway",
        teaching_goal="Recap",
    )
    arch = arch.model_copy(update={"scenes": [*arch.scenes, s5]})
    storyboard = ENGINE.plan_storyboard(arch, topic="Test Topic")
    winner = pick_thumbnail_scene(storyboard.scenes)
    assert winner.scene_id == "S5"
    assert storyboard.thumbnail_scene_id == "S5"
    assert winner.thumbnail_priority.rank == 1
    assert winner.thumbnail_priority.score >= 14


def test_storyboard_schema_validates() -> None:
    arch = architecture()
    storyboard = ENGINE.plan_storyboard(arch, topic="Test Topic")
    restored = VisualStoryboard.model_validate_json(storyboard.model_dump_json())
    assert restored == storyboard
    assert restored.version == "1.0.0"


def test_storyboard_is_deterministic() -> None:
    arch = architecture()
    first = ENGINE.plan_storyboard(arch, topic="Test Topic")
    second = ENGINE.plan_storyboard(arch, topic="Test Topic")
    assert first == second
    assert first.scenes[0].intent.goal is second.scenes[0].intent.goal


def test_storyboard_scenes_are_self_contained() -> None:
    arch = architecture()
    storyboard = ENGINE.plan_storyboard(arch, topic="Test Topic")
    s = storyboard.scenes[0]
    assert s.primary_subject.entity == arch.scenes[0].primary_subject.entity
    assert s.environment
    assert s.depth.background
    assert s.color_palette.base
    assert s.objects_to_avoid == arch.scenes[0].objects_to_avoid
    assert s.consistency_tags == arch.scenes[0].consistency_tags


def test_compile_for_storyboard_sdxl() -> None:
    arch = architecture()
    storyboard = ENGINE.plan_storyboard(arch, topic="Test Topic")
    row = compile_for_storyboard(storyboard, "sdxl", topic="Test Topic")
    assert row.model == "sdxl"
    assert set(row.scenes) == {"S1", "S2", "S3", "S4"}
    prefix = SHOT_PREFIXES[storyboard.scenes[0].intent.shot_type]
    assert row.scenes["S1"].prompt.startswith(prefix)
    assert row.thumbnail.metadata["target"] == "storyboard_thumbnail"
    assert row.thumbnail.metadata["thumbnail_score"] >= 0
    assert row.scenes["S2"].metadata["source"] == {
        "field": "visual_storyboard_json",
        "schema_version": "1.0.0",
    }


def test_storyboard_negative_includes_diagram_tokens() -> None:
    arch = architecture()
    force = arch.scenes[1].model_copy(
        update={"modality": Modality.PHOTOREAL, "engineering_goal": "load paths"}
    )
    arch = arch.model_copy(update={"scenes": [arch.scenes[0], force, *arch.scenes[2:]]})
    storyboard = ENGINE.plan_storyboard(arch, topic="Test Topic")
    row = compile_for_storyboard(storyboard, "sdxl", topic="Test Topic")
    annotated = next(
        s for s in storyboard.scenes if s.intent.shot_type is ShotType.ANNOTATED_DIAGRAM
    )
    negative = row.scenes[annotated.scene_id].negative_prompt
    assert negative is not None
    assert "photographic shadows" in negative
    assert "3d render" in negative


def test_compile_for_storyboard_unknown_model_fails_closed() -> None:
    arch = architecture()
    storyboard = ENGINE.plan_storyboard(arch, topic="Test Topic")
    with pytest.raises(KeyError):
        compile_for_storyboard(storyboard, "not_a_model", topic="Test Topic")
    with pytest.raises(CompileError, match="no compiler"):
        compile_for_storyboard(storyboard, "flux", topic="Test Topic")


def test_compile_for_model_still_works_unchanged() -> None:
    arch = architecture()
    row = compile_for_model(arch, "sdxl", topic="Test Topic")
    assert row.scenes["S1"].prompt.startswith("cross-section cutaway of")
    assert "cut-open test part" in row.scenes["S1"].prompt


def test_knowledge_base_row_from_csv() -> None:
    row = KnowledgeBaseRow.from_csv_row(
        {
            "topic": "Infill Pattern Comparisons",
            "keywords": '["infill patterns","gyroid","cubic","grid infill","honeycomb"]',
            "scene_count": "5",
            "materials": '["PLA test prints","steel"]',
            "engineering_summary": "Gyroid is the engineering favorite.",
        }
    )
    assert row.keywords == ["infill patterns", "gyroid", "cubic", "grid infill", "honeycomb"]
    assert row.scene_count == 5
    assert row.materials == ["PLA test prints", "steel"]
    assert row.topic == "Infill Pattern Comparisons"


def test_engine_build_storyboard_from_row() -> None:
    arch = build_gyroid_architecture()
    row = KnowledgeBaseRow.from_csv_row(
        {
            "topic": TOPIC,
            "keywords": '["infill patterns","gyroid","cubic","grid infill","honeycomb"]',
            "scene_count": "5",
        }
    )
    storyboard = ENGINE.build_storyboard(arch, row)
    assert storyboard.topic == TOPIC
    assert storyboard.thumbnail_scene_id == "S5"


def test_gyroid_goal_arc() -> None:
    arch = build_gyroid_architecture()
    goals = ENGINE.classify_goals(arch, keywords=["infill patterns", "gyroid", "grid infill"])
    assert goals == [
        VisualGoal.INTRODUCE_CONCEPT,
        VisualGoal.REVEAL_INTERNAL_GEOMETRY,
        VisualGoal.EXPLAIN_FORCE_FLOW,
        VisualGoal.HIGHLIGHT_DIFFERENCE,
        VisualGoal.SUMMARIZE,
    ]


def test_gyroid_full_storyboard() -> None:
    arch = build_gyroid_architecture()
    storyboard = ENGINE.plan_storyboard(arch, topic=TOPIC, keywords=["infill patterns"])
    assert len(storyboard.scenes) == 5
    assert [s.intent.shot_type for s in storyboard.scenes] == [
        ShotType.CROSS_SECTION,
        ShotType.CROSS_SECTION,
        ShotType.ANNOTATED_DIAGRAM,
        ShotType.BEFORE_AFTER,
        ShotType.HERO,
    ]
    force = storyboard.scenes[2].intent.engineering_visualizations
    assert force and force[0].type is EngineeringVisualizationType.FORCE_ARROWS
    assert storyboard.scenes[0].transition.type is TransitionType.NONE
    assert storyboard.scenes[-1].transition.type is TransitionType.FADE
    assert storyboard.scenes[3].transition.type is TransitionType.WIPE
    assert storyboard.thumbnail_scene_id == "S5"
    ranks = {s.scene_id: s.thumbnail_priority.rank for s in storyboard.scenes}
    assert ranks["S5"] == 1
    assert ranks["S4"] == 2


def test_gyroid_storyboard_compiles_with_engineering_tokens() -> None:
    arch = build_gyroid_architecture()
    storyboard = ENGINE.plan_storyboard(arch, topic=TOPIC, keywords=["infill patterns"])
    row = compile_for_storyboard(storyboard, "sdxl", topic=TOPIC)
    s3 = row.scenes["S3"].prompt
    assert s3.startswith("annotated technical diagram of")
    assert "engineering visualization: white force arrows showing load paths" in s3
    assert "made of PLA" in s3
    thumb = row.thumbnail.prompt
    assert thumb.startswith("hero photograph of")
    assert "high contrast" in thumb
    assert thumb != row.scenes["S5"].prompt  # thumbnail adds thumbnail tokens