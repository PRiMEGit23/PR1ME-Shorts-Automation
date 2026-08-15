"""Resource manager: factory-wide resource accounting and auto-pause.

The manager tracks GPU, CPU, RAM, VRAM and disk claims of every running job
against the factory limits (ComfyUI/Ollama instances and voice/video workers
are represented by their worker capacities in :mod:`worker_pool`).  When a
candidate job would exceed a limit, the scheduler asks the manager which
running jobs to *auto-pause* (lowest priority first) so the candidate can
start; paused jobs release their claims and are re-dispatched later.
"""

from __future__ import annotations

from typing import Iterable

from .production_models import (
    ResourceClaims,
    ResourceUsage,
    WorkerSpec,
    WorkerType,
    _validate_int,
)


class ResourceManager:
    """Deterministic utilization accounting against fixed factory limits."""

    def __init__(self, *, limits: ResourceClaims, workers: Iterable[WorkerSpec] = ()) -> None:
        if limits is None:
            raise TypeError("limits must be a ResourceClaims")
        self._limits: ResourceClaims = limits
        self._workers: tuple[WorkerSpec, ...] = tuple(workers)
        self._running_claims: dict[str, ResourceClaims] = {}
        self._job_priority: dict[str, int] = {}
        self._job_worker: dict[str, WorkerType] = {}
        self._history: list[dict] = []

    @property
    def limits(self) -> ResourceClaims:
        return self._limits

    def workers(self) -> tuple[WorkerSpec, ...]:
        return self._workers

    def workers_of(self, worker_type: WorkerType) -> tuple[WorkerSpec, ...]:
        return tuple(
            sorted(
                (worker for worker in self._workers if worker.worker_type == worker_type),
                key=lambda worker: worker.worker_id,
            )
        )

    def acquire(self, job_id: str, claims: ResourceClaims, *, priority: int, worker_type: WorkerType) -> None:
        """Register the claims of a starting job.  Raises when the factory
        limits would be exceeded (the scheduler must avoid this state)."""
        if job_id in self._running_claims:
            raise ValueError(f"job {job_id!r} already holds resources")
        combined = self._sum(self._running_claims.values(), claims)
        if self._exceeds(combined):
            raise ValueError(f"job {job_id!r} claims would exceed factory limits")
        self._running_claims[job_id] = claims
        self._job_priority[job_id] = priority
        self._job_worker[job_id] = worker_type

    def release(self, job_id: str) -> ResourceClaims:
        claims = self._running_claims.pop(job_id)
        self._job_priority.pop(job_id, None)
        self._job_worker.pop(job_id, None)
        return claims

    def is_held(self, job_id: str) -> bool:
        return job_id in self._running_claims

    def running(self) -> tuple[tuple[str, ResourceClaims], ...]:
        return tuple(sorted(self._running_claims.items(), key=lambda item: item[0]))

    def current_usage(self, *, tick: int = 0) -> ResourceUsage:
        """Aggregated claims of all running jobs at ``tick``."""
        _validate_int("tick", tick)
        combined = self._sum(*self._running_claims.values())
        return ResourceUsage(claims=combined, limits=self._limits, tick=tick)

    def fits(self, claims: ResourceClaims) -> bool:
        """True when adding ``claims`` keeps every resource within limits."""
        combined = self._sum(self._running_claims.values(), claims)
        return not self._exceeds(combined)

    def over_limits(self) -> bool:
        return self._exceeds(self.current_usage().claims)

    def record_snapshot(self, *, tick: int) -> None:
        """Append the usage snapshot at ``tick`` to the deterministic history
        used by the resource statistics export."""
        self._history.append(self.current_usage(tick=tick).to_dict())

    def resource_history(self) -> tuple[dict, ...]:
        return tuple(self._history)

    def clear_history(self) -> None:
        self._history.clear()

    def pause_candidates(
        self,
        candidate_priority: int,
        *,
        needed_claims: ResourceClaims,
        candidate_worker_type: WorkerType | None = None,
    ) -> tuple[str, ...]:
        """Deterministic ids of running jobs to auto-pause so that
        ``needed_claims`` can fit: lowest priority first, then earliest
        acquisition.

        Only jobs that (a) are running, (b) have priority strictly below the
        candidate's priority and (c) run on ``candidate_worker_type`` (when
        given) may be paused.  Returns the minimal set that frees enough
        capacity; jobs are not paused when pausing them cannot make the
        candidate fit.
        """
        candidates = [
            (job_id, claims)
            for job_id, claims in self._running_claims.items()
            if self._job_priority.get(job_id, 0) < candidate_priority
            and (candidate_worker_type is None or self._job_worker.get(job_id) == candidate_worker_type)
        ]
        candidates.sort(key=lambda item: (self._job_priority.get(item[0], 0), item[0]))
        paused: list[str] = []
        remaining = self._sum(*self._running_claims.values())
        for job_id, claims in candidates:
            paused.append(job_id)
            remaining = self._subtract(remaining, claims)
            combined = self._sum(remaining, needed_claims)
            if not self._exceeds(combined):
                break
        else:
            return ()
        return tuple(sorted(paused))

    def utilization_breakdown(self, *, tick: int = 0) -> dict[str, float]:
        """Per-resource utilization fractions at ``tick``."""
        return self.current_usage(tick=tick).to_dict()["utilization"]

    @staticmethod
    def _sum(*claim_sets: ResourceClaims) -> ResourceClaims:
        return ResourceClaims(
            gpu_units=sum(claims.gpu_units for claims in claim_sets),
            vram_mb=sum(claims.vram_mb for claims in claim_sets),
            ram_mb=sum(claims.ram_mb for claims in claim_sets),
            cpu_units=sum(claims.cpu_units for claims in claim_sets),
            disk_mb=sum(claims.disk_mb for claims in claim_sets),
        )

    @staticmethod
    def _subtract(total: ResourceClaims, claims: ResourceClaims) -> ResourceClaims:
        return ResourceClaims(
            gpu_units=max(0.0, total.gpu_units - claims.gpu_units),
            vram_mb=max(0, total.vram_mb - claims.vram_mb),
            ram_mb=max(0, total.ram_mb - claims.ram_mb),
            cpu_units=max(0.0, total.cpu_units - claims.cpu_units),
            disk_mb=max(0, total.disk_mb - claims.disk_mb),
        )

    def _exceeds(self, claims: ResourceClaims) -> bool:
        return (
            claims.gpu_units > self._limits.gpu_units
            or claims.vram_mb > self._limits.vram_mb
            or claims.ram_mb > self._limits.ram_mb
            or claims.cpu_units > self._limits.cpu_units
            or claims.disk_mb > self._limits.disk_mb
        )
