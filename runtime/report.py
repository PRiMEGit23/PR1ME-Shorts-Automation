"""Structured execution report for one production run.

The report is the machine-readable record of what a run did: per-stage
timing, cache hits, memory/GPU sampling, render attempts and QA scores from
the render loop, optimization history, token/model usage, and the final
deliverables. It is written to ``<run_dir>/reports/execution_report.json``
and summarized into the pipeline's top-level manifest.

All metrics are deterministic in shape; values that depend on clocks or
hardware (durations, memory peaks) are recorded but never influence stage
outputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from runtime.artifact_store import ArtifactRecord
from runtime.fingerprint import canonical_json

REPORT_VERSION = "1.0.0"


class StageReport(BaseModel):
    """The full instrumentation record of one stage execution."""

    model_config = {"extra": "forbid"}

    stage_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: str = Field(pattern=r"^(completed|skipped|failed)$")
    duration_ms: float = Field(ge=0.0)
    cache_hit: bool = False
    fingerprint: str = Field(min_length=64, max_length=64)
    memory_peak_mb: float = Field(ge=0.0)
    gpu_time_ms: float = Field(ge=0.0)
    #: Metrics contributed by the stage itself (render attempts, QA scores...).
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class ExecutionReport(BaseModel):
    """Everything a run reports about itself."""

    model_config = {"extra": "forbid"}

    version: str = REPORT_VERSION
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    status: str = Field(pattern=r"^(complete|failed)$")
    total_duration_ms: float = Field(ge=0.0)
    stages: list[StageReport] = Field(default_factory=list)
    #: Final deliverables: name -> absolute path (or list of paths).
    final_artifacts: dict[str, Any] = Field(default_factory=dict)

    # ------------------------------------------------------------ helpers --

    @property
    def stage_count(self) -> int:
        return len(self.stages)

    @property
    def cache_hit_count(self) -> int:
        return sum(1 for stage in self.stages if stage.cache_hit)

    def stage(self, stage_id: str) -> StageReport | None:
        """The report for one stage, if it ran."""
        for stage in self.stages:
            if stage.stage_id == stage_id:
                return stage
        return None

    def write(self, path: Path) -> None:
        """Persist the report as canonical JSON (atomic)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.model_dump(mode="json")
        tmp = path.with_suffix(f"{path.suffix}.tmp")
        tmp.write_text(canonical_json(payload), encoding="utf-8")
        tmp.replace(path)
