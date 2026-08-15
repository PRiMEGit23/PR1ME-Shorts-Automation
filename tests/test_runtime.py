"""Phase 6 runtime tests: the closed-loop generation engine.

Covers the runtime schemas (fingerprints, attempts, sessions), the
deterministic SimulatedRenderer and its defect/cure model, the content
cache, retry budget and duplicate guard, workflow/storyboard construction,
the full render -> QA -> optimize loop (pass-first-try, full repair, budget
exhaustion, duplicate skip, artifact persistence, cache reuse), session
management (run_all, determinism, replayability) and the knowledge-layer
hardening caps (repair suggestions <= 8, optimization actions <= 24).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from knowledge.compiler import compile_for_storyboard
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW
from knowledge.image_qa.image_critic import ImageCritic, QAContext
from knowledge.image_qa.qa_models import GeneratedImageMetadata, QACheck, QAIssue
from knowledge.image_qa.render_repair import RenderRepairEngine
from knowledge.render_optimizer import (
    OptimizationEngine,
    RenderProfileKey,
    VisualizationChange,
    WorkflowChange,
)
from knowledge.visual_architecture import EngineeringDomain, Modality
from knowledge.visual_intelligence.storyboard import ShotType
from pydantic import ValidationError
from runtime import (
    AttemptStatus,
    RenderCache,
    RenderHistory,
    RenderLoop,
    RenderRequest,
    RenderSession,
    RenderSessionResult,
    RetryManager,
    SessionConfig,
    SimulatedRenderer,
    StoryboardBuilder,
    WorkflowBuilder,
    attempt_dir,
    fingerprint_of,
    replay,
    tiny_png,
    topic_slug,
    verify_replay_identical,
)
from runtime.models import RenderAttempt

FDM = EngineeringDomain.FDM
MECHANISMS = EngineeringDomain.MECHANISMS
PHOTOREAL = Modality.PHOTOREAL


def _bad_metadata(scene_id: str, all_failing: bool = False) -> GeneratedImageMetadata:
    """Metadata that fails many QA checks but stays within model caps."""
    if all_failing:
        return GeneratedImageMetadata(
            scene_id=scene_id,
            subject_present=True,
            subject_prominence=0.35,
            subject_occluded=True,
            hierarchy_clear=False,
            engineering_accuracy=0.3,
            geometry_correct=False,
            geometry_quality=0.35,
            material_correct=False,
            material_quality=0.35,
            camera_distance_matches=False,
            camera_angle_matches=False,
            lens_matches=False,
            lighting_direction_matches=False,
            lighting_style_matches=False,
            composition_rule_matches=False,
            composition_quality=0.35,
            clutter_level=0.7,
            visual_clarity=0.45,
            method_implemented=False,
            annotations_present=False,
            annotation_quality=0.35,
            comparison_axis_present=False,
            thumbnail_contrast=0.35,
            thumbnail_focus=0.35,
            thumbnail_negative_space=False,
            scene_consistency=0.4,
            consistency_violations=["palette drift"],
            prompt_term_mismatches=["missing terms"],
        )
    return GeneratedImageMetadata(
        scene_id=scene_id,
        subject_present=True,
        subject_prominence=0.55,
        subject_occluded=False,
        hierarchy_clear=False,
        engineering_accuracy=0.45,
        geometry_correct=False,
        geometry_quality=0.45,
        material_correct=True,
        material_quality=0.7,
        camera_distance_matches=False,
        camera_angle_matches=False,
        lens_matches=True,
        lighting_direction_matches=True,
        lighting_style_matches=True,
        composition_rule_matches=True,
        composition_quality=0.7,
        clutter_level=0.35,
        visual_clarity=0.7,
        method_implemented=False,
        annotations_present=False,
        annotation_quality=0.45,
        comparison_axis_present=True,
        thumbnail_contrast=0.6,
        thumbnail_focus=0.6,
        thumbnail_negative_space=True,
        scene_consistency=0.6,
        consistency_violations=[],
        prompt_term_mismatches=[],
    )


class AlwaysBadRenderer:
    """Deterministic renderer that always fails QA, never cures."""

    def __init__(self, all_failing: bool = False) -> None:
        self.all_failing = all_failing

    def render(self, request: RenderRequest) -> object:
        return type(
            "R",
            (),
            {
                "metadata": _bad_metadata(request.scene_id, self.all_failing),
                "image_bytes": b"\x89PNG-bad",
            },
        )()


class CountingRenderer(SimulatedRenderer):
    """SimulatedRenderer that counts every actual render call."""

    def __init__(self) -> None:
        super().__init__()
        self.renders = 0

    def render(self, request: RenderRequest):
        self.renders += 1
        return super().render(request)


@pytest.fixture()
def planetary():
    plan = EducationalDirector().direct_from_csv(PLANETARY_ROW)
    return plan


@pytest.fixture()
def gyroid():
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    return plan


@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    return tmp_path / "output"


# --------------------------------------------------------------------------
# models: fingerprint, slugs, schemas
# --------------------------------------------------------------------------


def test_fingerprint_is_stable_and_sha256():
    fp = fingerprint_of("a", "b", {"x": 1}, 7)
    assert len(fp) == 64
    assert fp == fingerprint_of("a", "b", {"x": 1}, 7)


def test_fingerprint_sensitive_to_every_input():
    base = fingerprint_of("p", "n", {"w": 1}, 1)
    assert fingerprint_of("p2", "n", {"w": 1}, 1) != base
    assert fingerprint_of("p", "n2", {"w": 1}, 1) != base
    assert fingerprint_of("p", "n", {"w": 2}, 1) != base
    assert fingerprint_of("p", "n", {"w": 1}, 2) != base


def test_topic_slug():
    assert topic_slug("Planetary Gears 2") == "planetary_gears_2"
    assert topic_slug("  ") == "topic"
    assert len(topic_slug("x" * 100)) <= 60


def test_attempt_dir_layout(tmp_path):
    p = attempt_dir(tmp_path, "Planetary Gears", "S2", "attempt_01")
    assert p == tmp_path / "planetary_gears" / "S2" / "attempt_01"


def test_session_config_defaults():
    cfg = SessionConfig()
    assert cfg.max_attempts == 3
    assert cfg.model_key == "sdxl"
    assert cfg.output_root == Path("output/runtime")
    assert cfg.save_artifacts is True


@pytest.mark.parametrize("bad", [0, 11])
def test_session_config_rejects_bad_budget(bad):
    with pytest.raises(ValidationError):
        SessionConfig(max_attempts=bad)


def test_render_request_validates_scene_id():
    ok = RenderRequest(
        attempt_index=1,
        scene_id="S2",
        prompt="p",
        workflow_profile=RenderProfileKey.HERO,
        seed=1,
    )
    assert ok.scene_id == "S2"
    with pytest.raises(ValidationError):
        RenderRequest(
            attempt_index=1,
            scene_id="x2",
            prompt="p",
            workflow_profile=RenderProfileKey.HERO,
            seed=1,
        )


def test_render_request_is_frozen():
    req = RenderRequest(
        attempt_index=1,
        scene_id="S2",
        prompt="p",
        workflow_profile=RenderProfileKey.HERO,
        seed=1,
    )
    with pytest.raises(ValidationError):
        req.seed = 2


def test_render_attempt_validates_fingerprint():
    with pytest.raises(ValidationError):
        RenderAttempt(
            attempt_id="attempt_01",
            index=1,
            status=AttemptStatus.FAILED,
            scene_id="S2",
            prompt="p",
            workflow_profile=RenderProfileKey.HERO,
            seed=1,
            fingerprint="short",
            image_sha256="0" * 64,
        )


def test_session_result_attempts_used_excludes_skipped():
    fp = "a" * 64
    attempts = [
        RenderAttempt(
            attempt_id="attempt_01",
            index=1,
            status=AttemptStatus.FAILED,
            scene_id="S2",
            prompt="p",
            workflow_profile=RenderProfileKey.HERO,
            seed=1,
            fingerprint=fp,
            image_sha256=fp,
        ),
        RenderAttempt(
            attempt_id="attempt_02",
            index=2,
            status=AttemptStatus.SKIPPED_DUPLICATE,
            scene_id="S2",
            prompt="p",
            workflow_profile=RenderProfileKey.HERO,
            seed=1,
            fingerprint=fp,
            image_sha256=fp,
        ),
    ]
    result = RenderSessionResult(
        topic="t", scene_id="S2", seed=1, max_attempts=3, passed=False, attempts=attempts
    )
    assert result.attempts_used == 1
    assert isinstance(result.history, RenderHistory)
    assert len(result.history.attempts) == 2


# --------------------------------------------------------------------------
# renderer: tiny_png and the SimulatedRenderer defect/cure model
# --------------------------------------------------------------------------


def test_tiny_png_deterministic():
    assert tiny_png(1, 1) == tiny_png(1, 1)
    assert tiny_png(1, 1).startswith(b"\x89PNG\r\n\x1a\n")
    assert tiny_png(1, 2) != tiny_png(1, 1)


def _request(scene_id="S2", prompt="macro shot of the part", negative="", seed=1):
    return RenderRequest(
        attempt_index=1,
        scene_id=scene_id,
        prompt=prompt,
        negative_prompt=negative,
        workflow={},
        workflow_profile=RenderProfileKey.MACRO,
        seed=seed,
    )


def test_simulated_renderer_deterministic():
    renderer = SimulatedRenderer()
    a = renderer.render(_request())
    b = renderer.render(_request())
    assert a.metadata.model_dump() == b.metadata.model_dump()
    assert a.image_bytes == b.image_bytes


def test_simulated_renderer_cures_camera():
    renderer = SimulatedRenderer()
    base = renderer.render(_request(seed=4)).metadata
    cured = renderer.render(
        _request(prompt="macro shot of the part, 100mm macro lens, 100mm macro lens", seed=4)
    ).metadata
    assert not (base.camera_distance_matches and base.camera_angle_matches and base.lens_matches)
    assert cured.camera_distance_matches and cured.camera_angle_matches and cured.lens_matches


def test_simulated_renderer_cures_lighting():
    renderer = SimulatedRenderer()
    base = renderer.render(_request(seed=3)).metadata
    cured = renderer.render(
        _request(prompt="key lighting, key lighting", seed=3)
    ).metadata
    assert not (base.lighting_direction_matches and base.lighting_style_matches)
    assert cured.lighting_direction_matches and cured.lighting_style_matches


def test_simulated_renderer_cures_composition_and_clutter():
    renderer = SimulatedRenderer()
    base = renderer.render(_request(seed=4)).metadata
    cured = renderer.render(_request(prompt="focal point on the part", seed=4)).metadata
    assert cured.composition_rule_matches
    assert cured.composition_quality == 0.92
    assert cured.clutter_level <= 0.5
    decluttered = renderer.render(
        _request(prompt="p", negative="clutter", seed=4)
    ).metadata
    assert decluttered.clutter_level == 0.20
    assert base.composition_quality < 0.92


def test_simulated_renderer_cures_accuracy_and_geometry():
    renderer = SimulatedRenderer()
    base = renderer.render(_request(seed=6)).metadata
    cured = renderer.render(
        _request(prompt="engineering visualization, exact silhouettes", seed=6)
    ).metadata
    assert cured.engineering_accuracy == 0.95
    assert cured.geometry_correct and cured.geometry_quality == 0.95
    assert not (base.engineering_accuracy == 0.95)


def test_simulated_renderer_cures_consistency_via_negative():
    renderer = SimulatedRenderer()
    base = renderer.render(_request(seed=2)).metadata
    cured = renderer.render(
        _request(prompt="p", negative="inconsistent color", seed=2)
    ).metadata
    assert cured.scene_consistency == 0.95
    assert cured.consistency_violations == []
    assert base.scene_consistency < 0.95


def test_simulated_renderer_cures_prominence_and_occlusion():
    renderer = SimulatedRenderer()
    base = renderer.render(_request(seed=8)).metadata
    cured = renderer.render(
        _request(prompt="dominating the frame, emphasize the primary subject", seed=8)
    ).metadata
    assert cured.subject_prominence == 0.95
    assert not cured.subject_occluded
    assert not base.subject_occluded or base.subject_prominence < 0.95


def test_simulated_renderer_metadata_always_valid_for_critic():
    """Caps hold: the loop must never crash building a QA report."""
    renderer = SimulatedRenderer()
    critic = ImageCritic()
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    storyboard = StoryboardBuilder().build(plan, engineering_domain=FDM, modality=PHOTOREAL)
    compiled = compile_for_storyboard(storyboard, "sdxl", topic=plan.topic)
    for seed in range(1, 25):
        for scene in storyboard.scenes:
            req = RenderRequest(
                attempt_index=1,
                scene_id=scene.scene_id,
                prompt=compiled.scenes[scene.scene_id].prompt,
                negative_prompt=compiled.scenes[scene.scene_id].negative_prompt or "",
                workflow={},
                workflow_profile=RenderProfileKey.HERO,
                seed=seed,
            )
            result = renderer.render(req)
            report = critic.assess(
                QAContext(
                    plan=plan,
                    storyboard=storyboard,
                    scene=scene,
                    metadata=result.metadata,
                    compiled_prompt=compiled.scenes[scene.scene_id],
                ),
                topic=plan.topic,
            )
            assert report.pass_fail.value in ("pass", "fail")
            assert len(report.repair_suggestions) <= 8


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------


def _cached_result(scene_id="S2"):
    return SimulatedRenderer().render(_request(scene_id=scene_id))


def test_cache_memory_roundtrip():
    cache = RenderCache()
    fp = fingerprint_of("p", None, {}, 1)
    assert not cache.has(fp)
    cache.put(fp, _cached_result())
    assert cache.has(fp)
    assert cache.get(fp).metadata.scene_id == "S2"
    assert len(cache) == 1


def test_cache_disk_roundtrip(tmp_path):
    root = tmp_path / "cache"
    cache = RenderCache(root=root)
    fp = fingerprint_of("p", None, {}, 1)
    entry = cache.put(fp, _cached_result())
    assert entry is not None and entry.exists()
    fresh = RenderCache(root=root)
    assert fresh.has(fp)
    got = fresh.get(fp)
    assert got is not None
    assert got.image_bytes == _cached_result().image_bytes
    assert got.metadata.scene_id == "S2"


def test_cache_has_and_len_disk(tmp_path):
    root = tmp_path / "cache"
    cache = RenderCache(root=root)
    cache.put(fingerprint_of("a", None, {}, 1), _cached_result())
    cache.put(fingerprint_of("b", None, {}, 1), _cached_result("S3"))
    assert len(cache) == 2
    assert cache.has(fingerprint_of("a", None, {}, 1))


# --------------------------------------------------------------------------
# retry manager
# --------------------------------------------------------------------------


def test_retry_budget():
    rm = RetryManager(max_attempts=3)
    assert rm.can_render(0) and rm.can_render(2)
    assert not rm.can_render(3)
    assert rm.remaining(1) == 2
    assert rm.remaining(5) == 0


def test_retry_duplicate_guard():
    rm = RetryManager()
    fp = fingerprint_of("p", None, {}, 1)
    assert not rm.is_duplicate(fp)
    assert rm.classify(fp) is AttemptStatus.RENDERED
    rm.record(fp)
    assert rm.is_duplicate(fp)
    assert rm.classify(fp) is AttemptStatus.SKIPPED_DUPLICATE
    assert rm.executed_fingerprints == (fp,)


# --------------------------------------------------------------------------
# workflow builder
# --------------------------------------------------------------------------


def test_workflow_builder_build_uses_profile():
    builder = WorkflowBuilder()
    prompt = compile_for_storyboard(
        StoryboardBuilder().build(
            EducationalDirector().direct_from_csv(GYROID_ROW), engineering_domain=FDM, modality=PHOTOREAL
        ),
        "sdxl",
        topic="gyroid",
    ).scenes["S2"]
    workflow = builder.build(prompt=prompt, profile=RenderProfileKey.MACRO)
    assert workflow["workflow_version"] == "1.0.0"
    assert workflow["profile"] == "macro"
    assert workflow["sampler"] == "dpmpp_2m"
    assert workflow["resolution"] == "832x1216"
    assert workflow["positive_prompt"] == prompt.prompt
    assert "nodes" in workflow


def test_workflow_regenerate_unchanged_when_nothing_prescribed(planetary):
    builder = WorkflowBuilder()
    prompt = compile_for_storyboard(
        StoryboardBuilder().build(planetary, engineering_domain=MECHANISMS, modality=PHOTOREAL),
        "sdxl",
        topic=planetary.topic,
    ).scenes["S2"]
    workflow = builder.build(prompt=prompt, profile=RenderProfileKey.HERO)
    plan = OptimizationEngine().optimize(
        _minimal_failing_report(planetary), scene=None, compiled_prompt=prompt
    )
    plan.workflow_changes.clear()
    plan.visualization_changes.clear()
    rebuilt = builder.regenerate(plan, workflow)
    assert rebuilt == workflow


def test_workflow_regenerate_switches_profile_and_tokens(planetary):
    builder = WorkflowBuilder()
    prompt = compile_for_storyboard(
        StoryboardBuilder().build(planetary, engineering_domain=MECHANISMS, modality=PHOTOREAL),
        "sdxl",
        topic=planetary.topic,
    ).scenes["S2"]
    workflow = builder.build(prompt=prompt, profile=RenderProfileKey.HERO)
    plan = OptimizationEngine().optimize(
        _minimal_failing_report(planetary), scene=None, compiled_prompt=prompt
    )
    plan.workflow_changes.append(
        WorkflowChange(profile=RenderProfileKey.CUTAWAY, rationale="plan")
    )
    plan.visualization_changes.append(
        VisualizationChange(
            type="cross section",
            elements=("cut",),
            prompt_tokens=("cutaway cross-section view",),
            rationale="plan",
        )
    )
    rebuilt = builder.regenerate(plan, workflow)
    assert rebuilt["profile"] == "cutaway"
    assert "cutaway cross-section view" in rebuilt["nodes"]["visualization"]
    assert rebuilt != workflow


# --------------------------------------------------------------------------
# storyboard builder
# --------------------------------------------------------------------------


def test_storyboard_five_scene_arc(planetary):
    storyboard = StoryboardBuilder().build(
        planetary, engineering_domain=MECHANISMS, modality=PHOTOREAL
    )
    assert len(storyboard.scenes) == 5
    assert [s.scene_id for s in storyboard.scenes] == [f"S{i}" for i in range(1, 6)]
    assert storyboard.thumbnail_scene_id == "S5"
    assert storyboard.scenes[-1].thumbnail_candidate is True
    assert all(not s.thumbnail_candidate for s in storyboard.scenes[:-1])
    assert storyboard.topic == planetary.topic


def test_storyboard_shot_mapping():
    from runtime.storyboard_builder import _shot_for_method

    builder = StoryboardBuilder()
    plan = EducationalDirector().direct_from_csv(PLANETARY_ROW)
    storyboard = builder.build(plan, engineering_domain=MECHANISMS, modality=PHOTOREAL)
    assert storyboard.scenes[1].intent.engineering_visualizations[0].type == "cross section"
    expected = {
        "comparison board": ShotType.COMPARISON_SPLIT,
        "cross section": ShotType.CROSS_SECTION,
        "exploded view": ShotType.EXPLODED_VIEW,
        "macro": ShotType.MACRO,
        "xray": ShotType.XRAY,
        "not a method": ShotType.HERO,
    }
    for method, shot in expected.items():
        assert _shot_for_method(method) is shot


def test_storyboard_matches_knowledge_stack(planetary):
    """The runtime storyboard must mirror the knowledge example stack."""
    from knowledge.image_qa.examples._stack import build_stack, default_specs

    runtime_sb = StoryboardBuilder().build(
        planetary, engineering_domain=MECHANISMS, modality=PHOTOREAL
    )
    knowledge_sb, _, _ = build_stack(
        planetary,
        domain=MECHANISMS,
        modality=PHOTOREAL,
        specs=default_specs(planetary),
        thumbnail_scene_id="S5",
        renders=[],
    )
    for runtime_scene, knowledge_scene in zip(
        runtime_sb.scenes, knowledge_sb.scenes, strict=True
    ):
        assert runtime_scene.model_dump() == knowledge_scene.model_dump()
    assert runtime_sb.thumbnail_scene_id == knowledge_sb.thumbnail_scene_id
    assert runtime_sb.topic == knowledge_sb.topic


# --------------------------------------------------------------------------
# render loop
# --------------------------------------------------------------------------


def _run_scene(row, scene_id, seed, renderer, domain, max_attempts=3, output_root=None):
    session = RenderSession(renderer=renderer)
    return session.run(
        row,
        scene_id,
        seed=seed,
        engineering_domain=domain,
        modality=PHOTOREAL,
        config=SessionConfig(output_root=output_root, max_attempts=max_attempts),
    )


def test_loop_passes_first_attempt(tmp_path):
    result = _run_scene(
        GYROID_ROW, "S2", seed=29, renderer=SimulatedRenderer(), domain=FDM,
        output_root=tmp_path / "out",
    )
    assert result.passed
    assert result.attempts_used == 1
    assert result.winner is not None and result.winner.attempt_id == "attempt_01"
    assert result.winner.status is AttemptStatus.PASSED
    assert result.winner.optimization_report is None


def test_loop_full_repair(tmp_path):
    out = tmp_path / "out"
    result = _run_scene(
        PLANETARY_ROW, "S2", seed=42, renderer=SimulatedRenderer(), domain=MECHANISMS,
        output_root=out,
    )
    assert result.passed
    assert [a.status for a in result.attempts] == [AttemptStatus.FAILED, AttemptStatus.PASSED]
    first, second = result.attempts
    assert first.optimization_report is not None
    assert len(first.optimization_report.optimization_actions) > 0
    assert second.qa_report is not None
    assert second.qa_report.overall_score > first.qa_report.overall_score
    assert second.optimization_report is None
    # artifacts on disk
    attempt_dir1 = out / topic_slug(result.topic) / "S2" / "attempt_01"
    for name in ("prompt.txt", "prompt_negative.txt", "workflow.json",
                 "qa_report.json", "optimization_report.json", "image.png", "attempt.json"):
        assert (attempt_dir1 / name).is_file(), name
    assert first.image_path is not None and first.image_path.name == "image.png"
    assert first.image_path.read_bytes().startswith(b"\x89PNG")


def test_loop_budget_exhaustion(tmp_path):
    result = _run_scene(
        PLANETARY_ROW, "S2", seed=3, renderer=AlwaysBadRenderer(), domain=MECHANISMS,
        max_attempts=3, output_root=tmp_path / "out",
    )
    assert not result.passed
    assert result.winner is None
    assert len(result.attempts) == 3
    assert all(a.status is AttemptStatus.FAILED for a in result.attempts)
    assert result.attempts_used == 3


def test_loop_catastrophic_failure_stays_valid(tmp_path):
    """Every check failing must still yield valid reports and plans."""
    result = _run_scene(
        PLANETARY_ROW, "S2", seed=1, renderer=AlwaysBadRenderer(all_failing=True),
        domain=MECHANISMS, max_attempts=3, output_root=tmp_path / "out",
    )
    assert not result.passed
    assert len(result.attempts) == 3
    for attempt in result.attempts:
        assert attempt.qa_report is not None
        assert len(attempt.qa_report.repair_suggestions) <= 8
        if attempt.optimization_report is not None:
            assert len(attempt.optimization_report.optimization_actions) <= 24


def test_loop_duplicate_skip(tmp_path):
    plan = EducationalDirector().direct_from_csv(PLANETARY_ROW)
    storyboard = StoryboardBuilder().build(
        plan, engineering_domain=MECHANISMS, modality=PHOTOREAL
    )
    scene = next(s for s in storyboard.scenes if s.scene_id == "S2")
    retry = RetryManager(max_attempts=3)
    loop = RenderLoop(renderer=SimulatedRenderer(), retry_manager=retry)
    cfg = SessionConfig(output_root=tmp_path / "out")
    first = loop.run(plan=plan, storyboard=storyboard, scene=scene, topic=plan.topic,
                     seed=7, config=cfg)
    second = loop.run(plan=plan, storyboard=storyboard, scene=scene, topic=plan.topic,
                      seed=7, config=cfg)
    assert first.passed
    assert len(second.attempts) == 1
    assert second.attempts[0].status is AttemptStatus.SKIPPED_DUPLICATE
    assert second.attempts_used == 0
    assert not second.passed


def test_loop_never_repeats_identical_render(tmp_path):
    result = _run_scene(
        PLANETARY_ROW, "S2", seed=7, renderer=SimulatedRenderer(), domain=MECHANISMS,
        output_root=tmp_path / "out",
    )
    fingerprints = [a.fingerprint for a in result.attempts]
    assert len(fingerprints) == len(set(fingerprints))


def test_loop_save_artifacts_false(tmp_path):
    out = tmp_path / "out"
    session = RenderSession(renderer=SimulatedRenderer())
    result = session.run(
        PLANETARY_ROW, "S2", seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
        config=SessionConfig(output_root=out, save_artifacts=False),
    )
    assert result.passed
    assert all(a.image_path is None for a in result.attempts)
    assert list(out.glob("*")) == []


def test_loop_cache_reuse_across_runs(tmp_path):
    counting = CountingRenderer()
    session = RenderSession(renderer=counting)
    cfg = SessionConfig(output_root=tmp_path / "out")
    r1 = session.run(
        PLANETARY_ROW, "S2", seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
        config=cfg,
    )
    r2 = session.run(
        PLANETARY_ROW, "S2", seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
        config=cfg,
    )
    assert counting.renders == 2
    assert r1.passed and r2.passed
    assert r1.model_dump(mode="json") == r2.model_dump(mode="json")
    assert r1.attempts[0].image_sha256 == r2.attempts[0].image_sha256


# --------------------------------------------------------------------------
# render session
# --------------------------------------------------------------------------


def test_session_run_all_five_scenes(tmp_path):
    session = RenderSession(renderer=SimulatedRenderer())
    results = session.run_all(
        PLANETARY_ROW, seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
        config=SessionConfig(output_root=tmp_path / "out"),
    )
    assert list(results) == ["S1", "S2", "S3", "S4", "S5"]
    assert all(r.passed for r in results.values())
    for scene_id, result in results.items():
        history_path = tmp_path / "out" / topic_slug(result.topic) / scene_id / "history.json"
        assert history_path.is_file()


def test_session_history_saved_and_replayable(tmp_path):
    session = RenderSession(renderer=SimulatedRenderer())
    result = session.run(
        PLANETARY_ROW, "S2", seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
        config=SessionConfig(output_root=tmp_path / "out"),
    )
    history_path = tmp_path / "out" / topic_slug(result.topic) / "S2" / "history.json"
    replayed = replay(history_path)
    verify_replay_identical(result, replayed)
    assert replayed.passed


def test_session_determinism(tmp_path):
    def run_once():
        session = RenderSession(renderer=SimulatedRenderer())
        return session.run(
            PLANETARY_ROW, "S2", seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
            config=SessionConfig(output_root=tmp_path / "out"),
        )

    a, b = run_once(), run_once()
    assert a.model_dump(mode="json") == b.model_dump(mode="json")
    assert [x.prompt for x in a.attempts] == [x.prompt for x in b.attempts]


def test_replay_from_every_input(tmp_path):
    session = RenderSession(renderer=SimulatedRenderer())
    result = session.run(
        PLANETARY_ROW, "S2", seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
        config=SessionConfig(output_root=tmp_path / "out"),
    )
    history = result.history
    assert replay(history).model_dump(mode="json") == result.model_dump(mode="json")
    history_path = tmp_path / "out" / topic_slug(result.topic) / "S2" / "history.json"
    assert replay(history_path).model_dump(mode="json") == result.model_dump(mode="json")
    raw = history_path.read_text(encoding="utf-8")
    assert replay(raw).model_dump(mode="json") == result.model_dump(mode="json")
    assert replay(json.loads(raw)).model_dump(mode="json") == result.model_dump(mode="json")


def test_verify_replay_identical_detects_tampering(tmp_path):
    session = RenderSession(renderer=SimulatedRenderer())
    result = session.run(
        PLANETARY_ROW, "S2", seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
        config=SessionConfig(output_root=tmp_path / "out"),
    )
    history_path = tmp_path / "out" / topic_slug(result.topic) / "S2" / "history.json"
    tampered = json.loads(history_path.read_text(encoding="utf-8"))
    tampered["attempts"][0]["prompt"] = "tampered prompt"
    replayed = replay(tampered)
    with pytest.raises(AssertionError):
        verify_replay_identical(result, replayed)


def test_injection_session_converges(tmp_path):
    session = RenderSession(renderer=SimulatedRenderer())
    result = session.run(
        INJECTION_ROW, "S2", seed=42, engineering_domain=EngineeringDomain.INJECTION_MOLDING,
        modality=PHOTOREAL, config=SessionConfig(output_root=tmp_path / "out"),
    )
    assert result.passed
    assert len(result.attempts) == 2


# --------------------------------------------------------------------------
# history
# --------------------------------------------------------------------------


def test_history_evolutions_and_scores(tmp_path):
    session = RenderSession(renderer=SimulatedRenderer())
    result = session.run(
        PLANETARY_ROW, "S2", seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
        config=SessionConfig(output_root=tmp_path / "out"),
    )
    history = result.history
    evolution = history.prompt_evolution()
    assert [p.attempt_id for p in evolution] == ["attempt_01", "attempt_02"]
    assert evolution[0].prompt != evolution[1].prompt
    workflows = history.workflow_evolution()
    assert [w.profile for w in workflows] == [a.workflow_profile.value for a in result.attempts]
    scores = history.qa_scores()
    assert len(scores) == 2
    assert scores[0].overall == result.attempts[0].qa_report.overall_score
    assert scores[1].verdict == "pass"
    actions = history.optimization_actions()
    assert actions
    assert actions[0].attempt_id == "attempt_01"
    assert all(a.expected_gain > 0 for a in actions)
    assert history.winner is result.winner
    assert history.passed is True
    assert history.attempts_used == 2


def test_history_roundtrip(tmp_path):
    session = RenderSession(renderer=SimulatedRenderer())
    result = session.run(
        PLANETARY_ROW, "S2", seed=42, engineering_domain=MECHANISMS, modality=PHOTOREAL,
        config=SessionConfig(output_root=tmp_path / "out"),
    )
    path = tmp_path / "history.json"
    result.history.to_file(path)
    loaded = RenderHistory.from_file(path)
    assert loaded.model_dump() == result.history.model_dump()
    assert loaded.to_session_result().model_dump(mode="json") == result.model_dump(mode="json")


# --------------------------------------------------------------------------
# knowledge-layer hardening caps (surfaced by the runtime loop)
# --------------------------------------------------------------------------


def _minimal_failing_report(plan):
    critic = ImageCritic()
    storyboard = StoryboardBuilder().build(plan, engineering_domain=MECHANISMS, modality=PHOTOREAL)
    scene = storyboard.scenes[1]
    compiled = compile_for_storyboard(storyboard, "sdxl", topic=plan.topic)
    metadata = SimulatedRenderer().render(
        RenderRequest(
            attempt_index=1,
            scene_id=scene.scene_id,
            prompt=compiled.scenes[scene.scene_id].prompt,
            negative_prompt=compiled.scenes[scene.scene_id].negative_prompt or "",
            workflow={},
            workflow_profile=RenderProfileKey.HERO,
            seed=1,
        )
    ).metadata
    return critic.assess(
        QAContext(
            plan=plan, storyboard=storyboard, scene=scene, metadata=metadata,
            compiled_prompt=compiled.scenes[scene.scene_id],
        ),
        topic=plan.topic,
    )


def test_repair_suggestions_capped_at_eight():
    issues = [
        QAIssue(check=check, severity="minor", message=f"issue {check.value}")
        for check in QACheck
    ]
    suggestions = RenderRepairEngine().suggest(issues)
    assert len(suggestions) <= 8


def test_optimization_actions_capped_at_twenty_four():
    """A catastrophically failing report must still produce a valid plan."""
    critic = ImageCritic()
    plan = EducationalDirector().direct_from_csv(PLANETARY_ROW)
    storyboard = StoryboardBuilder().build(plan, engineering_domain=MECHANISMS, modality=PHOTOREAL)
    scene = storyboard.scenes[1]
    compiled = compile_for_storyboard(storyboard, "sdxl", topic=plan.topic)
    report = critic.assess(
        QAContext(
            plan=plan,
            storyboard=storyboard,
            scene=scene,
            metadata=_bad_metadata("S2", all_failing=True),
            compiled_prompt=compiled.scenes["S2"],
        ),
        topic=plan.topic,
    )
    assert len(report.issues) >= 9
    repair_plan = OptimizationEngine().optimize(report, scene=scene, compiled_prompt=compiled.scenes["S2"])
    assert len(repair_plan.optimization_actions) <= 24


def test_runtime_version_export():
    from runtime import RUNTIME_VERSION

    assert RUNTIME_VERSION == "1.0.0"