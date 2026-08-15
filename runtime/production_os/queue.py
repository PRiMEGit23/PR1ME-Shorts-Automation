"""Execution queue: the unlimited, deterministic job queue of the factory.

The queue admits exactly the seven lifecycle statuses of the Production OS
(pending, running, paused, retry, completed, cancelled, failed) and stores
jobs in a registry keyed by job id with per-status indexes, so large
factories (thousands of projects) dispatch without scanning the whole queue.
Job ordering inside the queue is stable (insertion order by job id), while
the *dispatch* order is decided by the priority engine and the dependency
graph.
"""

from __future__ import annotations

from typing import Any, Iterable

from .production_models import (
    PRODUCTION_OS_VERSION,
    JobStatus,
    ProductionJob,
)


class ExecutionQueue:
    """Registry of every job of the factory, with per-status indexes.

    Jobs are immutable; every state transition stores a *replacement* with the
    same id, so a job id always maps to the newest revision.  The queue never
    drops or deduplicates work: re-planning the same topic produces a new
    project and new job ids.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ProductionJob] = {}
        self._insertion_order: list[str] = []
        self._status_index: dict[JobStatus, dict[str, ProductionJob]] = {
            status: {} for status in JobStatus
        }

    def enqueue(self, job: ProductionJob) -> ProductionJob:
        """Add or replace a job (idempotent by job id)."""
        existing = self._jobs.get(job.job_id)
        if existing is None:
            self._insertion_order.append(job.job_id)
        else:
            self._status_index[existing.status].pop(job.job_id, None)
        self._jobs[job.job_id] = job
        self._status_index[job.status][job.job_id] = job
        return job

    def get(self, job_id: str) -> ProductionJob | None:
        return self._jobs.get(job_id)

    def require(self, job_id: str) -> ProductionJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"unknown job {job_id!r}")
        return job

    def update(self, job: ProductionJob) -> ProductionJob:
        if job.job_id not in self._jobs:
            raise KeyError(f"cannot update unknown job {job.job_id!r}")
        return self.enqueue(job)

    def remove(self, job_id: str) -> ProductionJob:
        job = self._jobs.pop(job_id)
        self._status_index[job.status].pop(job_id, None)
        try:
            self._insertion_order.remove(job_id)
        except ValueError:
            pass
        return job

    def jobs(self) -> tuple[ProductionJob, ...]:
        """All jobs in stable insertion order."""
        return tuple(self._jobs[job_id] for job_id in self._insertion_order)

    def by_status(self, status: JobStatus) -> tuple[ProductionJob, ...]:
        """Jobs in one status, deterministic job-id order."""
        return tuple(sorted(self._status_index[status].values(), key=lambda job: job.job_id))

    def by_project(self, project_id: str) -> tuple[ProductionJob, ...]:
        return tuple(job for job in self.jobs() if job.project_id == project_id)

    def status_counts(self) -> dict[str, int]:
        return {status.value: len(self._status_index[status]) for status in JobStatus}

    def count(self) -> int:
        return len(self._jobs)

    def all_ids(self) -> tuple[str, ...]:
        return tuple(self._insertion_order)

    def ids_by_status(self, status: JobStatus) -> tuple[str, ...]:
        return tuple(sorted(self._status_index[status].keys()))

    def pending_or_paused_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                set(self._status_index[JobStatus.PENDING])
                | set(self._status_index[JobStatus.PAUSED])
                | set(self._status_index[JobStatus.RETRY])
            )
        )

    def clear(self) -> None:
        self._jobs.clear()
        self._insertion_order.clear()
        for bucket in self._status_index.values():
            bucket.clear()

    def snapshot(self) -> dict[str, Any]:
        """Queue snapshot for reporting: status counts plus a per-job summary."""
        return {
            "version": PRODUCTION_OS_VERSION,
            "total_jobs": self.count(),
            "status_counts": dict(self.status_counts()),
            "jobs": [
                {
                    "job_id": job.job_id,
                    "project_id": job.project_id,
                    "topic": job.topic,
                    "job_type": job.job_type.value,
                    "worker_type": job.worker_type.value,
                    "status": job.status.value,
                    "priority": job.priority,
                    "deadline_tick": job.deadline_tick,
                    "estimated_runtime_ticks": job.estimated_runtime_ticks,
                    "start_tick": job.start_tick,
                    "end_tick": job.end_tick,
                    "retries": job.retries,
                }
                for job in self.jobs()
            ],
        }

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, job_id: str) -> bool:
        return job_id in self._jobs

    def __repr__(self) -> str:
        return f"ExecutionQueue(jobs={self.count()}, {self.status_counts()})"


class QueueMetrics:
    """Deterministic aggregate metrics derived from queue state."""

    def __init__(self, jobs: Iterable[ProductionJob]) -> None:
        self._jobs: tuple[ProductionJob, ...] = tuple(jobs)

    @property
    def total_runtime_ticks(self) -> int:
        return sum(job.estimated_runtime_ticks for job in self._jobs)

    @property
    def completed_runtime_ticks(self) -> int:
        return sum(
            job.estimated_runtime_ticks
            for job in self._jobs
            if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED)
        )

    @property
    def remaining_runtime_ticks(self) -> int:
        return max(0, self.total_runtime_ticks - self.completed_runtime_ticks)

    @property
    def mean_priority(self) -> float:
        if not self._jobs:
            return 0.0
        return round(sum(job.priority for job in self._jobs) / len(self._jobs), 2)

    def pending_before(self, tick: int, *, horizon_ticks: int = 86_400) -> int:
        """Unfinished jobs whose deadline falls within ``horizon_ticks`` of the
        given tick (still pending, paused or retrying)."""
        return sum(
            1
            for job in self._jobs
            if job.status in (JobStatus.PENDING, JobStatus.PAUSED, JobStatus.RETRY)
            and job.deadline_tick >= tick
            and job.deadline_tick - tick <= horizon_ticks
        )


def job_id_for(project_id: str, stage_key: str) -> str:
    """Deterministic job identity: ``{project_id}/{stage_key}``."""
    if not project_id or not stage_key:
        raise ValueError("project_id and stage_key must be non-empty")
    return f"{project_id}/{stage_key}"