"""Pipeline orchestration.

The runner wires registered stages together, executes them in dependency order,
handles fail-fast aborts, writes JSON artifacts, and returns a typed run report.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pr1me.core.base_stage import BaseStage
from pr1me.core.context import StageContext
from pr1me.core.errors import ArtifactIOError, JobAbortedError, PipelineError, StageNotFoundError
from pr1me.core.logging import get_logger
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.meta import RunStatus, StageStatus

__all__ = ["PipelineRunner", "RunReport", "StageRunRecord"]


class StageRunRecord(BaseModel):
    """One stage's execution record inside a run report."""

    stage_id: str
    status: StageStatus = StageStatus.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: float = 0.0
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class RunReport(BaseModel):
    """Per-job orchestration report following the shared run-report schema."""

    job_id: str
    run_id: str
    run_status: RunStatus = RunStatus.COMPLETE
    stages: list[StageRunRecord] = Field(default_factory=list)
    final_artifact: str | None = None
    summary: str = ""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


class PipelineRunner:
    """Runs a :class:`StageRegistry`'s stages in dependency order.

    Stages exchange JSON-only payloads. The runner resolves each stage's input
    from the outputs of its declared dependencies (flattened into a single
    dict, overlaid with any matching seed values) and writes every output to
    ``artifact_dir`` as ``f"{job_id}_{stage_id}.json"``.

    The run is fail-fast: the first failure aborts the run and raises
    :class:`JobAbortedError`. ``last_report`` keeps the full report for
    inspection after an abort.
    """

    def __init__(
        self,
        registry: StageRegistry,
        *,
        context: StageContext,
        artifact_dir: Path | None = None,
    ) -> None:
        self._registry = registry
        self._context = context
        self._artifacts = artifact_dir or Path(context.settings.run_dir)
        self._logger = get_logger(
            "pr1me.pipeline.runner",
            run_id=context.run_id,
            job_id=context.job_id,
        )
        self.last_report: RunReport | None = None

    # ------------------------------------------------------------- entry ----

    async def run(
        self,
        job_input: dict[str, Any] | BaseModel,
        *,
        job_id: str,
        run_id: str | None = None,
    ) -> RunReport:
        """Execute the pipeline top to bottom and return a :class:`RunReport`.

        Raises :class:`JobAbortedError` on the first stage failure; the report
        is still available via ``last_report``.
        """
        seed = self._to_dict(job_input)
        order = self._registry.execution_order()
        completed: dict[str, dict[str, Any]] = {}
        records: list[StageRunRecord] = []
        run_status = RunStatus.COMPLETE
        final_artifact: str | None = None
        failure: PipelineError | None = None

        self._logger.info("pipeline.started", n_stages=len(order), job_id=job_id, run_id=run_id or job_id)

        for stage_id in order:
            stage = self._registry.resolve(stage_id)
            record = StageRunRecord(
                stage_id=stage_id,
                status=StageStatus.IN_PROGRESS,
                started_at=_now(),
                input=self._seed_input(stage, seed, completed),
            )
            self._logger.info("stage.started", stage=stage_id)
            started = datetime.now(tz=UTC)
            try:
                output = await stage.run(record.input)
            except PipelineError as exc:
                record.status = StageStatus.FAILED
                record.completed_at = _now()
                record.error = exc.message
                records.append(record)
                run_status = RunStatus.FAILED
                self._logger.error("pipeline.aborted", stage=stage_id, reason=exc.message)
                failure = exc
                break

            record.status = StageStatus.OK
            record.completed_at = _now()
            record.duration_ms = (datetime.now(tz=UTC) - started).total_seconds() * 1000.0
            record.output = self._to_dict(output)
            final_artifact = self._write_artifact(job_id, stage_id, record.output)
            completed[stage_id] = record.output
            records.append(record)
            self._logger.info("pipeline.stage_completed", stage=stage_id)

        self.last_report = RunReport(
            job_id=job_id,
            run_id=run_id or f"run-{job_id}",
            run_status=run_status,
            stages=records,
            final_artifact=final_artifact,
            summary=self._summarize(run_status, records),
        )
        if failure is not None:
            raise JobAbortedError(failure.message, detail=self.last_report.model_dump(mode="json"))
        return self.last_report

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _to_dict(value: dict[str, Any] | BaseModel) -> dict[str, Any]:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        return dict(value)

    def _seed_input(
        self,
        stage: BaseStage[Any, Any],
        seed: dict[str, Any],
        completed: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        deps = list(stage.depends_on)
        if not deps:
            return seed
        merged: dict[str, Any] = {}
        for dep in deps:
            if dep not in completed:
                raise StageNotFoundError(f"dependency {dep!r} of {stage.stage_id!r} has no output")
            merged.update(completed[dep])
        merged.update(seed)
        return merged

    def _write_artifact(self, job_id: str, stage_id: str, output: dict[str, Any]) -> str:
        path = self._artifacts / f"{job_id}_{stage_id}.json"
        try:
            path.write_text(json.dumps(output, default=str), encoding="utf-8")
        except OSError as exc:
            raise ArtifactIOError(f"cannot write artifact {path}: {exc}") from exc
        return str(path)

    @staticmethod
    def _summarize(status: RunStatus, records: list[StageRunRecord]) -> str:
        if status == RunStatus.FAILED and records:
            return "aborted after stage " + records[-1].stage_id
        return f"completed {len(records)} stage(s)"