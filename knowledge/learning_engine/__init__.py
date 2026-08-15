"""Learning Engine: the self-improving observer of completed runs (Phase 11).

The engine is the deterministic brain of PR1ME: it reads completed
pipeline histories (``PipelineHistory`` of ``ProjectRecord`` of
``SceneObservation``) and produces reviewable ``ImprovementProposal`` s
with ``KnowledgeDiff`` s, success/failure profiles, winner-vs-rest
patterns, eight leaderboards, and four JSON exports. It never modifies
the knowledge base; every improvement is a proposal awaiting review.

No LLM, no randomness, no timestamps: the same history always produces
the same report.
"""

from __future__ import annotations

from knowledge.learning_engine.curriculum_statistics import (
    educational_stats,
    retention_leaderboard,
    topic_leaderboard,
)
from knowledge.learning_engine.failure_analyzer import (
    failed_runs,
    failure_profiles,
)
from knowledge.learning_engine.improvement_generator import generate_proposals
from knowledge.learning_engine.knowledge_diff import build_diff, build_diffs
from knowledge.learning_engine.learning_engine import LearningEngine
from knowledge.learning_engine.learning_models import (
    LEARNING_ENGINE_VERSION,
    CompilerRecommendation,
    DirectorRecommendation,
    FailureProfile,
    ImprovementProposal,
    KnowledgeDiff,
    KnowledgeProposal,
    LeaderboardRow,
    LearningReport,
    ModelRecommendation,
    OptimizationRecommendation,
    PatternObservation,
    PipelineHistory,
    ProjectRecord,
    Proposal,
    ProposalKind,
    QualitySummary,
    SceneObservation,
    SuccessProfile,
    WorkflowRecommendation,
)
from knowledge.learning_engine.learning_rules import IMMUTABILITY_STATEMENT
from knowledge.learning_engine.pattern_detector import detect_patterns
from knowledge.learning_engine.prompt_statistics import (
    mutation_summary,
    prompt_leaderboard,
)
from knowledge.learning_engine.quality_statistics import (
    all_qa_leaderboards,
    group_rows,
    overall_stats,
    qa_leaderboard,
)
from knowledge.learning_engine.render_statistics import (
    mutation_stats,
    render_leaderboard,
    retry_stats,
    switch_stats,
)
from knowledge.learning_engine.report_generator import export_reports
from knowledge.learning_engine.success_analyzer import success_profiles

__all__ = [
    "LEARNING_ENGINE_VERSION",
    "IMMUTABILITY_STATEMENT",
    "LearningEngine",
    "PipelineHistory",
    "ProjectRecord",
    "SceneObservation",
    "ProposalKind",
    "Proposal",
    "ImprovementProposal",
    "KnowledgeProposal",
    "ModelRecommendation",
    "DirectorRecommendation",
    "CompilerRecommendation",
    "WorkflowRecommendation",
    "OptimizationRecommendation",
    "PatternObservation",
    "KnowledgeDiff",
    "SuccessProfile",
    "FailureProfile",
    "LeaderboardRow",
    "QualitySummary",
    "LearningReport",
    "detect_patterns",
    "generate_proposals",
    "build_diff",
    "build_diffs",
    "group_rows",
    "qa_leaderboard",
    "all_qa_leaderboards",
    "overall_stats",
    "render_leaderboard",
    "retry_stats",
    "switch_stats",
    "mutation_stats",
    "prompt_leaderboard",
    "mutation_summary",
    "topic_leaderboard",
    "retention_leaderboard",
    "educational_stats",
    "success_profiles",
    "failure_profiles",
    "failed_runs",
    "export_reports",
    "learn",
    "export",
]


def learn(history: PipelineHistory) -> LearningReport:
    """One deterministic learning pass over a completed run history."""
    return LearningEngine().learn(history)


def export(
    report: LearningReport,
    history: PipelineHistory,
    output_dir: str,
) -> dict[str, str]:
    """Write the four JSON reports (learning, proposals, dashboard, trends)."""
    return {
        name: str(path)
        for name, path in LearningEngine().export(report, history, output_dir).items()
    }
