"""Scheduler: deterministic dispatch of eligible jobs to workers.

The scheduler is the single dispatcher of the factory.  At every tick it:

1. finalizes running jobs whose window has elapsed (they become completed),
2. requeues retries as pending,
3. starts every eligible job in the priority engine's total dispatch order,
   assigning the first capable free worker of the job's class and releasing
   resources — auto-pausing the lowest-priority running job of the same
   class when worker capacity or factory limits require it.

The scheduler keeps an incremental *ready set* (jobs whose dependencies are
met), so a factory with thousands of projects dispatches in time per event
rather than per queue scan.  Every transition is a pure function of the
current state, so schedules are byte-for-byte reproducible from a checkpoint.
"""

from __future__ import annotations

from .dependency_graph import DependencyGraph
from .production_models import (
    JobOutcome,
    JobStatus,
    ProductionJob,
)
from .priority_engine import rank_eligible
from .queue import ExecutionQueue
from .resource_manager import ResourceManager
from .worker_pool import WorkerPool

#: Statuses the scheduler considers dispatchable.
DISPATCHABLE = (JobStatus.PENDING, JobStatus.PAUSED, JobStatus.RETRY)


class Scheduler:
    """The deterministic dispatcher of the factory."""

    def __init__(
        self,
        *,
        queue: ExecutionQueue,
        graph: DependencyGraph,
        workers: WorkerPool,
        resources: ResourceManager,
    ) -> None:
        self._queue: ExecutionQueue = queue
        self._graph: DependencyGraph = graph
        self._workers: WorkerPool = workers
        self._resources: ResourceManager = resources
        self._completed: set[str] = set()
        self._ready: dict[str, ProductionJob] = {}
        self._paused_by: dict[str, str] = {}

    # ------------------------------------------------------------ bookkeeping --

    @property
    def completed_ids(self) -> set[str]:
        return set(self._completed)

    def sync_from_queue(self) -> None:
        """(Re)build the ready set from the whole queue — one scan, used once
        per planned batch or restored checkpoint."""
        self._ready.clear()
        for job in self._queue.jobs():
            if (
                job.status in DISPATCHABLE
                and self._graph.is_ready(job, completed=self._completed)
            ):
                self._ready[job.job_id] = job

    def _prune_ready(self) -> None:
        stale = [job_id for job_id, job in self._ready.items() if job.status not in DISPATCHABLE]
        for job_id in stale:
            self._ready.pop(job_id, None)

    def _add_ready(self, job: ProductionJob) -> None:
        if (
            job.status in DISPATCHABLE
            and self._graph.is_ready(job, completed=self._completed)
        ):
            self._ready[job.job_id] = job
        else:
            self._ready.pop(job.job_id, None)

    # ------------------------------------------------------------------ ticks --

    def tick(self, now_tick: int) -> tuple[ProductionJob, ...]:
        """One scheduling pass at ``now_tick``: finalize due jobs, requeue
        retries, start eligible jobs.  Returns the started jobs in dispatch
        order."""
        self.finalize_due_jobs(now_tick)
        self.requeue_retries(now_tick)
        return self.start_jobs_at(now_tick)

    def finalize_due_jobs(self, tick: int) -> tuple[ProductionJob, ...]:
        """Complete every running job whose window has elapsed."""
        finalized: list[ProductionJob] = []
        for job in self._queue.by_status(JobStatus.RUNNING):
            if job.end_tick is not None and job.end_tick <= tick:
                updated = job.with_status(status=JobStatus.COMPLETED, end_tick=tick)
                self._queue.update(updated)
                self._complete_bookkeeping(updated)
                finalized.append(updated)
        return tuple(finalized)

    def requeue_retries(self, tick: int) -> tuple[ProductionJob, ...]:
        """Move retry jobs back to pending (they rejoin the ready set)."""
        requeued: list[ProductionJob] = []
        for job in self._queue.by_status(JobStatus.RETRY):
            updated = job.with_status(status=JobStatus.PENDING, failure_reason="")
            self._queue.update(updated)
            self._add_ready(updated)
            requeued.append(updated)
        return tuple(requeued)

    def start_jobs_at(self, tick: int) -> tuple[ProductionJob, ...]:
        """Start every ready job possible at ``tick``; returns started jobs in
        deterministic dispatch order."""
        self._prune_ready()
        ready_jobs = rank_eligible(tuple(self._ready.values()), now_tick=tick)
        started: list[ProductionJob] = []
        for job in ready_jobs:
            worker_id = self._pick_worker(job, tick)
            if worker_id is None:
                continue
            updated = job.with_status(
                status=JobStatus.RUNNING,
                worker_id=worker_id,
                start_tick=tick,
                end_tick=tick + job.estimated_runtime_ticks,
            )
            self._workers.assign(
                worker_id,
                job.job_id,
                now_tick=tick,
                estimated_runtime_ticks=job.estimated_runtime_ticks,
            )
            self._resources.acquire(
                job.job_id, job.claims, priority=job.priority, worker_type=job.worker_type
            )
            self._queue.update(updated)
            self._ready.pop(job.job_id, None)
            started.append(updated)
        return tuple(started)

    def _pick_worker(self, job: ProductionJob, tick: int) -> str | None:
        worker_id = self._workers.pick_worker(job.worker_type, job.claims)
        if worker_id is not None and self._resources.fits(job.claims):
            return worker_id
        return self._make_room(job, tick)

    def _make_room(self, job: ProductionJob, tick: int) -> str | None:
        """Auto-pause lower-priority running jobs to make capacity for ``job``.

        Only jobs of the candidate's worker class with strictly lower priority
        may be paused; the pause decision is deterministic and minimal.
        """
        candidates = self._resources.pause_candidates(
            job.priority,
            needed_claims=job.claims,
            candidate_worker_type=job.worker_type,
        )
        for candidate_id in candidates:
            running = self._queue.require(candidate_id)
            self._resources.release(candidate_id)
            self._workers.pause(running.worker_id or "", now_tick=tick)
            paused = running.with_status(
                status=JobStatus.PAUSED,
                paused_reason="auto-paused for higher-priority work",
                worker_id=None,
                start_tick=None,
                end_tick=None,
            )
            self._queue.update(paused)
            self._paused_by[paused.job_id] = f"auto-paused at tick {tick}"
            self._add_ready(paused)
            worker_id = self._workers.pick_worker(job.worker_type, job.claims)
            if worker_id is not None and self._resources.fits(job.claims):
                return worker_id
        return None

    # ----------------------------------------------------------- job outcomes --

    def attach_outcome(self, job: ProductionJob, outcome: JobOutcome) -> ProductionJob:
        """Attach a successful executor outcome to a running job."""
        updated = job.with_status(status=JobStatus.RUNNING, outcome=outcome.outcome)
        self._queue.update(updated)
        return updated

    def handle_failure(self, job: ProductionJob, outcome: JobOutcome, *, tick: int) -> ProductionJob:
        """Release the worker and resources of ``job`` and schedule its retry
        (or mark it failed permanently once the retry budget is spent)."""
        worker_id = job.worker_id
        if worker_id is None:
            raise ValueError(f"job {job.job_id!r} has no assigned worker")
        self._workers.release(worker_id, now_tick=tick, success=False)
        if self._resources.is_held(job.job_id):
            self._resources.release(job.job_id)
        self._ready.pop(job.job_id, None)
        if job.retries < job.max_retries:
            updated = job.with_status(
                status=JobStatus.RETRY,
                retries=job.retries + 1,
                failure_reason=outcome.failure_reason,
                worker_id=None,
                start_tick=None,
                end_tick=None,
            )
        else:
            updated = job.with_status(
                status=JobStatus.FAILED,
                retries=job.retries + 1,
                failure_reason=outcome.failure_reason,
                worker_id=None,
                start_tick=None,
                end_tick=None,
            )
        self._queue.update(updated)
        return updated

    def cancel_job(self, job_id: str, *, tick: int) -> ProductionJob:
        """Cancel a job: pending/paused/retry jobs are removed from dispatch,
        running jobs release their worker and resources immediately."""
        job = self._queue.require(job_id)
        if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED):
            return job
        if job.status == JobStatus.RUNNING:
            worker_id = job.worker_id
            if worker_id is not None and self._workers.current_job(worker_id) == job.job_id:
                self._workers.pause(worker_id, now_tick=tick)
            if self._resources.is_held(job.job_id):
                self._resources.release(job.job_id)
        updated = job.with_status(
            status=JobStatus.CANCELLED,
            worker_id=None,
            start_tick=None,
            end_tick=None,
            paused_reason="",
        )
        self._queue.update(updated)
        self._ready.pop(job.job_id, None)
        return updated

    def _complete_bookkeeping(self, job: ProductionJob) -> None:
        worker_id = job.worker_id
        if worker_id is None:
            raise ValueError(f"job {job.job_id!r} has no assigned worker")
        end_tick = job.end_tick or 0
        self._workers.release(worker_id, now_tick=end_tick, success=True)
        if self._resources.is_held(job.job_id):
            self._resources.release(job.job_id)
        self._completed.add(job.job_id)
        self._ready.pop(job.job_id, None)
        for dependent_id in self._graph.dependents_of(job.job_id):
            dependent = self._queue.require(dependent_id)
            self._add_ready(dependent)

    # ------------------------------------------------------------------ views --

    def paused_jobs(self) -> tuple[ProductionJob, ...]:
        return self._queue.by_status(JobStatus.PAUSED)

    def paused_reason_of(self, job_id: str) -> str:
        return self._paused_by.get(job_id, "")

    def ready_count(self) -> int:
        return len(self._ready)

    def blocked_jobs(self) -> tuple[ProductionJob, ...]:
        """Dispatchable jobs whose dependencies are not all completed (they
        are blocked by failed, cancelled or still-pending dependencies)."""
        return tuple(
            sorted(
                (
                    job
                    for job in self._queue.by_status(JobStatus.PENDING)
                    if not self._graph.is_ready(job, completed=self._completed)
                ),
                key=lambda job: job.job_id,
            )
        )

    def __repr__(self) -> str:
        return f"Scheduler(completed={len(self._completed)}, ready={len(self._ready)})"