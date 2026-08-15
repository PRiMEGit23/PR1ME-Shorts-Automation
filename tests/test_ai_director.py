"""AI Director (Phase 8) tests: decision engine, integration, validation.

Covers the director's guarantees:

- determinism: the same plan always produces the identical creative brief
- validation: every curated row in assets/knowledge_base.csv directs to a
  schema-valid DirectorOutput (roles, arcs, budgets, predictions)
- arc decisions: merge (4 scenes), canonical (5), split (6); the hero,
  thumbnail, and recap scenes follow the rules; reveal orders are
  permutations; staggered reveal for reveal-style strategies
- transition grammar: fade / dissolve / wipe fire from the decisions
- downstream consumption: the storyboard, the compiled prompts, and the
  workflow profiles carry the director's decisions; the legacy path
  (director=None) is byte-identical to pre-Phase-8 behavior
- the QA envelope: director-directed storyboards still pass the
  simulated vision QA across seeds
- performance: the full 400-row knowledge base directs well within budget
"""

from __future__ import annotations

import csv
import hashlib
import json
import struct
import time
from pathlib import Path

import pytest
from knowledge.ai_director import AIDirector
from knowledge.ai_director.director_models import DirectorOutput
from knowledge.ai_director.director_rules import (
    decide_scene_count,
    transition_between,
    visualization_for,
)
from knowledge.ai_director.examples.run_worked_examples import direct_all
from knowledge.compiler import compile_for_storyboard
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.educational_models import (
    AnimationRequirement,
    CognitiveStep,
    DifficultyLevel,
    EducationalPlan,
    FailureMode,
    RetentionMethod,
    TeachingStrategy,
    VisualTeachingMethod,
)
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.render_optimizer import select_workflow_profile
from knowledge.visual_architecture import EngineeringDomain, Lens, LightDirection, Modality
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualizationType,
    ShotType,
)
from knowledge.visual_intelligence.visual_goal import VisualGoal
from runtime.models import SessionConfig
from runtime.pipeline import ProductionPipeline
from runtime.render_loop import RenderLoop
from runtime.renderer import SimulatedRenderer
from runtime.storyboard_builder import StoryboardBuilder

from pr1me.providers.video_renderer import VideoRender, VideoRenderRequest
from pr1me.providers.voice import VoiceRender

FDM = EngineeringDomain.FDM
PHOTOREAL = Modality.PHOTOREAL

_ED = EducationalDirector()
_DIRECTOR = AIDirector()
_ROWS = list(csv.DictReader(open("assets/knowledge_base.csv", encoding="utf-8")))


class _FakeVoice:
    """Deterministic voice seam for the pipeline integration test."""

    name = "voice"
    provider_name = "fake-voice"

    async def synthesize(
        self,
        text: str,
        *,
        output_dir: str | Path,
        voice: str | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
    ) -> VoiceRender:
        data = struct.pack("<I", 1)  # a few valid WAV bytes suffice
        target = Path(output_dir) / f"narration.{(format_ or 'wav').lstrip('.')}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return VoiceRender(
            file=str(target),
            text=text,
            voice=voice or "default",
            sample_rate=sample_rate or 22050,
            format=(format_ or "wav").lstrip("."),
            duration_seconds=0.01,
            checksum=hashlib.sha256(data).hexdigest(),
        )


class _FakeVideo:
    """Deterministic video renderer seam for the pipeline integration test."""

    name = "video_renderer"
    provider_name = "fake-video"
    codec = "libx264"
    container = "mp4"
    crf = 20
    audio_codec = "aac"
    audio_bitrate_kbps = 192

    async def render(
        self,
        request: VideoRenderRequest,
        *,
        output_dir: str | Path,
        filename: str = "short.mp4",
    ) -> VideoRender:
        data = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 24
        target = Path(output_dir) / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return VideoRender(
            file=str(target),
            fps=request.fps,
            width=request.width,
            height=request.height,
            duration_seconds=6.0,
            size_bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
        )


# ------------------------------------------------------------------ helper --


def _plan(
    *,
    strategy: TeachingStrategy = TeachingStrategy.PROBLEM_SOLUTION,
    flow_steps: int = 5,
    methods: tuple[str, ...] = ("diagram", "cross section"),
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
    animation: AnimationRequirement = AnimationRequirement.PARTIAL,
) -> EducationalPlan:
    """A minimal, legal EducationalPlan with overridable teaching choices."""
    stages = (
        CognitiveStep.HOOK,
        CognitiveStep.QUESTION,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.REVEAL,
        CognitiveStep.SOLUTION,
        CognitiveStep.COMPARISON,
        CognitiveStep.CONCLUSION,
    )
    flow = [
        {
            "step": index,
            "stage": stages[index % len(stages)].value,
            "concept": f"concept {index}",
            "justification": "test concept",
        }
        for index in range(1, flow_steps + 1)
    ]
    cognitive = [stage.value for stage in stages[: min(flow_steps, len(stages))]]
    while len(cognitive) < 3:
        cognitive.append(CognitiveStep.EXPLANATION.value)
    return EducationalPlan.model_validate(
        {
            "topic": "Crafted Topic",
            "learning_objective": {
                "statement": "The viewer can explain the concept.",
                "verbs": ["explain"],
                "success_criteria": "restates the rule",
            },
            "core_misconception": {
                "statement": "The concept is believed to work differently.",
                "why_common": "intuition",
                "why_dangerous": "wrong predictions",
                "refutation": "show the mechanism",
            },
            "teaching_strategy": strategy.value,
            "strategy_rationale": "test",
            "visual_teaching_method": [methods[0]],
            "method_rationale": "test",
            "cognitive_sequence": cognitive,
            "cognitive_flow_rationale": "test",
            "attention_hook": "Ever wondered?",
            "knowledge_flow": flow,
            "retention_method": RetentionMethod.VISUAL_ANCHOR.value,
            "retention_rationale": "test",
            "difficulty_level": difficulty.value,
            "expected_mental_model": "a working model",
            "comparison_strategy": "",
            "analogy_strategy": "",
            "animation_requirement": animation.value,
            "animation_rationale": "test",
            "visualization_priority": list(methods),
            "failure_mode": FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR.value,
            "failure_mode_rationale": "test",
            "final_takeaway": "Remember the rule.",
            "prior_knowledge": [],
        }
    )


def _direct(row: dict[str, str]) -> DirectorOutput:
    return _DIRECTOR.direct(_ED.direct_from_csv(row))


# ------------------------------------------------------------- determinism --


def test_director_is_deterministic() -> None:
    plan = _ED.direct_from_csv(GYROID_ROW)
    assert _DIRECTOR.direct(plan) == _DIRECTOR.direct(plan)
    assert _DIRECTOR.direct(plan).model_dump(mode="json") == _DIRECTOR.direct(
        plan
    ).model_dump(mode="json")


def test_director_is_deterministic_over_the_whole_knowledge_base() -> None:
    for row in _ROWS:
        plan = _ED.direct_from_csv(row)
        assert _DIRECTOR.direct(plan) == _DIRECTOR.direct(plan)


# ---------------------------------------------------------------- validation --


def test_director_validates_every_curated_row() -> None:
    for row in _ROWS:
        output = _direct(row)
        assert output.version == "8.0.0"
        assert output.topic == row["topic"]
        assert 4 <= output.scene_count <= 6
        assert len(output.scene_directives) == output.scene_count
        assert [d.scene_index for d in output.scene_directives] == list(
            range(1, output.scene_count + 1)
        )
        assert output.recap_scene_id == f"S{output.scene_count}"
        for directive in output.scene_directives:
            assert 1 <= directive.importance <= 5
            for budget in (
                directive.visual_budget,
                directive.animation_budget,
                directive.motion_budget,
                directive.camera_intensity,
                directive.lighting_priority,
                directive.diagram_priority,
                directive.engineering_emphasis,
                directive.comparison_emphasis,
                directive.emotion,
                directive.pacing,
            ):
                assert 1 <= budget <= 10
            assert 0.0 <= directive.retention_score <= 100.0
            assert 0.0 <= directive.expected_attention <= 100.0
            assert directive.reveal_order >= 1


def test_director_role_invariants_hold_for_every_row() -> None:
    for row in _ROWS:
        output = _direct(row)
        heroes = [d for d in output.scene_directives if d.is_hero]
        thumbnails = [d for d in output.scene_directives if d.is_thumbnail]
        recaps = [d for d in output.scene_directives if d.is_recap]
        assert len(heroes) == len(thumbnails) == len(recaps) == 1
        assert heroes[0].scene_id == output.hero_scene_id
        assert thumbnails[0].scene_id == output.thumbnail_scene_id
        assert recaps[0].scene_id == output.recap_scene_id
        assert heroes[0].scene_id != recaps[0].scene_id
        assert thumbnails[0].scene_id != recaps[0].scene_id
        assert thumbnails[0].thumbnail_priority.rank == 1
        assert {d.thumbnail_priority.rank for d in output.scene_directives} == {1, 2}


# ------------------------------------------------------------- arc decisions --


def test_scene_count_merge_keep_split() -> None:
    merge, merge_reason = decide_scene_count(
        3, TeachingStrategy.PROBLEM_SOLUTION, [VisualTeachingMethod.DIAGRAM]
    )
    assert merge == 4
    assert "merge" in merge_reason

    keep, _ = decide_scene_count(
        5,
        TeachingStrategy.COMPARISON,
        [VisualTeachingMethod.COMPARISON_BOARD],
    )
    assert keep == 5

    split, split_reason = decide_scene_count(
        6,
        TeachingStrategy.MANUFACTURING_SEQUENCE,
        [VisualTeachingMethod.TIMELINE],
    )
    assert split == 6
    assert "evidence" in split_reason


def test_merge_arc_drops_the_comparison_beat() -> None:
    output = _director_output(_plan(flow_steps=3, strategy=TeachingStrategy.PROBLEM_SOLUTION))
    assert output.scene_count == 4
    goals = [d.visual_goal for d in output.scene_directives]
    assert goals == [
        VisualGoal.INTRODUCE_CONCEPT,
        VisualGoal.REVEAL_INTERNAL_GEOMETRY,
        VisualGoal.EXPLAIN_PROCESS,
        VisualGoal.SUMMARIZE,
    ]


def test_split_arc_earns_an_evidence_beat() -> None:
    output = _director_output(
        _plan(flow_steps=6, strategy=TeachingStrategy.MANUFACTURING_SEQUENCE)
    )
    assert output.scene_count == 6
    goals = [d.visual_goal for d in output.scene_directives]
    assert goals[-1] is VisualGoal.SUMMARIZE
    assert goals[4] in (VisualGoal.HIGHLIGHT_DIFFERENCE, VisualGoal.EXPLAIN_PROCESS)


def test_canonical_arc_is_five_scenes() -> None:
    assert _direct(GYROID_ROW).scene_count == 5


def test_hero_scene_is_the_highest_value_showpiece() -> None:
    output = _direct(GYROID_ROW)
    hero = next(d for d in output.scene_directives if d.is_hero)
    assert hero.importance == 5
    assert not hero.is_recap


def test_reveal_orders_are_a_permutation() -> None:
    for row in _ROWS:
        output = _direct(row)
        orders = [d.reveal_order for d in output.scene_directives]
        assert sorted(orders) == list(range(1, output.scene_count + 1))


def test_staggered_reveal_for_reveal_strategies() -> None:
    output = _director_output(
        _plan(flow_steps=5, strategy=TeachingStrategy.HIDDEN_GEOMETRY)
    )
    assert output.reveal_plan == "staggered reveal"
    by_scene = {d.scene_index: d for d in output.scene_directives}
    assert by_scene[2].reveal_order == 4  # the reveal lands after the comparison


def test_sequential_reveal_for_other_strategies() -> None:
    output = _director_output(
        _plan(flow_steps=5, strategy=TeachingStrategy.COMPARISON)
    )
    assert output.reveal_plan == "sequential reveal"
    assert [d.reveal_order for d in output.scene_directives] == [1, 2, 3, 4, 5]


def test_macro_shot_required_for_inspection_strategies() -> None:
    """Strategies whose vehicle is close inspection force a macro reveal."""
    for strategy in (
        TeachingStrategy.SCALE_COMPARISON,
        TeachingStrategy.FAILURE_ANALYSIS,
    ):
        output = _director_output(_plan(flow_steps=5, strategy=strategy))
        reveal = {d.scene_index: d for d in output.scene_directives}[2]
        assert reveal.shot_type is ShotType.MACRO, strategy
        assert "macro inspection required" in reveal.rationale


def test_macro_not_forced_when_shot_is_already_inspection_level() -> None:
    output = _director_output(
        _plan(
            flow_steps=5,
            strategy=TeachingStrategy.FAILURE_ANALYSIS,
            methods=("microscope", "diagram"),
        )
    )
    reveal = {d.scene_index: d for d in output.scene_directives}[2]
    assert reveal.shot_type is ShotType.MICROSCOPE
    assert "macro inspection required" not in reveal.rationale


def test_macro_never_forced_for_other_strategies() -> None:
    output = _director_output(
        _plan(
            flow_steps=5,
            strategy=TeachingStrategy.PROBLEM_SOLUTION,
            methods=("cross section", "diagram"),
        )
    )
    reveal = {d.scene_index: d for d in output.scene_directives}[2]
    assert reveal.shot_type is ShotType.CROSS_SECTION


def test_visualization_tokens_come_from_the_rule() -> None:
    """The overlay tokens are the single rule's tokens, never re-written."""
    viz = visualization_for(
        EngineeringVisualizationType.DIMENSION_OVERLAY, "test rationale"
    )
    assert viz.prompt_tokens == [EngineeringVisualizationType.DIMENSION_OVERLAY.value]
    assert viz.rationale == "test rationale"

    output = _director_output(
        _plan(flow_steps=5, strategy=TeachingStrategy.ENERGY_FLOW)
    )
    reveal = {d.scene_index: d for d in output.scene_directives}[2]
    wireframes = [
        v
        for v in reveal.engineering_visualizations
        if v.type is EngineeringVisualizationType.WIREFRAME_OVERLAY
    ]
    assert wireframes
    assert wireframes[0].prompt_tokens == [
        EngineeringVisualizationType.WIREFRAME_OVERLAY.value
    ]


def test_attention_curve_peaks_at_100() -> None:
    for row in _ROWS:
        output = _direct(row)
        assert max(d.expected_attention for d in output.scene_directives) == 100.0


# ------------------------------------------------------------- transitions --


def test_transition_grammar_rules() -> None:
    assert transition_between(9, comparison_emphasis=3, pacing=5, is_first=False).type.value == "fade"
    assert (
        transition_between(5, comparison_emphasis=8, pacing=5, is_first=False).type.value
        == "dissolve"
    )
    assert transition_between(5, comparison_emphasis=3, pacing=8, is_first=False).type.value == "wipe"
    assert transition_between(5, comparison_emphasis=3, pacing=5, is_first=False).type.value == "cut"
    assert transition_between(9, comparison_emphasis=9, pacing=9, is_first=True).type.value == "cut"


def test_arc_transitions_follow_the_decisions() -> None:
    output = _direct(GYROID_ROW)
    transitions = [d.transition.type.value for d in output.scene_directives]
    assert transitions[0] == "cut"  # opening
    assert transitions[1] == "fade"  # into the emotional peak (reveal, emotion 9)
    assert transitions[3] == "dissolve"  # into the comparison beat
    assert transitions[4] == "cut"  # continuity into the recap


# ------------------------------------------------------------- QA envelope --


def test_camera_and_lighting_stay_in_the_qa_envelope() -> None:
    """The simulated vision pipeline cures camera/lighting defects only for
    the 100mm macro lens and key lighting, so the director must keep those."""
    for row in _ROWS:
        output = _direct(row)
        for directive in output.scene_directives:
            assert directive.camera.lens is Lens.MACRO_100
            assert directive.lighting.direction is LightDirection.KEY
            assert directive.lighting.style.value in ("studio", "hard key")


def test_camera_intensity_varies_the_plan() -> None:
    output = _direct(GYROID_ROW)
    intensities = {d.camera_intensity for d in output.scene_directives}
    assert len(intensities) >= 2  # the director is not a constant camera
    hero = next(d for d in output.scene_directives if d.is_hero)
    assert hero.camera_intensity >= 7


def test_director_driven_storyboard_passes_qa_across_seeds() -> None:
    plan = _ED.direct_from_csv(GYROID_ROW)
    output = _DIRECTOR.direct(plan)
    storyboard = StoryboardBuilder().build(
        plan, engineering_domain=FDM, modality=PHOTOREAL, director=output
    )
    for seed in range(42, 47):
        for index, scene in enumerate(storyboard.scenes):
            result = RenderLoop(renderer=SimulatedRenderer()).run(
                plan=plan,
                storyboard=storyboard,
                scene=scene,
                topic=plan.topic,
                seed=seed + index,
                config=SessionConfig(max_attempts=3, model_key="sdxl"),
            )
            assert result.passed, f"{scene.scene_id} failed at seed {seed + index}"


# ---------------------------------------------------- downstream consumption --


def test_storyboard_consumes_the_director_decisions() -> None:
    plan = _ED.direct_from_csv(GYROID_ROW)
    output = _DIRECTOR.direct(plan)
    storyboard = StoryboardBuilder().build(
        plan, engineering_domain=FDM, modality=PHOTOREAL, director=output
    )
    assert storyboard.thumbnail_scene_id == output.thumbnail_scene_id
    for scene in storyboard.scenes:
        directive = next(
            d for d in output.scene_directives if d.scene_id == scene.scene_id
        )
        assert scene.scene_importance == directive.importance
        assert scene.intent.shot_type is directive.shot_type
        assert scene.intent.goal is directive.visual_goal
        assert scene.camera == directive.camera
        assert scene.lighting == directive.lighting
        assert scene.composition == directive.composition
        assert scene.motion == directive.motion
        assert scene.mood is directive.mood
        assert scene.transition == directive.transition
        assert scene.thumbnail_priority.rank == directive.thumbnail_priority.rank
        assert scene.thumbnail_candidate is directive.is_thumbnail
        assert [
            viz.type for viz in scene.intent.engineering_visualizations
        ] == [viz.type for viz in directive.engineering_visualizations]


def test_legacy_storyboard_path_is_unchanged() -> None:
    plan = _ED.direct_from_csv(GYROID_ROW)
    storyboard = StoryboardBuilder().build(
        plan, engineering_domain=FDM, modality=PHOTOREAL
    )
    assert [s.scene_importance for s in storyboard.scenes] == [4, 3, 3, 3, 5]
    assert storyboard.thumbnail_scene_id == "S5"
    assert storyboard.scenes[-1].thumbnail_candidate is True
    assert all(not s.thumbnail_candidate for s in storyboard.scenes[:-1])
    assert all(s.camera.lens is Lens.MACRO_100 for s in storyboard.scenes)


def test_compiled_prompts_carry_the_director_decisions() -> None:
    plan = _ED.direct_from_csv(GYROID_ROW)
    output = _DIRECTOR.direct(plan)
    storyboard = StoryboardBuilder().build(
        plan, engineering_domain=FDM, modality=PHOTOREAL, director=output
    )
    compiled = compile_for_storyboard(storyboard, "sdxl", topic=plan.topic)
    for scene in storyboard.scenes:
        directive = next(
            d for d in output.scene_directives if d.scene_id == scene.scene_id
        )
        metadata = compiled.scenes[scene.scene_id].metadata
        assert metadata["visual_goal"] == directive.visual_goal.value
        assert metadata["shot_type"] == directive.shot_type.value
    thumbnail = next(s for s in storyboard.scenes if s.scene_id == output.thumbnail_scene_id)
    assert compiled.thumbnail.metadata["scene_id"] == thumbnail.scene_id
    assert compiled.thumbnail.metadata["thumbnail_score"] == thumbnail.thumbnail_priority.score


def test_workflow_profiles_follow_the_director_shots() -> None:
    plan = _ED.direct_from_csv(GYROID_ROW)
    output = _DIRECTOR.direct(plan)
    storyboard = StoryboardBuilder().build(
        plan, engineering_domain=FDM, modality=PHOTOREAL, director=output
    )
    for scene in storyboard.scenes:
        directive = next(
            d for d in output.scene_directives if d.scene_id == scene.scene_id
        )
        viz_type = (
            scene.intent.engineering_visualizations[0].type
            if scene.intent.engineering_visualizations
            else None
        )
        profile, _ = select_workflow_profile(
            visualization_type=viz_type, shot_type=directive.shot_type
        )
        assert profile is not None


# ---------------------------------------------------------------- pipeline --


@pytest.mark.asyncio
async def test_pipeline_runs_the_director_stage(tmp_path) -> None:
    run_dir = tmp_path / "run"
    result = await ProductionPipeline(
        row=GYROID_ROW,
        run_dir=run_dir,
        seed=42,
        max_attempts=3,
        engineering_domain=FDM,
        modality=PHOTOREAL,
        renderer=SimulatedRenderer(),
        voice_provider=_FakeVoice(),
        video_renderer_provider=_FakeVideo(),
    ).run()
    assert result.status == "complete"

    report = json.loads((run_dir / "reports" / "execution_report.json").read_text(encoding="utf-8"))
    stage_ids = [stage["stage_id"] for stage in report["stages"]]
    assert stage_ids[2] == "ai_director"
    assert stage_ids[3] == "visual_intelligence"

    outputs = list((run_dir / "artifacts" / "ai_director").glob("output.*.json"))
    assert outputs, "expected a persisted AI Director output artifact"
    director_output = json.loads(outputs[0].read_text(encoding="utf-8"))
    assert director_output["version"] == "8.0.0"
    assert len(director_output["scene_directives"]) == 5
    assert director_output["recap_scene_id"] == "S5"


# ------------------------------------------------------------ worked examples --


def test_worked_examples_direct_to_valid_outputs() -> None:
    outputs = direct_all()
    assert list(outputs) == ["gyroid", "planetary_gear", "injection_molding"]
    gyroid = outputs["gyroid"]
    assert gyroid.scene_count == 5
    assert gyroid.recap_scene_id == "S5"
    assert gyroid.hero_scene_id == "S1"
    planetary = outputs["planetary_gear"]
    assert planetary.reveal_plan == "staggered reveal"
    assert planetary.hero_scene_id == "S2"  # the reveal is the showpiece
    injection = outputs["injection_molding"]
    assert injection.scene_count == 6  # manufacturing sequence earns a split
    for output in outputs.values():
        DirectorOutput.model_validate(output.model_dump(mode="json"))


# ---------------------------------------------------------------- performance --


def test_directing_the_whole_knowledge_base_is_fast() -> None:
    started = time.perf_counter()
    for row in _ROWS:
        _direct(row)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"directing 400 rows took {elapsed:.2f}s"


# ---------------------------------------------------------------- helpers --

def _director_output(plan: EducationalPlan) -> DirectorOutput:
    return _DIRECTOR.direct(plan)
