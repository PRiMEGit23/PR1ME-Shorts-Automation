"""The Learning Engine: deterministic learning over completed runs (Phase 11).

``LearningEngine.learn`` is a pure function of one ``PipelineHistory``:
it computes the overall statistics, the eight leaderboards, the success
and failure profiles, the winner-vs-rest patterns, the reviewable
improvement proposals with their knowledge diffs, and assembles the
``LearningReport``. ``LearningEngine.export`` writes the four JSON
reports (``learning_report.json``, ``knowledge_proposals.json``,
``performance_dashboard.json``, ``trend_report.json``).

The engine never modifies the knowledge base. No LLM, no randomness, no
timestamps: the same history always produces the same report.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.learning_engine.curriculum_statistics import topic_leaderboard
from knowledge.learning_engine.failure_analyzer import (
    failed_runs,
    failure_profiles,
)
from knowledge.learning_engine.improvement_generator import generate_proposals
from knowledge.learning_engine.knowledge_diff import build_diffs
from knowledge.learning_engine.learning_models import (
    LEARNING_ENGINE_VERSION,
    LearningReport,
    PatternObservation,
    PipelineHistory,
    Proposal,
    QualitySummary,
)
from knowledge.learning_engine.learning_rules import LEADERBOARD_DIMENSIONS
from knowledge.learning_engine.pattern_detector import detect_patterns
from knowledge.learning_engine.quality_statistics import (
    all_qa_leaderboards,
    overall_stats,
)
from knowledge.learning_engine.render_statistics import render_leaderboard
from knowledge.learning_engine.report_generator import export_reports
from knowledge.learning_engine.success_analyzer import success_profiles


class LearningEngine:
    """Stateless, deterministic observer of completed pipeline histories."""

    def learn(self, history: PipelineHistory) -> LearningReport:
        """One learning pass over a history; a pure function of the input."""
        qa_boards = all_qa_leaderboards(history)
        boards = {
            name: _rows_for(history, name, qa_boards)
            for name, _ in LEADERBOARD_DIMENSIONS
        }
        overall = overall_stats(history)
        successes = success_profiles(history)
        failures = failure_profiles(history)
        patterns = detect_patterns(history)
        proposals = generate_proposals(history, patterns, failures, successes, overall)
        diffs = build_diffs(proposals)
        return LearningReport(
            version=LEARNING_ENGINE_VERSION,
            project_count=len(history.projects),
            scene_count=overall.scene_count,
            failed_runs=len(failed_runs(history)),
            overall=overall,
            success_profiles=successes,
            failure_profiles=failures,
            patterns=patterns,
            proposals=proposals,
            knowledge_diffs=diffs,
            leaderboards=boards,
            summary=self._summary(history, overall, patterns, proposals),
        )

    def export(
        self,
        report: LearningReport,
        history: PipelineHistory,
        output_dir: Path | str,
    ) -> dict[str, Path]:
        """Write the four deterministic JSON reports; returns name -> path."""
        return export_reports(report, history, Path(output_dir))

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _summary(
        history: PipelineHistory,
        overall: QualitySummary,
        patterns: tuple[PatternObservation, ...],
        proposals: tuple[Proposal, ...],
    ) -> str:
        wins = [pattern.winner for pattern in patterns[:2]]
        leader = (
            f"{overall.pass_rate:.0%} pass rate"
            if patterns
            else "no patterns yet (need more runs)"
        )
        return (
            f"{len(history.projects)} runs, {overall.scene_count} scenes; "
            f"{leader}; mean QA {overall.mean_qa:.1f}; "
            f"{len(patterns)} patterns, {len(proposals)} proposals"
            + (f"; leading: {', '.join(wins)}" if wins else "")
        )


def _rows_for(
    history: PipelineHistory,
    name: str,
    qa_boards: dict[str, tuple],
) -> tuple:
    """One leaderboard by name (the eight definitions stay in the rules)."""
    if name == "render":
        return render_leaderboard(history)
    if name == "topic":
        return topic_leaderboard(history)
    if name in qa_boards:
        return qa_boards[name]
    return tuple()
