"""Worker pool: the seven worker classes of the factory.

The pool owns image, video, voice, metadata, publishing, asset and learning
workers.  Each worker has a capacity (the max resource claims one job may
use) and runs one job at a time; dispatch is deterministic — a job always
goes to the first free worker whose capacity fits, in worker id order, and
tie-broken by the scheduler's dispatch key.
"""

from __future__ import annotations

from typing import Iterable

from .production_models import (
    ResourceClaims,
    WorkerSpec,
    WorkerStatistics,
    WorkerType,
    _validate_int,
)

# Default factory worker pool: one video, one voice, one metadata, one
# publishing, one asset and one learning worker plus two image workers.
DEFAULT_WORKERS: tuple[WorkerSpec, ...] = (
    WorkerSpec(
        worker_id="image-worker-1",
        worker_type=WorkerType.IMAGE_WORKER,
        capacity=ResourceClaims(gpu_units=1.0, vram_mb=24 * 1024, ram_mb=64 * 1024, cpu_units=8.0, disk_mb=100 * 1024),
    ),
    WorkerSpec(
        worker_id="image-worker-2",
        worker_type=WorkerType.IMAGE_WORKER,
        capacity=ResourceClaims(gpu_units=1.0, vram_mb=24 * 1024, ram_mb=64 * 1024, cpu_units=8.0, disk_mb=100 * 1024),
    ),
    WorkerSpec(
        worker_id="video-worker-1",
        worker_type=WorkerType.VIDEO_WORKER,
        capacity=ResourceClaims(gpu_units=1.0, vram_mb=48 * 1024, ram_mb=128 * 1024, cpu_units=16.0, disk_mb=200 * 1024),
    ),
    WorkerSpec(
        worker_id="voice-worker-1",
        worker_type=WorkerType.VOICE_WORKER,
        capacity=ResourceClaims(cpu_units=2.0, ram_mb=4 * 1024, disk_mb=10 * 1024),
    ),
    WorkerSpec(
        worker_id="metadata-worker-1",
        worker_type=WorkerType.METADATA_WORKER,
        capacity=ResourceClaims(cpu_units=1.0, ram_mb=2 * 1024, disk_mb=5 * 1024),
    ),
    WorkerSpec(
        worker_id="publishing-worker-1",
        worker_type=WorkerType.PUBLISHING_WORKER,
        capacity=ResourceClaims(cpu_units=1.0, ram_mb=2 * 1024, disk_mb=5 * 1024),
    ),
    WorkerSpec(
        worker_id="asset-worker-1",
        worker_type=WorkerType.ASSET_WORKER,
        capacity=ResourceClaims(cpu_units=2.0, ram_mb=4 * 1024, disk_mb=20 * 1024),
    ),
    WorkerSpec(
        worker_id="learning-worker-1",
        worker_type=WorkerType.LEARNING_WORKER,
        capacity=ResourceClaims(cpu_units=4.0, ram_mb=16 * 1024, disk_mb=10 * 1024),
    ),
)

# Default factory-wide limits (roughly the aggregate capacity above).
DEFAULT_LIMITS: ResourceClaims = ResourceClaims(
    gpu_units=2.0,
    vram_mb=48 * 1024,
    ram_mb=128 * 1024,
    cpu_units=24.0,
    disk_mb=250 * 1024,
)


class WorkerPool:
    """Registry of workers with deterministic dispatch bookkeeping."""

    def __init__(self, workers: Iterable[WorkerSpec]) -> None:
        specs = tuple(workers)
        ids = [worker.worker_id for worker in specs]
        if len(set(ids)) != len(ids):
            raise ValueError("worker ids must be unique")
        self._workers: tuple[WorkerSpec, ...] = tuple(sorted(specs, key=lambda worker: worker.worker_id))
        self._current_job: dict[str, str | None] = {worker.worker_id: None for worker in self._workers}
        self._busy_until: dict[str, int] = {worker.worker_id: 0 for worker in self._workers}
        self._executed: dict[str, int] = {worker.worker_id: 0 for worker in self._workers}
        self._completed: dict[str, int] = {worker.worker_id: 0 for worker in self._workers}
        self._failed: dict[str, int] = {worker.worker_id: 0 for worker in self._workers}
        self._busy_ticks: dict[str, int] = {worker.worker_id: 0 for worker in self._workers}
        self._idle_ticks: dict[str, int] = {worker.worker_id: 0 for worker in self._workers}
        self._busy_from: dict[str, int] = {worker.worker_id: 0 for worker in self._workers}

    def all_workers(self) -> tuple[WorkerSpec, ...]:
        return self._workers

    def workers_of(self, worker_type: WorkerType) -> tuple[WorkerSpec, ...]:
        return tuple(worker for worker in self._workers if worker.worker_type == worker_type)

    def worker(self, worker_id: str) -> WorkerSpec:
        for worker in self._workers:
            if worker.worker_id == worker_id:
                return worker
        raise KeyError(f"unknown worker {worker_id!r}")

    def worker_types(self) -> tuple[WorkerType, ...]:
        return tuple(sorted({worker.worker_type for worker in self._workers}, key=lambda t: t.value))

    def can_run(self, worker_id: str, claims: ResourceClaims) -> bool:
        """True when ``worker_id`` is free and its capacity fits ``claims``."""
        return (
            self._current_job[worker_id] is None
            and claims.fits_in(self.worker(worker_id).capacity)
        )

    def pick_worker(self, worker_type: WorkerType, claims: ResourceClaims) -> str | None:
        """First free, capable worker for ``worker_type`` (worker id order)."""
        for worker in self.workers_of(worker_type):
            if self.can_run(worker.worker_id, claims):
                return worker.worker_id
        return None

    def assign(self, worker_id: str, job_id: str, *, now_tick: int, estimated_runtime_ticks: int) -> None:
        """Mark ``worker_id`` busy with ``job_id`` until ``now + runtime``."""
        _validate_int("now_tick", now_tick)
        _validate_int("estimated_runtime_ticks", estimated_runtime_ticks, minimum=1)
        if self._current_job[worker_id] is not None:
            raise ValueError(f"worker {worker_id!r} is busy")
        self._current_job[worker_id] = job_id
        self._busy_until[worker_id] = now_tick + estimated_runtime_ticks
        self._executed[worker_id] += 1
        self._busy_from[worker_id] = now_tick

    def release(self, worker_id: str, *, now_tick: int, success: bool) -> None:
        """Free ``worker_id`` at ``now_tick``; accumulate busy/idle ticks."""
        _validate_int("now_tick", now_tick)
        job_id = self._current_job[worker_id]
        if job_id is None:
            raise ValueError(f"worker {worker_id!r} is idle")
        self._current_job[worker_id] = None
        if success:
            self._completed[worker_id] += 1
        else:
            self._failed[worker_id] += 1
        self._busy_ticks[worker_id] += max(0, now_tick - self._busy_from[worker_id])
        self._idle_ticks[worker_id] += max(0, self._busy_until[worker_id] - now_tick)

    def pause(self, worker_id: str, *, now_tick: int) -> None:
        """Free ``worker_id`` at ``now_tick`` because its job was paused.

        Pausing is not a failure: the job is simply re-dispatched later with a
        fresh window, so only busy ticks up to ``now_tick`` are accrued.
        """
        _validate_int("now_tick", now_tick)
        job_id = self._current_job[worker_id]
        if job_id is None:
            raise ValueError(f"worker {worker_id!r} is idle")
        self._current_job[worker_id] = None
        self._busy_ticks[worker_id] += max(0, now_tick - self._busy_from[worker_id])
        self._busy_from[worker_id] = now_tick
        self._idle_ticks[worker_id] += max(0, self._busy_until[worker_id] - now_tick)

    def current_job(self, worker_id: str) -> str | None:
        return self._current_job[worker_id]

    def busy_until(self, worker_id: str) -> int:
        return self._busy_until[worker_id]

    def free_workers(self, worker_type: WorkerType, *, now_tick: int) -> tuple[str, ...]:
        """Free workers of ``worker_type`` whose busy window has elapsed."""
        return tuple(
            worker.worker_id
            for worker in self.workers_of(worker_type)
            if self._busy_until[worker.worker_id] <= now_tick and self._current_job[worker.worker_id] is None
        )

    def next_free_tick(self, worker_type: WorkerType) -> int:
        """Earliest tick at which some worker of ``worker_type`` is free."""
        busy_until = [
            self._busy_until[worker.worker_id]
            for worker in self.workers_of(worker_type)
            if self._current_job[worker.worker_id] is not None
        ]
        return min(busy_until) if busy_until else 0

    def statistics(self) -> tuple[WorkerStatistics, ...]:
        """Per-worker aggregate statistics (deterministic worker id order)."""
        return tuple(
            WorkerStatistics(
                worker_id=worker.worker_id,
                worker_type=worker.worker_type,
                capacity=worker.capacity,
                executed_jobs=self._executed[worker.worker_id],
                completed_jobs=self._completed[worker.worker_id],
                failed_jobs=self._failed[worker.worker_id],
                busy_ticks=self._busy_ticks[worker.worker_id],
                idle_ticks=self._idle_ticks[worker.worker_id],
            )
            for worker in self._workers
        )

    def type_statistics(self) -> dict[str, dict]:
        """Aggregates per worker type for the worker statistics export."""
        totals: dict[str, dict] = {}
        for stats in self.statistics():
            bucket = totals.setdefault(
                stats.worker_type.value,
                {
                    "worker_count": 0,
                    "executed_jobs": 0,
                    "completed_jobs": 0,
                    "failed_jobs": 0,
                    "busy_ticks": 0,
                    "idle_ticks": 0,
                },
            )
            bucket["worker_count"] += 1
            bucket["executed_jobs"] += stats.executed_jobs
            bucket["completed_jobs"] += stats.completed_jobs
            bucket["failed_jobs"] += stats.failed_jobs
            bucket["busy_ticks"] += stats.busy_ticks
            bucket["idle_ticks"] += stats.idle_ticks
        return {name: dict(sorted(bucket.items())) for name, bucket in sorted(totals.items())}

    def __repr__(self) -> str:
        return f"WorkerPool(workers={len(self._workers)})"
