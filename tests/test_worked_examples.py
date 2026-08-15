"""Worked examples tests: the four canonical closed-loop scenarios.

Proves the runtime deliverable "worked examples" end to end: three real
Knowledge Base rows through the full deterministic chain (gyroid passes on
the first render, planetary gear and injection molding repair in two
attempts) plus a retry-budget exhaustion case that burns all three attempts
without a winner - every attempt saved with its artifacts and a replayable
history.
"""

from __future__ import annotations

from pathlib import Path

from runtime import AttemptStatus, RenderSessionResult, topic_slug
from runtime.examples.run_worked_examples import WORKED_EXAMPLES, generate

_ARTIFACTS = (
    "prompt.txt",
    "prompt_negative.txt",
    "workflow.json",
    "qa_report.json",
    "image.png",
    "attempt.json",
)


def test_worked_examples_scenarios_arc() -> None:
    assert [e.name for e in WORKED_EXAMPLES] == [
        "gyroid",
        "planetary_gear",
        "injection_molding",
        "budget_exhaustion",
    ]


def test_worked_examples_generate_all_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "examples"
    results = generate(out)
    assert list(results) == [e.name for e in WORKED_EXAMPLES]

    gyroid = results["gyroid"]
    assert gyroid.passed
    assert [a.status for a in gyroid.attempts] == [AttemptStatus.PASSED]

    for name in ("planetary_gear", "injection_molding"):
        result = results[name]
        assert result.passed
        assert [a.status for a in result.attempts] == [
            AttemptStatus.FAILED,
            AttemptStatus.PASSED,
        ]
        assert result.attempts[0].optimization_report is not None
        assert result.attempts[0].qa_report is not None
        assert (
            result.attempts[0].qa_report.overall_score
            < result.attempts[1].qa_report.overall_score
        )

    exhausted = results["budget_exhaustion"]
    assert not exhausted.passed
    assert exhausted.winner is None
    assert [a.status for a in exhausted.attempts] == [
        AttemptStatus.FAILED,
        AttemptStatus.FAILED,
        AttemptStatus.FAILED,
    ]


def test_worked_examples_save_every_attempt(tmp_path: Path) -> None:
    out = tmp_path / "examples"
    results = generate(out)
    for name, result in results.items():
        scene_root = out / name / topic_slug(result.topic) / result.scene_id
        for attempt in result.attempts:
            directory = scene_root / attempt.attempt_id
            assert directory.is_dir(), attempt.attempt_id
            for artifact in _ARTIFACTS:
                assert (directory / artifact).is_file(), artifact
            if attempt.status is AttemptStatus.FAILED:
                assert (directory / "optimization_report.json").is_file()
        assert (scene_root / "history.json").is_file()


def test_worked_examples_are_replayable(tmp_path: Path) -> None:
    out = tmp_path / "examples"
    results = generate(out)
    for name, result in results.items():
        history_path = out / name / topic_slug(result.topic) / result.scene_id / "history.json"
        assert result.history.to_file(history_path) == history_path


def test_worked_examples_deterministic(tmp_path: Path) -> None:
    out = tmp_path / "examples"
    first = generate(out)
    second = generate(out)
    for name in first:
        assert first[name].model_dump(mode="json") == second[name].model_dump(
            mode="json"
        )


def test_worked_examples_session_type_is_runtime_result(tmp_path: Path) -> None:
    results = generate(tmp_path / "examples")
    assert all(isinstance(r, RenderSessionResult) for r in results.values())
