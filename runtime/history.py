"""RenderHistory: full tracking of one closed-loop session.

The history records every attempt, and from those attempts derives the four
trajectories the mission requires: prompt evolution, workflow evolution,
QA score series, and optimization actions - plus the final winner. The
history is the deterministic replay source: a saved history JSON fully
describes the session and reconstructs without re-rendering.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from runtime.models import AttemptStatus, RenderAttempt, RenderSessionResult


class PromptEvolution(BaseModel):
    """One step of the prompt trajectory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: str
    index: int
    prompt: str
    negative_prompt: str


class WorkflowEvolution(BaseModel):
    """One step of the workflow trajectory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: str
    index: int
    profile: str
    workflow: dict


class QAScorePoint(BaseModel):
    """The eight QA scores for one attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: str
    index: int
    overall: float
    engineering: float
    educational: float
    composition: float
    subject_hierarchy: float
    visual_clarity: float
    thumbnail: float
    consistency: float
    verdict: str


class OptimizationActionPoint(BaseModel):
    """One optimization action prescribed after an attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: str
    index: int
    kind: str
    check: str
    instruction: str
    expected_gain: float
    target_score: str


class RenderHistory(BaseModel):
    """The complete, replayable record of one session."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=200)
    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    seed: int
    max_attempts: int = Field(ge=1, le=10)
    attempts: list[RenderAttempt] = Field(default_factory=list, max_length=12)

    @property
    def winner(self) -> RenderAttempt | None:
        for attempt in reversed(self.attempts):
            if attempt.status is AttemptStatus.PASSED:
                return attempt
        return None

    @property
    def passed(self) -> bool:
        return self.winner is not None

    @property
    def attempts_used(self) -> int:
        return sum(
            1 for a in self.attempts if a.status is not AttemptStatus.SKIPPED_DUPLICATE
        )

    def prompt_evolution(self) -> list[PromptEvolution]:
        return [
            PromptEvolution(
                attempt_id=a.attempt_id,
                index=a.index,
                prompt=a.prompt,
                negative_prompt=a.negative_prompt,
            )
            for a in self.attempts
        ]

    def workflow_evolution(self) -> list[WorkflowEvolution]:
        return [
            WorkflowEvolution(
                attempt_id=a.attempt_id,
                index=a.index,
                profile=a.workflow_profile.value,
                workflow=a.workflow,
            )
            for a in self.attempts
        ]

    def qa_scores(self) -> list[QAScorePoint]:
        points: list[QAScorePoint] = []
        for attempt in self.attempts:
            report = attempt.qa_report
            if report is None:
                continue
            points.append(
                QAScorePoint(
                    attempt_id=attempt.attempt_id,
                    index=attempt.index,
                    overall=report.overall_score,
                    engineering=report.engineering_score,
                    educational=report.educational_score,
                    composition=report.composition_score,
                    subject_hierarchy=report.subject_hierarchy_score,
                    visual_clarity=report.visual_clarity_score,
                    thumbnail=report.thumbnail_score,
                    consistency=report.consistency_score,
                    verdict=report.pass_fail.value,
                )
            )
        return points

    def optimization_actions(self) -> list[OptimizationActionPoint]:
        points: list[OptimizationActionPoint] = []
        for attempt in self.attempts:
            plan = attempt.optimization_report
            if plan is None:
                continue
            for action in plan.optimization_actions:
                points.append(
                    OptimizationActionPoint(
                        attempt_id=attempt.attempt_id,
                        index=attempt.index,
                        kind=action.kind.value,
                        check=action.check.value,
                        instruction=action.instruction,
                        expected_gain=action.expected_gain,
                        target_score=action.target_score,
                    )
                )
        return points

    def to_session_result(self) -> RenderSessionResult:
        return RenderSessionResult(
            topic=self.topic,
            scene_id=self.scene_id,
            seed=self.seed,
            max_attempts=self.max_attempts,
            passed=self.passed,
            winner=self.winner,
            attempts=self.attempts,
        )

    def to_file(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def from_file(cls, path: Path) -> RenderHistory:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    @classmethod
    def from_json(cls, payload: str | dict) -> RenderHistory:
        if isinstance(payload, dict):
            return cls.model_validate(payload)
        return cls.model_validate_json(payload)