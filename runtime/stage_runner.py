"""The stage runner: execute one pipeline stage with full instrumentation.

StageRunner wraps a stage's implementation with everything the production
pipeline needs around it, in one place:

- content fingerprint of the stage's exact inputs
- resume decisions (skip when the checkpoint matches and artifacts are intact)
- timing, memory and GPU sampling around the execution
- structured events for start / complete / fail / skip / checkpoint
- artifact persistence through the ArtifactStore
- checkpoint persistence after completion (and after failure)

The runner is deliberately stage-agnostic: a Stage declares its identity,
version, dependencies, its input view, and its execute function, and the
runner provides the lifecycle.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from runtime.artifact_store import ArtifactRecord, ArtifactStore
from runtime.checkpoint import CheckpointStore, StageCheckpoint
from runtime.events import EventSink, PipelineEventType
from runtime.fingerprint import stage_fingerprint
from runtime.pipeline_context import NoopGPUProbe, PipelineContext
from runtime.resume import ResumePlanner, StageDecision, StagePlan

STAGE_RUNNER_VERSION = "1.0.0"


class StageError(RuntimeError):
    """A stage execution failed; carries the failing stage id."""

    def __init__(self, stage_id: str, message: str, *, detail: Any | None = None) -> None:
        super().__init__(message)
        self.stage_id = stage_id
        self.message = message
        self.detail = detail


class Stage(ABC):
    """Base contract for every production pipeline stage.

    A stage declares its identity, version, and dependencies, exposes the
    exact inputs its output depends on (the fingerprint view), and executes.
    Concrete stages may contribute extra metrics through :meth:`metrics`.
    """

    stage_id: str
    name: str
    version: str
    description: str
    dependencies: tuple[str, ...]

    @abstractmethod
    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        """The exact inputs this stage's output depends on (fingerprint view)."""

    @abstractmethod
    async def execute(self, ctx: PipelineContext) -> Any:
        """Run the stage and return its JSON-safe output."""

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        """Extra metrics this stage contributes to the execution report."""
        return {}


@dataclass(frozen=True)
class StageRunResult:
    """Everything the runner learned about one stage execution."""

    stage_id: str
    fingerprint: str
    status: str
    duration_ms: float
    cache_hit: bool
    output: Any
    artifacts: list[ArtifactRecord]
    memory_peak_mb: float
    gpu_time_ms: float
    metrics: dict[str, Any] = field(default_factory=dict)


class StageRunner:
    """Executes stages with fingerprinting, resume, events, and checkpoints."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        checkpoints: CheckpointStore,
        events: EventSink,
        planner: ResumePlanner | None = None,
    ) -> None:
        self._store = store
        self._checkpoints = checkpoints
        self._events = events
        self._planner = planner if planner is not None else ResumePlanner(
            checkpoints=checkpoints, store=store
        )

    async def run(
        self,
        stage: Stage,
        ctx: PipelineContext,
        *,
        resume: bool,
    ) -> StageRunResult:
        """Execute one stage (or restore it from a matching checkpoint)."""
        fingerprint = stage_fingerprint(stage.stage_id, stage.version, stage.inputs(ctx))
        decision = self._plan(stage, fingerprint, ctx, resume=resume)
        if decision.skip:
            checkpoint = self._checkpoints.load(stage.stage_id)
            assert checkpoint is not None  # the planner only skips on a match
            self._events.record(
                PipelineEventType.STAGE_SKIPPED,
                stage_id=stage.stage_id,
                payload={"reason": decision.reason, "fingerprint": fingerprint},
            )
            self._events.record(
                PipelineEventType.CACHE_HIT,
                stage_id=stage.stage_id,
                payload={"fingerprint": fingerprint},
            )
            return StageRunResult(
                stage_id=stage.stage_id,
                fingerprint=fingerprint,
                status="skipped",
                duration_ms=0.0,
                cache_hit=True,
                output=ResumePlanner.restore_output(checkpoint),
                artifacts=checkpoint.artifacts,
                memory_peak_mb=0.0,
                gpu_time_ms=0.0,
                metrics={},
            )

        self._events.record(
            PipelineEventType.STAGE_STARTED,
            stage_id=stage.stage_id,
            payload={"fingerprint": fingerprint},
        )
        memory_before = ctx.memory_probe.sample_mb()
        started = time.monotonic()
        try:
            output = await stage.execute(ctx)
        except Exception as exc:
            self._record_failure(stage.stage_id, fingerprint, exc)
            raise
        duration_ms = round((time.monotonic() - started) * 1000.0, 3)
        memory_after = ctx.memory_probe.sample_mb()
        gpu_time_ms = self._gpu_time_ms(ctx, stage.stage_id, duration_ms)

        records = self._save_outputs(stage.stage_id, output)
        self._save_checkpoint(stage.stage_id, fingerprint, "completed", records, output)
        stage_metrics = stage.metrics(ctx)
        self._events.record(
            PipelineEventType.STAGE_COMPLETED,
            stage_id=stage.stage_id,
            payload={
                "duration_ms": duration_ms,
                "artifacts": len(records),
                "memory_peak_mb": memory_after,
            },
        )
        return StageRunResult(
            stage_id=stage.stage_id,
            fingerprint=fingerprint,
            status="completed",
            duration_ms=duration_ms,
            cache_hit=False,
            output=output,
            artifacts=records,
            memory_peak_mb=max(memory_before, memory_after),
            gpu_time_ms=gpu_time_ms,
            metrics=stage_metrics,
        )

    # ------------------------------------------------------------ internals --

    def _plan(
        self,
        stage: Stage,
        fingerprint: str,
        ctx: PipelineContext,
        *,
        resume: bool,
    ) -> StageDecision:
        planned = StagePlan(
            stage_id=stage.stage_id,
            fingerprint=fingerprint,
            version=stage.version,
            dependencies=stage.dependencies,
            inputs=stage.inputs(ctx),
        )
        decisions = self._planner.plan([planned], resume=resume)
        return decisions[stage.stage_id]

    def _save_outputs(self, stage_id: str, output: Any) -> list[ArtifactRecord]:
        """Persist the stage output as a JSON artifact (single source)."""
        return [self._store.save_json(stage_id, "output", output)]

    def _save_checkpoint(
        self,
        stage_id: str,
        fingerprint: str,
        status: str,
        records: list[ArtifactRecord],
        output: Any,
    ) -> None:
        checkpoint = StageCheckpoint(
            stage_id=stage_id,
            fingerprint=fingerprint,
            status=status,
            artifacts=records,
            output=output,
        )
        self._checkpoints.save(checkpoint)
        self._events.record(
            PipelineEventType.CHECKPOINT_SAVED,
            stage_id=stage_id,
            payload={"fingerprint": fingerprint, "status": status},
        )

    def _record_failure(self, stage_id: str, fingerprint: str, exc: Exception) -> None:
        message = str(exc) or type(exc).__name__
        try:
            self._save_checkpoint(
                stage_id, fingerprint, "failed", [], None,
            )
        except OSError:  # pragma: no cover - checkpoint must never mask the error
            pass
        self._events.record(
            PipelineEventType.STAGE_FAILED,
            stage_id=stage_id,
            payload={"fingerprint": fingerprint, "error": message},
        )

    @staticmethod
    def _gpu_time_ms(ctx: PipelineContext, stage_id: str, duration_ms: float) -> float:
        """GPU-accounted time: wall time of render-bound stages when a GPU probe is active.

        Deterministic default: the no-op GPU probe reports 0 MB, so the
        reported GPU time is 0.0 and runs stay reproducible without hardware.
        """
        if isinstance(ctx.gpu_probe, NoopGPUProbe):
            return 0.0
        if stage_id in ("render_loop", "video_render"):
            return duration_ms
        return 0.0
