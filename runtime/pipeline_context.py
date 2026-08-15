"""Shared run state for the production pipeline.

PipelineContext is the single object every stage and the orchestrator touch:
the run identity, the run directory layout, the artifact store, the event
sink, the checkpoint store, and the accumulated per-stage outputs. It is a
plain mutable container - all behavior lives in the store/runner/pipeline
modules so the context stays trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from knowledge.visual_architecture import EngineeringDomain, Modality

from pr1me.core.config import Settings
from runtime.artifact_store import ArtifactRecord, ArtifactStore
from runtime.checkpoint import CheckpointStore
from runtime.events import EventSink

PIPELINE_VERSION = "7.0.0"


class MemoryProbe(Protocol):
    """Optional process memory sampling (MB). Deterministic no-op default."""

    def sample_mb(self) -> float: ...


class GPUProbe(Protocol):
    """Optional GPU utilization sampling (MB). Deterministic no-op default."""

    def sample_mb(self) -> float: ...


class NoopMemoryProbe:
    """Deterministic default: reports 0 MB without probing the system."""

    def sample_mb(self) -> float:
        return 0.0


class NoopGPUProbe:
    """Deterministic default: reports 0 MB without probing the system."""

    def sample_mb(self) -> float:
        return 0.0


@dataclass
class PipelineContext:
    """The complete state of one production pipeline run."""

    run_id: str
    job_id: str
    topic: str
    settings: Settings
    run_dir: Path
    store: ArtifactStore
    events: EventSink
    checkpoints: CheckpointStore
    memory_probe: MemoryProbe = field(default_factory=NoopMemoryProbe)
    gpu_probe: GPUProbe = field(default_factory=NoopGPUProbe)
    #: Knowledge Base row driving the run (canonical dict).
    row: dict[str, str] = field(default_factory=dict)
    #: Deterministic seed used by every stochastic-free stage (render seeds).
    seed: int = 42
    #: Per-scene render retry budget (shared with SessionConfig.max_attempts).
    max_attempts: int = 3
    #: Rendering model key used by the prompt compiler (default sdxl).
    model_key: str = "sdxl"
    #: stage_id -> stage output (JSON-safe payload, canonical form).
    outputs: dict[str, Any] = field(default_factory=dict)
    #: stage_id -> artifact records produced by that stage (insertion order).
    artifacts: dict[str, list[ArtifactRecord]] = field(default_factory=dict)
    #: True when the stage output came from a checkpoint (cache hit).
    cache_hits: dict[str, bool] = field(default_factory=dict)
    #: stage_id -> duration in milliseconds (recorded by the runner).
    durations_ms: dict[str, float] = field(default_factory=dict)
    #: Rendering domain and visual modality (deterministic pipeline directives).
    engineering_domain: EngineeringDomain = EngineeringDomain.FDM
    modality: Modality = Modality.PHOTOREAL
    #: When True, the publisher uploads to YouTube; otherwise it dry-runs.
    publish: bool = False

    # ------------------------------------------------------------ layout --

    def stage_output(self, stage_id: str) -> Any:
        """The output of a completed stage (raises KeyError when absent)."""
        return self.outputs[stage_id]

    def stage_artifacts(self, stage_id: str) -> list[ArtifactRecord]:
        """Artifact records of a stage (empty when the stage never ran)."""
        return self.artifacts.get(stage_id, [])

    def record_stage(
        self,
        stage_id: str,
        output: Any,
        records: list[ArtifactRecord],
        *,
        duration_ms: float,
        cache_hit: bool,
    ) -> None:
        """Persist one stage's outcome into the context."""
        self.outputs[stage_id] = output
        self.artifacts[stage_id] = records
        self.cache_hits[stage_id] = cache_hit
        self.durations_ms[stage_id] = duration_ms

    # ------------------------------------------------------------ paths --

    @property
    def images_dir(self) -> Path:
        return self.run_dir / "images"

    @property
    def audio_dir(self) -> Path:
        return self.run_dir / "audio"

    @property
    def subtitles_dir(self) -> Path:
        return self.run_dir / "subtitles"

    @property
    def video_dir(self) -> Path:
        return self.run_dir / "video"

    @property
    def thumbnail_dir(self) -> Path:
        return self.run_dir / "thumbnail"

    @property
    def metadata_dir(self) -> Path:
        return self.run_dir / "metadata"

    @property
    def workflow_dir(self) -> Path:
        return self.run_dir / "workflow"

    @property
    def history_dir(self) -> Path:
        return self.run_dir / "history"

    @property
    def reports_dir(self) -> Path:
        return self.run_dir / "reports"

    def ensure_dirs(self) -> None:
        """Create the run directory layout deterministically."""
        for path in (
            self.run_dir,
            self.store.artifacts_dir,
            self.checkpoints.dir,
            self.images_dir,
            self.audio_dir,
            self.subtitles_dir,
            self.video_dir,
            self.thumbnail_dir,
            self.metadata_dir,
            self.workflow_dir,
            self.history_dir,
            self.reports_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
