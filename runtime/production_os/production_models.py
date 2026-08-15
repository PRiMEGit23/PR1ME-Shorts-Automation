"""Production OS models: the schema layer of the PR1ME Operating System.

The Production OS runs an unlimited number of projects (single, daily, weekly or
monthly batches) through a deterministic factory pipeline.  Every entity in the
factory is a frozen, hashable dataclass so that state can be checkpointed,
resumed and exported byte-identically.  Time is *planned time* (an integer
tick); the factory never consults a wall clock, so the same inputs always
produce the same timeline, the same exports and the same checkpoints.

Versioning: every module in :mod:`runtime.production_os` is stamped with the
OS version string and checked by the compatibility tests.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Final

PRODUCTION_OS_VERSION: Final[str] = "13.0.0"

# One tick is one simulated second of factory time.
DAY_TICKS: Final[int] = 86_400
WEEK_TICKS: Final[int] = 7 * DAY_TICKS
MONTH_TICKS: Final[int] = 30 * DAY_TICKS

DEFAULT_PRIORITY: Final[int] = 50
DEFAULT_MAX_RETRIES: Final[int] = 3
AUTO_PAUSE_LIMIT: Final[float] = 0.95

_GPU_UNITS_TOLERANCE: Final[float] = 1e-6


class JobStatus(StrEnum):
    """Lifecycle status of a factory job.  The queue admits exactly these."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    RETRY = "retry"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class JobType(StrEnum):
    """The stages of one production project, in canonical order."""

    STORYBOARD = "storyboard"
    RENDER_IMAGE = "render_image"
    VOICE = "voice"
    RENDER_VIDEO = "render_video"
    METADATA = "metadata"
    ASSET_INDEX = "asset_index"
    PUBLISH = "publish"
    LEARNING = "learning"


class WorkerType(StrEnum):
    """The worker classes of the factory pool."""

    IMAGE_WORKER = "image_worker"
    VIDEO_WORKER = "video_worker"
    VOICE_WORKER = "voice_worker"
    METADATA_WORKER = "metadata_worker"
    PUBLISHING_WORKER = "publishing_worker"
    ASSET_WORKER = "asset_worker"
    LEARNING_WORKER = "learning_worker"


class BatchKind(StrEnum):
    """How a set of topics is scheduled: one shot, or a repeating batch."""

    SINGLE = "single"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# Canonical stage order for one project (index 0 runs first).
STAGE_ORDER: Final[tuple[JobType, ...]] = (
    JobType.STORYBOARD,
    JobType.RENDER_IMAGE,
    JobType.VOICE,
    JobType.RENDER_VIDEO,
    JobType.METADATA,
    JobType.ASSET_INDEX,
    JobType.PUBLISH,
    JobType.LEARNING,
)

STAGE_INDEX: Final[dict[JobType, int]] = {
    stage: index for index, stage in enumerate(STAGE_ORDER)
}

# Mission rules: render waits for storyboard, video waits for images,
# publisher waits for metadata, learning waits for completion, asset indexing
# waits for outputs.
STAGE_DEPENDENCIES: Final[dict[JobType, tuple[JobType, ...]]] = {
    JobType.STORYBOARD: (),
    JobType.RENDER_IMAGE: (JobType.STORYBOARD,),
    JobType.VOICE: (JobType.STORYBOARD,),
    JobType.RENDER_VIDEO: (JobType.RENDER_IMAGE, JobType.VOICE),
    JobType.METADATA: (JobType.RENDER_VIDEO,),
    JobType.ASSET_INDEX: (JobType.RENDER_IMAGE, JobType.RENDER_VIDEO),
    JobType.PUBLISH: (JobType.METADATA,),
    JobType.LEARNING: (JobType.PUBLISH, JobType.ASSET_INDEX),
}

# Which worker class executes each stage.
JOB_TYPE_WORKER: Final[dict[JobType, WorkerType]] = {
    JobType.STORYBOARD: WorkerType.METADATA_WORKER,
    JobType.RENDER_IMAGE: WorkerType.IMAGE_WORKER,
    JobType.VOICE: WorkerType.VOICE_WORKER,
    JobType.RENDER_VIDEO: WorkerType.VIDEO_WORKER,
    JobType.METADATA: WorkerType.METADATA_WORKER,
    JobType.ASSET_INDEX: WorkerType.ASSET_WORKER,
    JobType.PUBLISH: WorkerType.PUBLISHING_WORKER,
    JobType.LEARNING: WorkerType.LEARNING_WORKER,
}


def _validate_float(name: str, value: float, *, non_negative: bool = True) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    if non_negative and value < 0:
        raise ValueError(f"{name} must be non-negative, got {value!r}")


def _validate_int(name: str, value: int, *, minimum: int = 0) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value!r}")


class ResourceClaims:
    """The factory resources one job claims while it runs.

    Units: gpu_units is a fraction of one GPU (0..n), cpu_units is a fraction
    of one core, vram/ram/disk are megabytes.  Values are deterministic inputs
    to the scheduler; the manager never mutates a claim.
    """

    __slots__ = ("gpu_units", "vram_mb", "ram_mb", "cpu_units", "disk_mb")

    def __init__(
        self,
        *,
        gpu_units: float = 0.0,
        vram_mb: int = 0,
        ram_mb: int = 0,
        cpu_units: float = 0.0,
        disk_mb: int = 0,
    ) -> None:
        _validate_float("gpu_units", gpu_units)
        _validate_float("cpu_units", cpu_units)
        _validate_int("vram_mb", vram_mb)
        _validate_int("ram_mb", ram_mb)
        _validate_int("disk_mb", disk_mb)
        self.gpu_units: float = gpu_units
        self.vram_mb: int = vram_mb
        self.ram_mb: int = ram_mb
        self.cpu_units: float = cpu_units
        self.disk_mb: int = disk_mb

    def fits_in(self, capacity: "ResourceClaims") -> bool:
        """True when this claim fits inside a capacity (worker or factory)."""
        return (
            self.gpu_units <= capacity.gpu_units + _GPU_UNITS_TOLERANCE
            and self.vram_mb <= capacity.vram_mb
            and self.ram_mb <= capacity.ram_mb
            and self.cpu_units <= capacity.cpu_units + _GPU_UNITS_TOLERANCE
            and self.disk_mb <= capacity.disk_mb
        )

    def is_zero(self) -> bool:
        return (
            self.gpu_units <= _GPU_UNITS_TOLERANCE
            and self.vram_mb == 0
            and self.ram_mb == 0
            and self.cpu_units <= _GPU_UNITS_TOLERANCE
            and self.disk_mb == 0
        )

    def scaled(self, factor: float) -> "ResourceClaims":
        _validate_float("factor", factor)
        return ResourceClaims(
            gpu_units=self.gpu_units * factor,
            vram_mb=int(self.vram_mb * factor),
            ram_mb=int(self.ram_mb * factor),
            cpu_units=self.cpu_units * factor,
            disk_mb=int(self.disk_mb * factor),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "gpu_units": round(self.gpu_units, 6),
            "vram_mb": self.vram_mb,
            "ram_mb": self.ram_mb,
            "cpu_units": round(self.cpu_units, 6),
            "disk_mb": self.disk_mb,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceClaims":
        return cls(
            gpu_units=float(data["gpu_units"]),
            vram_mb=int(data["vram_mb"]),
            ram_mb=int(data["ram_mb"]),
            cpu_units=float(data["cpu_units"]),
            disk_mb=int(data["disk_mb"]),
        )

    def __repr__(self) -> str:
        return (
            f"ResourceClaims(gpu={self.gpu_units}, vram={self.vram_mb}MB, "
            f"ram={self.ram_mb}MB, cpu={self.cpu_units}, disk={self.disk_mb}MB)"
        )


class WorkerSpec:
    """A static worker definition (id, class, capacity)."""

    __slots__ = ("worker_id", "worker_type", "capacity")

    def __init__(self, *, worker_id: str, worker_type: WorkerType, capacity: ResourceClaims) -> None:
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker_id must be a non-empty string")
        if not isinstance(worker_type, WorkerType):
            raise TypeError("worker_type must be a WorkerType")
        self.worker_id: str = worker_id
        self.worker_type: WorkerType = worker_type
        self.capacity: ResourceClaims = capacity

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type.value,
            "capacity": self.capacity.to_dict(),
        }

    def __repr__(self) -> str:
        return f"WorkerSpec({self.worker_id!r}, {self.worker_type.value})"


class ProductionJob:
    """One immutable job record.  Jobs are replaced (never mutated) on state
    change, mirroring the content-addressed registry pattern of the engine."""

    __slots__ = (
        "job_id",
        "project_id",
        "topic",
        "job_type",
        "worker_type",
        "stage_key",
        "claims",
        "estimated_runtime_ticks",
        "deadline_tick",
        "priority",
        "dependencies",
        "status",
        "worker_id",
        "start_tick",
        "end_tick",
        "retries",
        "max_retries",
        "failure_reason",
        "paused_reason",
        "outcome",
    )

    def __init__(
        self,
        *,
        job_id: str,
        project_id: str,
        topic: str,
        job_type: JobType,
        claims: ResourceClaims,
        estimated_runtime_ticks: int,
        deadline_tick: int,
        priority: int = DEFAULT_PRIORITY,
        dependencies: tuple[str, ...] = (),
        worker_type: WorkerType | None = None,
        status: JobStatus = JobStatus.PENDING,
        worker_id: str | None = None,
        start_tick: int | None = None,
        end_tick: int | None = None,
        retries: int = 0,
        max_retries: int = DEFAULT_MAX_RETRIES,
        failure_reason: str = "",
        paused_reason: str = "",
        outcome: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("job_id must be a non-empty string")
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("project_id must be a non-empty string")
        if not isinstance(job_type, JobType):
            raise TypeError("job_type must be a JobType")
        if not isinstance(claims, ResourceClaims):
            raise TypeError("claims must be a ResourceClaims")
        _validate_int("estimated_runtime_ticks", estimated_runtime_ticks, minimum=1)
        _validate_int("deadline_tick", deadline_tick)
        _validate_int("priority", priority)
        _validate_int("retries", retries)
        _validate_int("max_retries", max_retries, minimum=1)
        if start_tick is not None:
            _validate_int("start_tick", start_tick)
        if end_tick is not None:
            _validate_int("end_tick", end_tick)
        if worker_type is None:
            worker_type = JOB_TYPE_WORKER[job_type]
        if not isinstance(worker_type, WorkerType):
            raise TypeError("worker_type must be a WorkerType")
        if worker_type != JOB_TYPE_WORKER[job_type]:
            raise ValueError(f"job_type {job_type} requires worker {JOB_TYPE_WORKER[job_type]}")
        self.job_id: str = job_id
        self.project_id: str = project_id
        self.topic: str = topic
        self.job_type: JobType = job_type
        self.worker_type: WorkerType = worker_type
        self.stage_key: str = job_type.value
        self.claims: ResourceClaims = claims
        self.estimated_runtime_ticks: int = estimated_runtime_ticks
        self.deadline_tick: int = deadline_tick
        self.priority: int = priority
        self.dependencies: tuple[str, ...] = tuple(dependencies)
        self.status: JobStatus = status
        self.worker_id: str | None = worker_id
        self.start_tick: int | None = start_tick
        self.end_tick: int | None = end_tick
        self.retries: int = retries
        self.max_retries: int = max_retries
        self.failure_reason: str = failure_reason
        self.paused_reason: str = paused_reason
        self.outcome: dict[str, Any] = dict(outcome or {})

    def with_status(
        self,
        *,
        status: JobStatus,
        worker_id: str | None = None,
        start_tick: int | None = None,
        end_tick: int | None = None,
        retries: int | None = None,
        failure_reason: str = "",
        paused_reason: str = "",
        outcome: dict[str, Any] | None = None,
    ) -> "ProductionJob":
        return ProductionJob(
            job_id=self.job_id,
            project_id=self.project_id,
            topic=self.topic,
            job_type=self.job_type,
            claims=self.claims,
            estimated_runtime_ticks=self.estimated_runtime_ticks,
            deadline_tick=self.deadline_tick,
            priority=self.priority,
            dependencies=self.dependencies,
            worker_type=self.worker_type,
            status=status,
            worker_id=worker_id if worker_id is not None else self.worker_id,
            start_tick=start_tick if start_tick is not None else self.start_tick,
            end_tick=end_tick if end_tick is not None else self.end_tick,
            retries=retries if retries is not None else self.retries,
            max_retries=self.max_retries,
            failure_reason=failure_reason if failure_reason else self.failure_reason,
            paused_reason=paused_reason if paused_reason else self.paused_reason,
            outcome=outcome if outcome is not None else self.outcome,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "project_id": self.project_id,
            "topic": self.topic,
            "job_type": self.job_type.value,
            "worker_type": self.worker_type.value,
            "stage_key": self.stage_key,
            "claims": self.claims.to_dict(),
            "estimated_runtime_ticks": self.estimated_runtime_ticks,
            "deadline_tick": self.deadline_tick,
            "priority": self.priority,
            "dependencies": list(self.dependencies),
            "status": self.status.value,
            "worker_id": self.worker_id,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "failure_reason": self.failure_reason,
            "paused_reason": self.paused_reason,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionJob":
        return cls(
            job_id=data["job_id"],
            project_id=data["project_id"],
            topic=data["topic"],
            job_type=JobType(data["job_type"]),
            claims=ResourceClaims.from_dict(data["claims"]),
            estimated_runtime_ticks=int(data["estimated_runtime_ticks"]),
            deadline_tick=int(data["deadline_tick"]),
            priority=int(data["priority"]),
            dependencies=tuple(data["dependencies"]),
            worker_type=WorkerType(data["worker_type"]),
            status=JobStatus(data["status"]),
            worker_id=data["worker_id"],
            start_tick=data["start_tick"],
            end_tick=data["end_tick"],
            retries=int(data["retries"]),
            max_retries=int(data["max_retries"]),
            failure_reason=data["failure_reason"],
            paused_reason=data["paused_reason"],
            outcome=data["outcome"],
        )

    def __repr__(self) -> str:
        return f"ProductionJob({self.job_id!r}, {self.job_type.value}, {self.status.value})"


class LearningEvent:
    """One deterministic learning run recorded on a project."""

    __slots__ = ("sequence", "tick", "pattern_count", "proposal_count", "project_count")

    def __init__(
        self, *, sequence: int, tick: int, pattern_count: int, proposal_count: int, project_count: int
    ) -> None:
        _validate_int("sequence", sequence, minimum=1)
        _validate_int("tick", tick)
        _validate_int("pattern_count", pattern_count)
        _validate_int("proposal_count", proposal_count)
        _validate_int("project_count", project_count)
        self.sequence: int = sequence
        self.tick: int = tick
        self.pattern_count: int = pattern_count
        self.proposal_count: int = proposal_count
        self.project_count: int = project_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "tick": self.tick,
            "pattern_count": self.pattern_count,
            "proposal_count": self.proposal_count,
            "project_count": self.project_count,
        }

    def __repr__(self) -> str:
        return (
            f"LearningEvent(seq={self.sequence}, tick={self.tick}, "
            f"patterns={self.pattern_count}, proposals={self.proposal_count})"
        )


class ProjectStatistics:
    """Aggregated statistics of one project (recomputed on every change)."""

    __slots__ = (
        "total_jobs",
        "completed_jobs",
        "failed_jobs",
        "cancelled_jobs",
        "paused_jobs",
        "total_runtime_ticks",
        "scene_count",
        "mean_qa",
        "reuse_count",
        "asset_count",
        "publish_tick",
        "learning_events",
    )

    def __init__(
        self,
        *,
        total_jobs: int = 0,
        completed_jobs: int = 0,
        failed_jobs: int = 0,
        cancelled_jobs: int = 0,
        paused_jobs: int = 0,
        total_runtime_ticks: int = 0,
        scene_count: int = 0,
        mean_qa: float | None = None,
        reuse_count: int = 0,
        asset_count: int = 0,
        publish_tick: int | None = None,
        learning_events: int = 0,
    ) -> None:
        for name in ("total_jobs", "completed_jobs", "failed_jobs", "cancelled_jobs", "paused_jobs"):
            _validate_int(name, locals()[name])  # type: ignore[arg-type]
        _validate_int("total_runtime_ticks", total_runtime_ticks)
        _validate_int("scene_count", scene_count)
        _validate_int("reuse_count", reuse_count)
        _validate_int("asset_count", asset_count)
        _validate_int("learning_events", learning_events)
        if publish_tick is not None:
            _validate_int("publish_tick", publish_tick)
        if mean_qa is not None:
            _validate_float("mean_qa", mean_qa)
        self.total_jobs: int = total_jobs
        self.completed_jobs: int = completed_jobs
        self.failed_jobs: int = failed_jobs
        self.cancelled_jobs: int = cancelled_jobs
        self.paused_jobs: int = paused_jobs
        self.total_runtime_ticks: int = total_runtime_ticks
        self.scene_count: int = scene_count
        self.mean_qa: float | None = mean_qa
        self.reuse_count: int = reuse_count
        self.asset_count: int = asset_count
        self.publish_tick: int | None = publish_tick
        self.learning_events: int = learning_events

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_jobs": self.total_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "cancelled_jobs": self.cancelled_jobs,
            "paused_jobs": self.paused_jobs,
            "total_runtime_ticks": self.total_runtime_ticks,
            "scene_count": self.scene_count,
            "mean_qa": round(self.mean_qa, 2) if self.mean_qa is not None else None,
            "reuse_count": self.reuse_count,
            "asset_count": self.asset_count,
            "publish_tick": self.publish_tick,
            "learning_events": self.learning_events,
        }

    def __repr__(self) -> str:
        return (
            f"ProjectStatistics(completed={self.completed_jobs}/{self.total_jobs}, "
            f"qa={self.mean_qa}, scenes={self.scene_count})"
        )


class ProductionProject:
    """One immutable project record.  A project owns its job ids and statistics;
    replacement (never mutation) applies, as in the asset engine registry."""

    __slots__ = (
        "project_id",
        "topic",
        "batch_kind",
        "priority",
        "deadline_tick",
        "schedule_tick",
        "knowledge_row_key",
        "disk_budget_mb",
        "job_ids",
        "published",
        "publish_tick",
        "learning_events",
        "asset_count",
        "stats",
    )

    def __init__(
        self,
        *,
        project_id: str,
        topic: str,
        batch_kind: BatchKind,
        priority: int = DEFAULT_PRIORITY,
        deadline_tick: int = 0,
        schedule_tick: int = 0,
        knowledge_row_key: str = "",
        disk_budget_mb: int = 0,
        job_ids: tuple[str, ...] = (),
        published: bool = False,
        publish_tick: int | None = None,
        learning_events: tuple[LearningEvent, ...] = (),
        asset_count: int = 0,
        stats: ProjectStatistics | None = None,
    ) -> None:
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("project_id must be a non-empty string")
        if not isinstance(topic, str) or not topic:
            raise ValueError("topic must be a non-empty string")
        if not isinstance(batch_kind, BatchKind):
            raise TypeError("batch_kind must be a BatchKind")
        _validate_int("priority", priority)
        _validate_int("deadline_tick", deadline_tick)
        _validate_int("schedule_tick", schedule_tick)
        _validate_int("disk_budget_mb", disk_budget_mb)
        if publish_tick is not None:
            _validate_int("publish_tick", publish_tick)
        self.project_id: str = project_id
        self.topic: str = topic
        self.batch_kind: BatchKind = batch_kind
        self.priority: int = priority
        self.deadline_tick: int = deadline_tick
        self.schedule_tick: int = schedule_tick
        self.knowledge_row_key: str = knowledge_row_key
        self.disk_budget_mb: int = disk_budget_mb
        self.job_ids: tuple[str, ...] = tuple(job_ids)
        self.published: bool = published
        self.publish_tick: int | None = publish_tick
        self.learning_events: tuple[LearningEvent, ...] = tuple(learning_events)
        self.asset_count: int = asset_count
        self.stats: ProjectStatistics = stats or ProjectStatistics(total_jobs=len(self.job_ids))

    def with_stats(self, stats: ProjectStatistics) -> "ProductionProject":
        return ProductionProject(
            project_id=self.project_id,
            topic=self.topic,
            batch_kind=self.batch_kind,
            priority=self.priority,
            deadline_tick=self.deadline_tick,
            schedule_tick=self.schedule_tick,
            knowledge_row_key=self.knowledge_row_key,
            disk_budget_mb=self.disk_budget_mb,
            job_ids=self.job_ids,
            published=self.published,
            publish_tick=self.publish_tick,
            learning_events=self.learning_events,
            asset_count=self.asset_count,
            stats=stats,
        )

    def with_published(self, publish_tick: int) -> "ProductionProject":
        return ProductionProject(
            project_id=self.project_id,
            topic=self.topic,
            batch_kind=self.batch_kind,
            priority=self.priority,
            deadline_tick=self.deadline_tick,
            schedule_tick=self.schedule_tick,
            knowledge_row_key=self.knowledge_row_key,
            disk_budget_mb=self.disk_budget_mb,
            job_ids=self.job_ids,
            published=True,
            publish_tick=publish_tick,
            learning_events=self.learning_events,
            asset_count=self.asset_count,
            stats=self.stats,
        )

    def with_learning_event(self, event: LearningEvent, asset_count: int = 0) -> "ProductionProject":
        return ProductionProject(
            project_id=self.project_id,
            topic=self.topic,
            batch_kind=self.batch_kind,
            priority=self.priority,
            deadline_tick=self.deadline_tick,
            schedule_tick=self.schedule_tick,
            knowledge_row_key=self.knowledge_row_key,
            disk_budget_mb=self.disk_budget_mb,
            job_ids=self.job_ids,
            published=self.published,
            publish_tick=self.publish_tick,
            learning_events=self.learning_events + (event,),
            asset_count=asset_count if asset_count else self.asset_count,
            stats=self.stats,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "topic": self.topic,
            "batch_kind": self.batch_kind.value,
            "priority": self.priority,
            "deadline_tick": self.deadline_tick,
            "schedule_tick": self.schedule_tick,
            "knowledge_row_key": self.knowledge_row_key,
            "disk_budget_mb": self.disk_budget_mb,
            "job_ids": list(self.job_ids),
            "published": self.published,
            "publish_tick": self.publish_tick,
            "learning_events": [event.to_dict() for event in self.learning_events],
            "asset_count": self.asset_count,
            "stats": self.stats.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionProject":
        return cls(
            project_id=data["project_id"],
            topic=data["topic"],
            batch_kind=BatchKind(data["batch_kind"]),
            priority=int(data["priority"]),
            deadline_tick=int(data["deadline_tick"]),
            schedule_tick=int(data["schedule_tick"]),
            knowledge_row_key=data["knowledge_row_key"],
            disk_budget_mb=int(data["disk_budget_mb"]),
            job_ids=tuple(data["job_ids"]),
            published=bool(data["published"]),
            publish_tick=data["publish_tick"],
            learning_events=tuple(
                LearningEvent(**{key: value for key, value in event.items()})
                for event in data["learning_events"]
            ),
            asset_count=int(data["asset_count"]),
            stats=ProjectStatistics(**data["stats"]),
        )

    def __repr__(self) -> str:
        return (
            f"ProductionProject({self.project_id!r}, {self.batch_kind.value}, "
            f"jobs={len(self.job_ids)})"
        )


class JobOutcome:
    """The result of executing one job.  Produced by the executor (real or
    simulated); every field is deterministic for a given job and tick."""

    __slots__ = ("success", "outcome", "failure_reason", "qa_score", "duration_ticks")

    def __init__(
        self,
        *,
        success: bool,
        outcome: dict[str, Any] | None = None,
        failure_reason: str = "",
        qa_score: float | None = None,
        duration_ticks: int | None = None,
    ) -> None:
        if not isinstance(success, bool):
            raise TypeError("success must be a bool")
        if qa_score is not None:
            _validate_float("qa_score", qa_score)
        if duration_ticks is not None:
            _validate_int("duration_ticks", duration_ticks, minimum=1)
        self.success: bool = success
        self.outcome: dict[str, Any] = dict(outcome or {})
        self.failure_reason: str = failure_reason
        self.qa_score: float | None = qa_score
        self.duration_ticks: int | None = duration_ticks

    def __repr__(self) -> str:
        status = "ok" if self.success else f"failed: {self.failure_reason}"
        return f"JobOutcome({status}, qa={self.qa_score})"


class ResourceUsage:
    """A snapshot of factory resource utilization at one tick."""

    __slots__ = ("claims", "limits", "tick")

    def __init__(self, *, claims: ResourceClaims, limits: ResourceClaims, tick: int) -> None:
        _validate_int("tick", tick)
        self.claims: ResourceClaims = claims
        self.limits: ResourceClaims = limits
        self.tick: int = tick

    def utilization(self, kind: str) -> float:
        if kind == "gpu_units":
            denominator = self.limits.gpu_units
            value = self.claims.gpu_units
        elif kind == "vram_mb":
            denominator = self.limits.vram_mb
            value = float(self.claims.vram_mb)
        elif kind == "ram_mb":
            denominator = self.limits.ram_mb
            value = float(self.claims.ram_mb)
        elif kind == "cpu_units":
            denominator = self.limits.cpu_units
            value = self.claims.cpu_units
        elif kind == "disk_mb":
            denominator = self.limits.disk_mb
            value = float(self.claims.disk_mb)
        else:
            raise ValueError(f"unknown resource kind {kind!r}")
        if denominator <= 0:
            return 0.0
        return min(1.0, value / denominator)

    def over_limits(self) -> bool:
        """True when any resource exceeds its factory limit."""
        return (
            self.claims.gpu_units > self.limits.gpu_units + _GPU_UNITS_TOLERANCE
            or self.claims.vram_mb > self.limits.vram_mb
            or self.claims.ram_mb > self.limits.ram_mb
            or self.claims.cpu_units > self.limits.cpu_units + _GPU_UNITS_TOLERANCE
            or self.claims.disk_mb > self.limits.disk_mb
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "usage": self.claims.to_dict(),
            "limits": self.limits.to_dict(),
            "utilization": {
                "gpu_units": round(self.utilization("gpu_units"), 6),
                "vram_mb": round(self.utilization("vram_mb"), 6),
                "ram_mb": round(self.utilization("ram_mb"), 6),
                "cpu_units": round(self.utilization("cpu_units"), 6),
                "disk_mb": round(self.utilization("disk_mb"), 6),
            },
        }

    def __repr__(self) -> str:
        return f"ResourceUsage(tick={self.tick}, gpu={self.claims.gpu_units})"


class WorkerStatistics:
    """Per-worker aggregate statistics."""

    __slots__ = (
        "worker_id",
        "worker_type",
        "capacity",
        "executed_jobs",
        "completed_jobs",
        "failed_jobs",
        "busy_ticks",
        "idle_ticks",
    )

    def __init__(
        self,
        *,
        worker_id: str,
        worker_type: WorkerType,
        capacity: ResourceClaims,
        executed_jobs: int = 0,
        completed_jobs: int = 0,
        failed_jobs: int = 0,
        busy_ticks: int = 0,
        idle_ticks: int = 0,
    ) -> None:
        for name in ("executed_jobs", "completed_jobs", "failed_jobs", "busy_ticks", "idle_ticks"):
            _validate_int(name, locals()[name])  # type: ignore[arg-type]
        self.worker_id: str = worker_id
        self.worker_type: WorkerType = worker_type
        self.capacity: ResourceClaims = capacity
        self.executed_jobs: int = executed_jobs
        self.completed_jobs: int = completed_jobs
        self.failed_jobs: int = failed_jobs
        self.busy_ticks: int = busy_ticks
        self.idle_ticks: int = idle_ticks

    @property
    def utilization(self) -> float:
        total = self.busy_ticks + self.idle_ticks
        if total <= 0:
            return 0.0
        return round(self.busy_ticks / total, 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type.value,
            "capacity": self.capacity.to_dict(),
            "executed_jobs": self.executed_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "busy_ticks": self.busy_ticks,
            "idle_ticks": self.idle_ticks,
            "utilization": self.utilization,
        }

    def __repr__(self) -> str:
        return f"WorkerStatistics({self.worker_id!r}, util={self.utilization})"


class ProductionSummary:
    """Factory-wide summary at the end of an execution (or a tick)."""

    __slots__ = (
        "tick",
        "project_count",
        "job_count",
        "completed_jobs",
        "failed_jobs",
        "paused_jobs",
        "cancelled_jobs",
        "active_projects",
        "published_count",
        "mean_qa",
        "asset_reuse_count",
        "asset_count",
        "learning_events",
        "estimated_completion_tick",
        "throughput_per_day",
        "batch_counts",
    )

    def __init__(
        self,
        *,
        tick: int,
        project_count: int = 0,
        job_count: int = 0,
        completed_jobs: int = 0,
        failed_jobs: int = 0,
        paused_jobs: int = 0,
        cancelled_jobs: int = 0,
        active_projects: int = 0,
        published_count: int = 0,
        mean_qa: float | None = None,
        asset_reuse_count: int = 0,
        asset_count: int = 0,
        learning_events: int = 0,
        estimated_completion_tick: int | None = None,
        throughput_per_day: float = 0.0,
        batch_counts: dict[str, int] | None = None,
    ) -> None:
        _validate_int("tick", tick)
        for name in (
            "project_count",
            "job_count",
            "completed_jobs",
            "failed_jobs",
            "paused_jobs",
            "cancelled_jobs",
            "active_projects",
            "published_count",
            "asset_reuse_count",
            "asset_count",
            "learning_events",
        ):
            _validate_int(name, locals()[name])  # type: ignore[arg-type]
        if estimated_completion_tick is not None:
            _validate_int("estimated_completion_tick", estimated_completion_tick)
        if mean_qa is not None:
            _validate_float("mean_qa", mean_qa)
        _validate_float("throughput_per_day", throughput_per_day)
        self.tick: int = tick
        self.project_count: int = project_count
        self.job_count: int = job_count
        self.completed_jobs: int = completed_jobs
        self.failed_jobs: int = failed_jobs
        self.paused_jobs: int = paused_jobs
        self.cancelled_jobs: int = cancelled_jobs
        self.active_projects: int = active_projects
        self.published_count: int = published_count
        self.mean_qa: float | None = mean_qa
        self.asset_reuse_count: int = asset_reuse_count
        self.asset_count: int = asset_count
        self.learning_events: int = learning_events
        self.estimated_completion_tick: int | None = estimated_completion_tick
        self.throughput_per_day: float = throughput_per_day
        self.batch_counts: dict[str, int] = dict(batch_counts or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "project_count": self.project_count,
            "job_count": self.job_count,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "paused_jobs": self.paused_jobs,
            "cancelled_jobs": self.cancelled_jobs,
            "active_projects": self.active_projects,
            "published_count": self.published_count,
            "mean_qa": round(self.mean_qa, 2) if self.mean_qa is not None else None,
            "asset_reuse_count": self.asset_reuse_count,
            "asset_count": self.asset_count,
            "learning_events": self.learning_events,
            "estimated_completion_tick": self.estimated_completion_tick,
            "throughput_per_day": round(self.throughput_per_day, 6),
            "batch_counts": dict(sorted(self.batch_counts.items())),
        }

    def __repr__(self) -> str:
        return (
            f"ProductionSummary(tick={self.tick}, projects={self.project_count}, "
            f"completed={self.completed_jobs}/{self.job_count})"
        )


class Checkpoint:
    """A full factory checkpoint.  Serialized with sorted keys so identical
    states produce byte-identical checkpoint files."""

    __slots__ = ("version", "tick", "next_project_sequence", "projects", "jobs", "workers", "resource_history")

    def __init__(
        self,
        *,
        version: str,
        tick: int,
        next_project_sequence: int,
        projects: tuple[ProductionProject, ...],
        jobs: tuple[ProductionJob, ...],
        workers: tuple[WorkerStatistics, ...],
        resource_history: tuple[dict[str, Any], ...] = (),
    ) -> None:
        _validate_int("tick", tick)
        _validate_int("next_project_sequence", next_project_sequence, minimum=1)
        self.version: str = version
        self.tick: int = tick
        self.next_project_sequence: int = next_project_sequence
        self.projects: tuple[ProductionProject, ...] = tuple(projects)
        self.jobs: tuple[ProductionJob, ...] = tuple(jobs)
        self.workers: tuple[WorkerStatistics, ...] = tuple(workers)
        self.resource_history: tuple[dict[str, Any], ...] = tuple(resource_history)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "tick": self.tick,
            "next_project_sequence": self.next_project_sequence,
            "projects": [project.to_dict() for project in self.projects],
            "jobs": [job.to_dict() for job in self.jobs],
            "workers": [worker.to_dict() for worker in self.workers],
            "resource_history": list(self.resource_history),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        return cls(
            version=data["version"],
            tick=int(data["tick"]),
            next_project_sequence=int(data["next_project_sequence"]),
            projects=tuple(ProductionProject.from_dict(item) for item in data["projects"]),
            jobs=tuple(ProductionJob.from_dict(item) for item in data["jobs"]),
            workers=tuple(WorkerStatistics(**item) for item in data["workers"]),
            resource_history=tuple(data["resource_history"]),
        )


#: Estimator callable: given a topic row dict and optional extra params,
#: returns per-stage :class:`ResourceClaims`.
ClaimsEstimator = Callable[
    [dict[str, Any], dict[str, Any]],
    dict[JobType, ResourceClaims],
]


def topic_slug(topic: str) -> str:
    """Deterministic slug of a topic string, used in project ids."""
    cleaned = "".join(character if character.isalnum() else "-" for character in topic.lower())
    return "-".join(part for part in cleaned.split("-") if part)


def digest(text: str) -> str:
    """Deterministic hex digest used for stable video ids and sim outcomes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
