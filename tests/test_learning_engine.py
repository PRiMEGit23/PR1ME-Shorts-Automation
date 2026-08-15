"""Learning Engine tests (Phase 11): the self-improving observer.

Covers the deterministic learning engine over completed pipeline runs:

- the input contract: histories validate run order and scene ids
- patterns: winner-vs-rest comparisons on qa / attempts / retention, with
  the minimum-sample and minimum-delta thresholds enforced
- proposals: all six kinds (model, director, compiler, workflow, knowledge,
  optimization) and the calibration of registry capabilities
- knowledge diffs: the before/after edit behind every proposal
- the eight leaderboards and the overall statistics
- determinism: the same history always produces the same report and the
  same exported bytes
- the knowledge base stays immutable: learning never changes the registry
- historical replay and trends ordered by the caller-supplied run index
- performance: a thousand-scene history learns within the budget
- the worked examples: real runs collected through the production stack

All tests run offline; rendering is the SimulatedRenderer.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from knowledge.learning_engine import LearningEngine, PipelineHistory
from knowledge.learning_engine.examples._collector import (
    SOURCE_ROWS,
    collect_film,
    collect_history,
)
from knowledge.learning_engine.improvement_generator import generate_proposals
from knowledge.learning_engine.knowledge_diff import build_diff
from knowledge.learning_engine.learning_models import (
    LEARNING_ENGINE_VERSION,
    CompilerRecommendation,
    DirectorRecommendation,
    KnowledgeProposal,
    ModelRecommendation,
    OptimizationRecommendation,
    ProjectRecord,
    SceneObservation,
    WorkflowRecommendation,
)
from knowledge.learning_engine.learning_rules import (
    MAX_PATTERNS,
    MAX_PROPOSALS,
    MIN_GROUP_SAMPLES,
)
from knowledge.learning_engine.pattern_detector import detect_patterns
from knowledge.learning_engine.quality_statistics import (
    all_qa_leaderboards,
    overall_stats,
)
from knowledge.learning_engine.report_generator import (
    build_trend_report_payload,
    export_reports,
)
from knowledge.model_director.model_registry import REGISTRY
from knowledge.visual_architecture import (
    CameraAngle,
    CameraDistance,
    Framing,
    Lens,
    LightDirection,
    LightingStyle,
    TransitionType,
)
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualizationType,
    ShotType,
)
from pydantic import ValidationError

# ---------------------------------------------------------------- builders --

_BASE = dict(
    camera_distance=CameraDistance.MEDIUM,
    camera_angle=CameraAngle.EYE,
    framing=Framing.TIGHT,
    light_direction=LightDirection.KEY,
    lighting_style=LightingStyle.SOFTBOX,
    video_model="hiredream",
    quality_target="balanced",
    thumbnail_priority=0,
    prompt_mutations=0,
    optimization_actions=0,
    vram_mb=24,
)


def _scene(
    run_id: str,
    scene_id: str,
    *,
    topic: str,
    shot_type: ShotType,
    image_model: str,
    qa: float,
    predicted: float = 85.0,
    passed: bool = True,
    attempts: int = 1,
    educational: float = 80.0,
    retention: float = 70.0,
    switches: int = 0,
    negative: tuple[str, ...] = (),
    render_profile: str = "balanced",
    viz: EngineeringVisualizationType | None = None,
    lens: Lens = Lens.PORTRAIT_50,
    transition: TransitionType = TransitionType.FADE,
) -> SceneObservation:
    index = int(scene_id[1:])
    return SceneObservation(
        run_id=run_id,
        scene_id=scene_id,
        scene_index=index,
        seed=42,
        topic=topic,
        shot_type=shot_type,
        image_model=image_model,
        predicted_qa=predicted,
        qa_score=qa,
        educational_score=educational,
        retention_prediction=retention,
        attempts=attempts,
        failed_attempts=attempts - 1 if passed else attempts,
        model_switches=switches,
        render_duration_ms=5000.0,
        negative_tokens=negative,
        passed=passed,
        visualization_type=viz,
        render_profile=render_profile,
        lens=lens,
        transition_type=transition,
        **_BASE,
    )


def _project(
    run_id: str,
    run_index: int,
    scenes: list[SceneObservation],
    *,
    topic: str,
    status: str = "complete",
) -> ProjectRecord:
    return ProjectRecord(
        run_id=run_id,
        run_index=run_index,
        topic=topic,
        seed=42,
        total_duration_ms=float(sum(s.render_duration_ms for s in scenes)),
        status=status,
        scenes=tuple(scenes),
    )


def _winner_history() -> PipelineHistory:
    """gpt-image/hero beats flux-dev/hero by ~12 QA; macro lags behind."""
    projects: list[ProjectRecord] = []
    index = 0
    for i in range(6):
        projects.append(
            _project(
                f"w{i}", index,
                [
                    _scene(
                        f"w{i}", "S1", topic="gyroid", shot_type=ShotType.HERO,
                        image_model="gpt-image", qa=92.0, predicted=90.0,
                    )
                ],
                topic="gyroid",
            )
        )
        index += 1
        projects.append(
            _project(
                f"l{i}", index,
                [
                    _scene(
                        f"l{i}", "S1", topic="planetary_gear",
                        shot_type=ShotType.HERO, image_model="flux-dev",
                        qa=80.0, predicted=80.0,
                    )
                ],
                topic="planetary_gear",
            )
        )
        index += 1
    for i in range(4):
        projects.append(
            _project(
                f"o{i}", index,
                [
                    _scene(
                        f"o{i}", "S1", topic="injection_molding",
                        shot_type=ShotType.MACRO, image_model="flux-dev",
                        qa=70.0, predicted=75.0,
                    )
                ],
                topic="injection_molding",
            )
        )
        index += 1
    return PipelineHistory(projects=tuple(projects))


# ------------------------------------------------------------ input rules --


class TestHistoryValidation:
    def test_empty_history_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PipelineHistory(projects=())

    def test_duplicate_run_index_rejected(self) -> None:
        scene_a = _scene("a", "S1", topic="t", shot_type=ShotType.HERO,
                         image_model="sdxl", qa=80.0)
        scene_b = _scene("b", "S1", topic="t", shot_type=ShotType.HERO,
                         image_model="sdxl", qa=80.0)
        with pytest.raises(ValidationError):
            PipelineHistory(
                projects=(
                    _project("a", 0, [scene_a], topic="t"),
                    _project("b", 0, [scene_b], topic="t"),
                )
            )

    def test_non_consecutive_scene_ids_rejected(self) -> None:
        scene = _scene("a", "S2", topic="t", shot_type=ShotType.HERO,
                       image_model="sdxl", qa=80.0)
        with pytest.raises(ValidationError):
            _project("a", 0, [scene], topic="t")

    def test_scene_run_id_mismatch_rejected(self) -> None:
        scene = _scene("other-run", "S1", topic="t", shot_type=ShotType.HERO,
                       image_model="sdxl", qa=80.0)
        with pytest.raises(ValidationError):
            _project("a", 0, [scene], topic="t")


# ------------------------------------------------------------- statistics --


class TestStatistics:
    def test_overall_stats(self) -> None:
        overall = overall_stats(_winner_history())
        assert overall.scene_count == 16
        assert overall.passed_scenes == 16
        assert overall.pass_rate == 1.0
        assert overall.mean_qa == pytest.approx(82.0, abs=0.1)
        assert overall.total_switches == 0
        assert overall.mean_attempts == 1.0

    def test_eight_leaderboards_present(self) -> None:
        report = LearningEngine().learn(_winner_history())
        assert sorted(report.leaderboards) == [
            "engineering_visualization",
            "model",
            "prompt",
            "qa",
            "render",
            "topic",
            "visual_strategy",
            "workflow",
        ]

    def test_qa_leaderboard_sorted_and_complete(self) -> None:
        rows = all_qa_leaderboards(_winner_history())["model"]
        assert [row.key for row in rows] == ["gpt-image", "flux-dev"]
        assert rows[0].mean > rows[1].mean
        assert rows[0].count == 6
        assert rows[1].count == 10

    def test_success_profiles_ordered(self) -> None:
        report = LearningEngine().learn(_winner_history())
        assert report.success_profiles
        assert report.success_profiles[0].pass_rate == 1.0

    def test_failure_profiles_only_for_failures(self) -> None:
        report = LearningEngine().learn(_winner_history())
        assert report.failure_profiles == ()

    def test_trends_follow_run_index(self) -> None:
        trends = build_trend_report_payload(_winner_history())["trends"]
        indexes = [trend["run_index"] for trend in trends]
        assert indexes == sorted(indexes)
        assert trends[0]["run_id"] == "w0"
        assert trends[-1]["run_id"] == "o3"

    def test_trend_window_summary(self) -> None:
        payload = build_trend_report_payload(_winner_history())
        assert payload["window_summary"]["window"] == 5
        assert payload["window_summary"]["qa_first_window"] is not None
        assert payload["window_summary"]["qa_last_window"] is not None


# ---------------------------------------------------------------- patterns --


class TestPatterns:
    def test_qa_pattern_detected(self) -> None:
        patterns = detect_patterns(_winner_history())
        winner = next(p for p in patterns if p.pattern_id == "qa-image_model-gpt_image")
        assert winner.winner == "gpt-image"
        assert winner.metric == "qa"
        assert winner.delta == pytest.approx(16.0, abs=0.1)
        assert winner.confidence >= 0.5
        assert len(winner.evidence_scenes) == 6
        assert winner.evidence_scenes[0] == "w0:S1"

    def test_min_samples_gate(self) -> None:
        projects = []
        for i in range(2):
            projects.append(
                _project(f"w{i}", i, [
                    _scene(f"w{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="gpt-image", qa=95.0)
                ], topic="t")
            )
        for i in range(6):
            projects.append(
                _project(f"l{i}", i + 2, [
                    _scene(f"l{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="flux-dev", qa=80.0)
                ], topic="t")
            )
        patterns = detect_patterns(PipelineHistory(projects=tuple(projects)))
        assert all(p.pattern_id != "qa-image_model-gpt_image" for p in patterns)

    def test_min_delta_gate(self) -> None:
        projects = [
            _project(f"w{i}", i, [
                _scene(f"w{i}", "S1", topic="t", shot_type=ShotType.HERO,
                       image_model="gpt-image", qa=81.0)
            ], topic="t")
            for i in range(MIN_GROUP_SAMPLES)
        ] + [
            _project(f"l{i}", i + MIN_GROUP_SAMPLES, [
                _scene(f"l{i}", "S1", topic="t", shot_type=ShotType.HERO,
                       image_model="flux-dev", qa=80.0)
            ], topic="t")
            for i in range(MIN_GROUP_SAMPLES)
        ]
        patterns = detect_patterns(PipelineHistory(projects=tuple(projects)))
        assert all(p.pattern_id != "qa-image_model-gpt_image" for p in patterns)

    def test_attempts_pattern_lower_is_better(self) -> None:
        projects: list[ProjectRecord] = []
        for i in range(4):
            projects.append(
                _project(f"w{i}", i, [
                    _scene(f"w{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="gpt-image", qa=85.0, attempts=1)
                ], topic="t")
            )
            projects.append(
                _project(f"l{i}", i + 4, [
                    _scene(f"l{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="flux-dev", qa=85.0, attempts=3)
                ], topic="t")
            )
        patterns = detect_patterns(PipelineHistory(projects=tuple(projects)))
        winner = next(p for p in patterns
                      if p.pattern_id == "attempts-image_model-gpt_image")
        assert winner.better_when_lower is True
        assert winner.delta == pytest.approx(2.0, abs=0.01)
        assert winner.winner == "gpt-image"

    def test_retention_pattern_by_transition(self) -> None:
        projects: list[ProjectRecord] = []
        for i in range(4):
            projects.append(
                _project(f"w{i}", i, [
                    _scene(f"w{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="flux-dev", qa=80.0, retention=90.0,
                           transition=TransitionType.WIPE)
                ], topic="t")
            )
            projects.append(
                _project(f"l{i}", i + 4, [
                    _scene(f"l{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="flux-dev", qa=80.0, retention=60.0,
                           transition=TransitionType.CUT)
                ], topic="t")
            )
        patterns = detect_patterns(PipelineHistory(projects=tuple(projects)))
        winner = next(p for p in patterns
                      if p.pattern_id == "retention-transition_type-wipe")
        assert winner.metric == "retention"
        assert winner.delta == pytest.approx(30.0, abs=0.1)

    def test_pattern_cap(self) -> None:
        assert len(detect_patterns(_winner_history())) <= MAX_PATTERNS


# -------------------------------------------------------------- proposals --


class TestProposals:
    def test_model_proposal(self) -> None:
        report = LearningEngine().learn(_winner_history())
        proposals = [p for p in report.proposals if isinstance(p, ModelRecommendation)]
        assert proposals
        proposal = next(p for p in proposals if p.to_model == "gpt-image")
        assert proposal.predicted_qa_gain == pytest.approx(16.0, abs=0.1)
        assert proposal.affected_modules

    def test_director_proposal(self) -> None:
        report = LearningEngine().learn(_winner_history())
        proposals = [p for p in report.proposals
                     if isinstance(p, DirectorRecommendation)]
        assert any(p.area == "shot selection" for p in proposals)

    def test_compiler_proposal_for_negative_tokens(self) -> None:
        projects: list[ProjectRecord] = []
        for i in range(4):
            projects.append(
                _project(f"w{i}", i, [
                    _scene(f"w{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="flux-dev", qa=92.0,
                           negative=("low quality", "blurry"))
                ], topic="t")
            )
            projects.append(
                _project(f"l{i}", i + 4, [
                    _scene(f"l{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="flux-dev", qa=78.0)
                ], topic="t")
            )
        report = LearningEngine().learn(PipelineHistory(projects=tuple(projects)))
        proposals = [p for p in report.proposals
                     if isinstance(p, CompilerRecommendation)]
        assert any(p.token == "low quality+blurry" for p in proposals)

    def test_workflow_proposal(self) -> None:
        projects: list[ProjectRecord] = []
        for i in range(4):
            projects.append(
                _project(f"w{i}", i, [
                    _scene(f"w{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="flux-dev", qa=92.0,
                           render_profile="premium")
                ], topic="t")
            )
            projects.append(
                _project(f"l{i}", i + 4, [
                    _scene(f"l{i}", "S1", topic="t", shot_type=ShotType.HERO,
                           image_model="flux-dev", qa=78.0)
                ], topic="t")
            )
        report = LearningEngine().learn(PipelineHistory(projects=tuple(projects)))
        proposals = [p for p in report.proposals
                     if isinstance(p, WorkflowRecommendation)]
        assert any(p.suggested_profile == "premium" for p in proposals)

    def test_topic_knowledge_proposal(self) -> None:
        report = LearningEngine().learn(_winner_history())
        proposals = [p for p in report.proposals
                     if isinstance(p, KnowledgeProposal)
                     and p.knowledge_table == "assets/knowledge_base.csv"]
        assert any(p.entry_key == "gyroid" for p in proposals)

    def test_calibration_proposal(self) -> None:
        projects = [
            _project(f"m{i}", i, [
                _scene(f"m{i}", "S1", topic="t", shot_type=ShotType.MACRO,
                       image_model="gpt-image", qa=80.0, predicted=90.0)
            ], topic="t")
            for i in range(MIN_GROUP_SAMPLES)
        ]
        report = LearningEngine().learn(PipelineHistory(projects=tuple(projects)))
        calibrations = [
            p for p in report.proposals
            if isinstance(p, KnowledgeProposal)
            and p.knowledge_table == "model_registry"
        ]
        assert calibrations
        proposal = calibrations[0]
        assert proposal.field == "macro_detail"
        before = float(proposal.before)
        after = float(proposal.after)
        assert after == pytest.approx(before - 5.0, abs=0.1)

    def test_calibration_gate(self) -> None:
        projects = [
            _project(f"m{i}", i, [
                _scene(f"m{i}", "S1", topic="t", shot_type=ShotType.MACRO,
                       image_model="gpt-image", qa=90.0, predicted=90.5)
            ], topic="t")
            for i in range(MIN_GROUP_SAMPLES)
        ]
        report = LearningEngine().learn(PipelineHistory(projects=tuple(projects)))
        calibrations = [
            p for p in report.proposals
            if isinstance(p, KnowledgeProposal)
            and p.knowledge_table == "model_registry"
        ]
        assert not calibrations

    def test_optimizer_proposal_without_switches(self) -> None:
        report = LearningEngine().learn(_failed_history(switches=0))
        proposals = [p for p in report.proposals
                     if isinstance(p, OptimizationRecommendation)]
        assert any("never_switched" in p.optimizer_rule for p in proposals)

    def test_optimizer_proposal_with_switches(self) -> None:
        report = LearningEngine().learn(_failed_history(switches=2))
        proposals = [p for p in report.proposals
                     if isinstance(p, OptimizationRecommendation)]
        assert any("switches_did_not_rescue" in p.optimizer_rule for p in proposals)

    def test_min_failed_gate_for_optimizer(self) -> None:
        projects = [
            _project(
                f"f{i}", i,
                [_scene(f"f{i}", "S1", topic="t", shot_type=ShotType.HERO,
                        image_model="flux-dev", qa=50.0, passed=False,
                        attempts=3)],
                topic="t",
            )
            for i in range(2)
        ]
        report = LearningEngine().learn(PipelineHistory(projects=tuple(projects)))
        assert not [p for p in report.proposals
                    if isinstance(p, OptimizationRecommendation)]

    def test_proposals_sorted_by_confidence(self) -> None:
        report = LearningEngine().learn(_winner_history())
        confidences = [p.confidence for p in report.proposals]
        assert confidences == sorted(confidences, reverse=True)
        assert len(report.proposals) <= MAX_PROPOSALS

    def test_calibration_and_model_kinds_reachable(self) -> None:
        """Calibration + patterns together produce knowledge and model kinds."""
        report = LearningEngine().learn(_winner_history())
        assert any(isinstance(p, KnowledgeProposal) for p in report.proposals)
        assert any(isinstance(p, ModelRecommendation) for p in report.proposals)


def _failed_history(*, switches: int) -> PipelineHistory:
    projects: list[ProjectRecord] = []
    for i in range(4):
        projects.append(
            _project(
                f"f{i}", i,
                [_scene(f"f{i}", "S1", topic="t", shot_type=ShotType.HERO,
                        image_model="flux-dev", qa=52.0, passed=False,
                        attempts=3, switches=switches)],
                topic="t",
            )
        )
        projects.append(
            _project(
                f"g{i}", i + 4,
                [_scene(f"g{i}", "S1", topic="t", shot_type=ShotType.HERO,
                        image_model="gpt-image", qa=90.0)],
                topic="t",
            )
        )
    return PipelineHistory(projects=tuple(projects))


# ------------------------------------------------------------------ diffs --


class TestKnowledgeDiffs:
    def test_diff_round_trip(self) -> None:
        report = LearningEngine().learn(_winner_history())
        for proposal in report.proposals:
            diff = build_diff(proposal)
            if diff is None:
                continue
            assert diff.proposal_kind is proposal.kind
            assert diff.confidence == proposal.confidence
            assert diff.evidence == proposal.evidence
            assert diff.reason == proposal.reason

    def test_diff_before_after_for_calibration(self) -> None:
        report = LearningEngine().learn(_winner_history())
        calibration = next(
            p for p in report.proposals
            if isinstance(p, KnowledgeProposal)
            and p.knowledge_table == "model_registry"
        )
        diff = build_diff(calibration)
        assert diff is not None
        assert diff.table == "model_registry"
        assert diff.field == calibration.field
        assert diff.before == calibration.before
        assert diff.after == calibration.after
        assert diff.module == "knowledge/model_director/model_registry.py"

    def test_knowledge_base_immutable(self) -> None:
        before = REGISTRY.get("gpt-image").macro_detail
        LearningEngine().learn(_winner_history())
        assert REGISTRY.get("gpt-image").macro_detail == before


# ------------------------------------------------------------ determinism --


class TestDeterminism:
    def test_learn_is_pure(self) -> None:
        history = _winner_history()
        first = LearningEngine().learn(history)
        second = LearningEngine().learn(history)
        assert first.model_dump() == second.model_dump()

    def test_export_is_byte_identical(self, tmp_path: Path) -> None:
        history = _winner_history()
        report = LearningEngine().learn(history)
        first = export_reports(report, history, tmp_path / "a")
        second = export_reports(report, history, tmp_path / "b")
        assert sorted(first) == sorted(second)
        for name, path in first.items():
            assert path.read_bytes() == second[name].read_bytes()

    def test_export_writes_four_json_reports(self, tmp_path: Path) -> None:
        history = _winner_history()
        report = LearningEngine().learn(history)
        written = export_reports(report, history, tmp_path)
        assert sorted(written) == [
            "knowledge_proposals.json",
            "learning_report.json",
            "performance_dashboard.json",
            "trend_report.json",
        ]
        payload = json.loads(
            (tmp_path / "learning_report.json").read_text(encoding="utf-8")
        )
        assert payload["version"] == LEARNING_ENGINE_VERSION
        assert payload["summary"]

    def test_historical_replay(self) -> None:
        full = _winner_history()
        sub = PipelineHistory(projects=full.projects[:6])
        full_report = LearningEngine().learn(full)
        sub_report = LearningEngine().learn(sub)
        full_ids = {p.pattern_id for p in full_report.patterns}
        sub_ids = {p.pattern_id for p in sub_report.patterns}
        assert sub_ids <= full_ids


# --------------------------------------------------------------- synthesis --


class TestEngine:
    def test_summary_text(self) -> None:
        report = LearningEngine().learn(_winner_history())
        assert "runs" in report.summary
        assert "scenes" in report.summary

    def test_failed_runs_counted(self) -> None:
        projects = list(_winner_history().projects[:3])
        projects[0] = _project(
            "w0", 0, list(projects[0].scenes), topic="gyroid",
            status="failed",
        )
        report = LearningEngine().learn(PipelineHistory(projects=tuple(projects)))
        assert report.failed_runs == 1

    def test_proposal_generator_direct_call(self) -> None:
        history = _winner_history()
        report = LearningEngine().learn(history)
        proposals = generate_proposals(
            history,
            report.patterns,
            report.failure_profiles,
            report.success_profiles,
            report.overall,
        )
        assert proposals


# ------------------------------------------------------------ performance --


class TestPerformance:
    def test_thousand_scenes_learn_quickly(self) -> None:
        projects: list[ProjectRecord] = []
        models = ["gpt-image", "flux-dev", "sdxl"]
        index = 0
        for run in range(200):
            scenes = [
                _scene(
                    f"perf-{run}", f"S{i}",
                    topic=f"topic-{i % 3}",
                    shot_type=ShotType.HERO if i % 2 else ShotType.MACRO,
                    image_model=models[i % 3],
                    qa=85.0 + (i % 5),
                )
                for i in range(1, 6)
            ]
            projects.append(_project(f"perf-{run}", index, scenes, topic="perf"))
            index += 1
        history = PipelineHistory(projects=tuple(projects))
        start = time.perf_counter()
        report = LearningEngine().learn(history)
        elapsed = time.perf_counter() - start
        assert report.scene_count == 1000
        assert elapsed < 5.0, f"learning took {elapsed:.2f}s"


# -------------------------------------------------------------- collector --


class TestWorkedExamples:
    def test_collector_produces_valid_history(self) -> None:
        history = collect_history(seeds=(7,))
        assert len(history.projects) == len(SOURCE_ROWS)
        scenes = [s for p in history.projects for s in p.scenes]
        assert len(scenes) >= 15
        assert all(4 <= len(p.scenes) <= 8 for p in history.projects)
        assert all(0.0 <= s.qa_score <= 100.0 for s in scenes)
        assert all(s.attempts >= 1 for s in scenes)
        assert all(s.predicted_qa > 0.0 for s in scenes)
        assert all(s.image_model for s in scenes)

    def test_collector_uses_directive_models(self) -> None:
        project = collect_film(
            key="gyroid", seed=11, run_index=0, preferred_model="gpt-image"
        )
        models = {scene.image_model for scene in project.scenes}
        assert "gpt-image" in models

    def test_worked_examples_export_reports(self, tmp_path: Path) -> None:
        import knowledge.learning_engine.examples.run_worked_examples as runner

        original = runner.OUTPUT_DIR
        runner.OUTPUT_DIR = tmp_path
        try:
            history, report = runner.run_worked_examples(seeds=(1,))
        finally:
            runner.OUTPUT_DIR = original
        assert report.project_count == len(SOURCE_ROWS)
        written = sorted(path.name for path in tmp_path.iterdir())
        assert written == [
            "knowledge_proposals.json",
            "learning_report.json",
            "performance_dashboard.json",
            "trend_report.json",
        ]
        del history

    def test_deterministic_recollection(self) -> None:
        first = collect_history(seeds=(13,))
        second = collect_history(seeds=(13,))
        assert first.model_dump() == second.model_dump()

