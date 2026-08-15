"""Dependency graph: per-project stage ordering and readiness.

The graph implements the mission rules verbatim:

* render waits for storyboard,
* video waits for images (and voice),
* publisher waits for metadata,
* learning waits for completion (everything in the project),
* asset indexing waits for outputs (images and video).

A job is *ready* when every id in its dependency tuple is completed.  The
graph is derived from job records, so it is always consistent with the queue
and needs no separate persistence.
"""

from __future__ import annotations

from .production_models import (
    STAGE_DEPENDENCIES,
    STAGE_INDEX,
    STAGE_ORDER,
    JobStatus,
    JobType,
    ProductionJob,
)


class DependencyGraph:
    """Read-only, deterministic view of job dependencies."""

    def __init__(self, jobs: tuple[ProductionJob, ...]) -> None:
        self._jobs: dict[str, ProductionJob] = {job.job_id: job for job in jobs}
        self._dependents: dict[str, set[str]] = {}
        for job in jobs:
            for dependency in job.dependencies:
                self._dependents.setdefault(dependency, set()).add(job.job_id)

    @property
    def job_count(self) -> int:
        return len(self._jobs)

    def dependencies_of(self, job_id: str) -> tuple[str, ...]:
        job = self._require(job_id)
        return job.dependencies

    def dependents_of(self, job_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._dependents.get(job_id, set())))

    def is_ready(self, job: ProductionJob, *, completed: set[str]) -> bool:
        """True when all dependencies of ``job`` are in ``completed``."""
        return all(dependency in completed for dependency in job.dependencies)

    def eligible_jobs(
        self,
        jobs: tuple[ProductionJob, ...],
        *,
        completed: set[str],
        statuses: tuple[JobStatus, ...] = (JobStatus.PENDING, JobStatus.PAUSED, JobStatus.RETRY),
    ) -> tuple[ProductionJob, ...]:
        """All jobs whose dependencies are satisfied and whose status is in
        ``statuses`` (deterministic order: job id)."""
        return tuple(
            sorted(
                (
                    job
                    for job in jobs
                    if job.status in statuses and self.is_ready(job, completed=completed)
                ),
                key=lambda job: job.job_id,
            )
        )

    def blocked_jobs(self, jobs: tuple[ProductionJob, ...]) -> tuple[ProductionJob, ...]:
        """Pending jobs that are blocked by at least one unfinished dependency."""
        return tuple(
            sorted(
                (
                    job
                    for job in jobs
                    if job.status == JobStatus.PENDING and not self.is_ready(job, completed=set())
                ),
                key=lambda job: job.job_id,
            )
        )

    def has_cycle(self) -> bool:
        """True when the dependency graph contains a cycle (should never
        happen for the canonical stage graph; guards checkpoints)."""
        visited: set[str] = set()
        in_stack: set[str] = set()

        def visit(job_id: str) -> bool:
            if job_id in in_stack:
                return True
            if job_id in visited:
                return False
            visited.add(job_id)
            in_stack.add(job_id)
            for dependent in self.dependents_of(job_id):
                if visit(dependent):
                    return True
            in_stack.remove(job_id)
            return False

        return any(visit(job_id) for job_id in self._jobs)

    @staticmethod
    def stage_order() -> tuple[JobType, ...]:
        """The canonical stage order of one project."""
        return STAGE_ORDER

    @staticmethod
    def canonical_dependencies(stage: JobType) -> tuple[JobType, ...]:
        """The canonical dependency stages of ``stage``."""
        return STAGE_DEPENDENCIES[stage]

    def _require(self, job_id: str) -> ProductionJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"unknown job {job_id!r}")
        return job

    def __contains__(self, job_id: str) -> bool:
        return job_id in self._jobs

    def __repr__(self) -> str:
        return f"DependencyGraph(jobs={self.job_count}, cyclic={self.has_cycle()})"
