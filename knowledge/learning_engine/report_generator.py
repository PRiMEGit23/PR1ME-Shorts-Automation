"""Report generator: the four deterministic export payloads (Phase 11).

``LearningEngine.export`` writes exactly four JSON files:

- ``learning_report.json`` - the full report (summary, patterns,
  proposals, diffs)
- ``knowledge_proposals.json`` - every proposal with its diff
- ``performance_dashboard.json`` - the eight leaderboards + overall
- ``trend_report.json`` - per-run trends (QA, pass rate, attempts,
  duration) in caller-supplied run order, plus the window comparison

All payloads are JSON-serializable plain dicts; the writer always dumps
with ``sort_keys=True`` so identical runs produce byte-identical files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge.learning_engine.learning_models import (
    LEARNING_ENGINE_VERSION,
    LearningReport,
    PipelineHistory,
)
from knowledge.learning_engine.learning_rules import TREND_WINDOW


def build_learning_report_payload(report: LearningReport) -> dict[str, Any]:
    """The full learning report as a plain dict."""
    return {
        "version": report.version,
        "project_count": report.project_count,
        "scene_count": report.scene_count,
        "failed_runs": report.failed_runs,
        "overall": report.overall.model_dump(mode="json"),
        "success_profiles": [
            profile.model_dump(mode="json") for profile in report.success_profiles
        ],
        "failure_profiles": [
            profile.model_dump(mode="json") for profile in report.failure_profiles
        ],
        "patterns": [pattern.model_dump(mode="json") for pattern in report.patterns],
        "proposals": [proposal.model_dump(mode="json") for proposal in report.proposals],
        "knowledge_diffs": [
            diff.model_dump(mode="json") for diff in report.knowledge_diffs
        ],
        "leaderboards": {
            name: [row.model_dump(mode="json") for row in rows]
            for name, rows in report.leaderboards.items()
        },
        "summary": report.summary,
    }


def build_knowledge_proposals_payload(report: LearningReport) -> dict[str, Any]:
    """Every proposal with its diff, for human review."""
    return {
        "version": LEARNING_ENGINE_VERSION,
        "proposals": [
            {
                **proposal.model_dump(mode="json"),
                "diff": (
                    proposal.diff.model_dump(mode="json")
                    if proposal.diff is not None
                    else None
                ),
            }
            for proposal in report.proposals
        ],
    }


def build_performance_dashboard_payload(report: LearningReport) -> dict[str, Any]:
    """The eight leaderboards plus the overall health summary."""
    return {
        "version": LEARNING_ENGINE_VERSION,
        "overall": report.overall.model_dump(mode="json"),
        "leaderboards": {
            name: [row.model_dump(mode="json") for row in rows]
            for name, rows in report.leaderboards.items()
        },
    }


def build_trend_report_payload(history: PipelineHistory) -> dict[str, Any]:
    """Per-run trends in run order, plus the first-vs-last window delta."""
    trends: list[dict[str, Any]] = []
    for project in history.projects:
        scenes = list(project.scenes)
        count = len(scenes)
        qa = [scene.qa_score for scene in scenes]
        passed = sum(1 for scene in scenes if scene.passed)
        trends.append(
            {
                "run_index": project.run_index,
                "run_id": project.run_id,
                "topic": project.topic,
                "status": project.status,
                "scene_count": count,
                "mean_qa": round(sum(qa) / count, 1),
                "pass_rate": round(passed / count, 3),
                "mean_attempts": round(
                    sum(scene.attempts for scene in scenes) / count, 2
                ),
                "mean_duration_ms": round(
                    sum(scene.render_duration_ms for scene in scenes) / count, 1
                ),
            }
        )

    def _window_mean(attribute: str, window: list[dict[str, Any]]) -> float | None:
        if not window:
            return None
        return round(sum(row[attribute] for row in window) / len(window), 1)

    first = trends[:TREND_WINDOW]
    last = trends[-TREND_WINDOW:] if len(trends) > TREND_WINDOW else trends
    qa_first = _window_mean("mean_qa", first)
    qa_last = _window_mean("mean_qa", last)
    window_summary: dict[str, Any] = {
        "window": TREND_WINDOW,
        "qa_first_window": qa_first,
        "qa_last_window": qa_last,
        "qa_trend": (
            round(qa_last - qa_first, 1)
            if qa_first is not None and qa_last is not None
            else None
        ),
    }
    return {
        "version": LEARNING_ENGINE_VERSION,
        "trends": trends,
        "window_summary": window_summary,
    }


def export_reports(
    report: LearningReport, history: PipelineHistory, output_dir: Path
) -> dict[str, Path]:
    """Write the four deterministic JSON exports; returns name -> path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "learning_report.json": build_learning_report_payload(report),
        "knowledge_proposals.json": build_knowledge_proposals_payload(report),
        "performance_dashboard.json": build_performance_dashboard_payload(report),
        "trend_report.json": build_trend_report_payload(history),
    }
    written: dict[str, Path] = {}
    for name, payload in payloads.items():
        target = output_dir / name
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        written[name] = target
    return written
