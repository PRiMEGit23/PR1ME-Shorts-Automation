"""Run all Learning Engine worked examples.

Collects every worked-example film (gyroid, planetary gear, injection
molding) across several seeds via the production stack, learns from the
combined history, and exports the four deterministic JSON reports.

``python -m knowledge.learning_engine.examples.run_worked_examples``
"""

from __future__ import annotations

from pathlib import Path

from knowledge.learning_engine import LearningEngine, PipelineHistory, learn
from knowledge.learning_engine.examples._collector import collect_history
from knowledge.learning_engine.learning_models import LearningReport

#: Where the exported reports land (next to this example).
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def run_worked_examples(seeds: tuple[int, ...] = (42, 43, 44)) -> tuple[
    PipelineHistory, LearningReport
]:
    """Collect the worked examples and learn from them; returns (history, report)."""
    history = collect_history(seeds=seeds)
    report = learn(history)
    LearningEngine().export(report, history, OUTPUT_DIR)
    return history, report


def main() -> None:
    history, report = run_worked_examples()
    print(f"== Learning Engine worked examples: {len(history.projects)} runs ==")
    print(f"  {report.summary}")
    print("  patterns:")
    for pattern in report.patterns:
        print(
            f"    {pattern.pattern_id}: {pattern.winner} "
            f"(delta {pattern.delta:+.2f} {pattern.metric}, "
            f"confidence {pattern.confidence:.2f})"
        )
    print("  proposals:")
    for proposal in report.proposals:
        print(
            f"    [{proposal.kind.value:12s}] {proposal.title} "
            f"(confidence {proposal.confidence:.2f})"
        )
    print("  leaderboards:")
    for name, rows in sorted(report.leaderboards.items()):
        top = rows[0] if rows else None
        print(f"    {name:26s} top: {top.key if top else '-'} mean={top.mean if top else '-'}")
    print(f"  exports -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
