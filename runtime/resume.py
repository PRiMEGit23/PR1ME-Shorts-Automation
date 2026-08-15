"""Resume planning: decide what a resumed run must (re)do.

ResumePlanner compares every planned stage's content fingerprint against the
checkpoints left by previous runs. A stage is skipped when a checkpoint
exists with the exact same fingerprint, all of its artifacts are still
present and checksum-valid, and the stage ran to completion. Anything else -
no checkpoint, a fingerprint drift, a failed stage, or a missing artifact -
forces that stage to run again, and every stage after it re-evaluates on its
own new fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime.artifact_store import ArtifactStore
from runtime.checkpoint import CheckpointStore, StageCheckpoint


@dataclass(frozen=True)
class StagePlan:
    """One planned stage execution in the production pipeline."""

    stage_id: str
    fingerprint: str
    version: str
    dependencies: tuple[str, ...] = ()
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StageDecision:
    """What the planner decided for one stage."""

    stage_id: str
    skip: bool
    reason: str


class ResumePlanner:
    """Content-addressed resume decisions against the checkpoint store."""

    def __init__(
        self,
        *,
        checkpoints: CheckpointStore,
        store: ArtifactStore,
    ) -> None:
        self._checkpoints = checkpoints
        self._store = store

    def plan(
        self,
        planned: list[StagePlan],
        *,
        resume: bool,
    ) -> dict[str, StageDecision]:
        """Decide for every planned stage whether it can be skipped.

        Without ``resume`` every stage is planned for execution. With resume,
        a stage is skipped only when its checkpoint matches exactly and all
        of its artifacts remain intact.
        """
        decisions: dict[str, StageDecision] = {}
        for stage in planned:
            checkpoint = self._checkpoints.load(stage.stage_id) if resume else None
            if checkpoint is None:
                decisions[stage.stage_id] = StageDecision(
                    stage_id=stage.stage_id,
                    skip=False,
                    reason="no checkpoint",
                )
                continue
            reason = self._match_reason(stage, checkpoint)
            if reason is None:
                decisions[stage.stage_id] = StageDecision(
                    stage_id=stage.stage_id,
                    skip=True,
                    reason="fingerprint match, artifacts intact",
                )
            else:
                decisions[stage.stage_id] = StageDecision(
                    stage_id=stage.stage_id,
                    skip=False,
                    reason=reason,
                )
        return decisions

    def _match_reason(self, stage: StagePlan, checkpoint: StageCheckpoint) -> str | None:
        if checkpoint.stage_id != stage.stage_id:
            return "checkpoint belongs to a different stage"
        if checkpoint.status != "completed":
            return "previous run failed or was interrupted"
        if checkpoint.fingerprint != stage.fingerprint:
            return "inputs changed since the checkpoint"
        for record in checkpoint.artifacts:
            if not self._store.has(record):
                return f"artifact missing or corrupted: {record.filename}"
        return None

    @staticmethod
    def restore_output(checkpoint: StageCheckpoint) -> Any:
        """The serialized output a skipped stage contributes to the run."""
        return checkpoint.output
