"""Execution monitor: deterministic tick-level observability of the factory."""

from __future__ import annotations

from typing import Optional

from .production_models import (
    JobStatus,
    ProductionJob,
    ProductionSummary,
    _validate_int,
)
from .priority_engine import rank_eligible


class ExecutionMonitor:
    """Read-only, deterministic view of factory execution state.

    The monitor never mutates state; it only computes snapshots from the
    queue, scheduler, workers and resources that are valid at a given tick.
    """

    def __init__(
        self,
        queue,
        scheduler,
        resources,
        workers,
        projects,
    ) -> None:
        self._queue = queue
        self._scheduler = scheduler
        self._resources = resources
        self._workers = workers
        self._projects = projects

    # ----------------------------------------------------------------- #
    # Next event (the tick at which something finishes)
    # ----------------------------------------------------------------- #

    def next_event_tick(self, tick: int = 0) -> Optional[int]:
        """The smallest ``end_tick`` among running jobs that is ``>= tick``.

        Returns ``None`` when no jobs are running (factory idle or blocked)."""
        _validate_int("tick", tick)
        running = self._queue.by_status(JobStatus.RUNNING)
        ends = [job.end_tick for job in running if job.end_tick is not None and job.end_tick >= tick]
        return min(ends) if ends else None

    # ----------------------------------------------------------------- #
    # Factory-wide summary
    # ----------------------------------------------------------------- #

    def summary(self, tick: int = 0) -> ProductionSummary:
        """Deterministic :class:`ProductionSummary` at *tick*."""
        _validate_int("tick", tick)
        jobs = self._queue.jobs()
        project_count = len(self._projects._projects) if hasattr(self._projects, "_projects") else 0
        completed = sum(1 for j in jobs if j.status == JobStatus.COMPLETED)
        failed = sum(1 for j in jobs if j.status == JobStatus.FAILED)
        paused = sum(1 for j in jobs if j.status == JobStatus.PAUSED)
        cancelled = sum(1 for j in jobs if j.status == JobStatus.CANCELLED)
        active = sum(1 for j in jobs if j.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.RETRY))

        # Mean QA from completed render_image jobs
        render_qas = [
            j.outcome.get("qa_score")
            for j in jobs
            if j.job_type == "render_image" and j.status == JobStatus.COMPLETED and j.outcome.get("qa_score") is not None
        ]
        mean_qa = round(sum(render_qas) / len(render_qas), 2) if render_qas else None

        # Asset reuse from engine if available
        asset_reuse = 0
        try:
            asset_reuse = len(self._scheduler._resources.pause_candidates.__self__.reuse_engine().most_used(limit=1))  # type: ignore[attr-error]
        except Exception:
            asset_reuse = 0

        # Estimated completion tick: last end_tick of running jobs, or None
        nxt = self.next_event_tick(tick)
        est_completion = nxt if nxt is not None else 0

        # Throughput: jobs completed per day so far (deterministic from tick)
        completed_projects = sum(
            1 for p in self._projects._projects.values() if all(
                j.status == JobStatus.COMPLETED for j in self._queue.by_project(p.project_id)
            )
        )
        elapsed_days = max(1, tick / DAY_TICKS)
        throughput_per_day = round(completed_projects / elapsed_days, 6)

        # Batch counts
        batch_counts: dict[str, int] = {}
        for p in self._projects._projects.values() if hasattr(self._projects, "_projects") else []:
            bk = p.batch_kind.value
            batch_counts[bk] = batch_counts.get(bk, 0) + 1

        return ProductionSummary(
            tick=tick,
            project_count=project_count,
            job_count=len(jobs),
            completed_jobs=completed,
            failed_jobs=failed,
            paused_jobs=paused,
            cancelled_jobs=cancelled,
            active_projects=active,
            mean_qa=mean_qa,
            asset_reuse_count=asset_reuse,
            asset_count=sum(1 for j in jobs if j.job_type == "asset_index"),
            learning_events=0,  # will be filled by dashboard when reports exist
            estimated_completion_tick=est_completion,
            throughput_per_day=throughput_per_day,
            batch_counts=batch_counts,
        )

    # ----------------------------------------------------------------- #
    # Per-project progress
    # ----------------------------------------------------------------- #

    def project_progress(self, project_id: str) -> dict[str, Any]:
        """Progress of one project at the current tick."""
        jobs = self._queue.by_project(project_id)
        total = len(jobs)
        if total == 0:
            return {"progress": 0, "status": "unknown"}
        completed = sum(1 for j in jobs if j.status == JobStatus.COMPLETED)
        failed = sum(1 for j in jobs if j.status == JobStatus.FAILED)
        paused = sum(1 for j in jobs if j.status == JobStatus.PAUSED)
        return {
            "progress": round(completed / total, 2) if total else 0,
            "total": total,
            "completed": completed,
            "failed": failed,
            "paused": paused,
            "statuses": {j.status.value for j in jobs},
        }

    # ----------------------------------------------------------------- #
    # Resource utilisation snapshot
    # ----------------------------------------------------------------- #

    def resource_usage(self, *, tick: int = 0) -> dict[str, Any]:
        """Current resource utilisation as a dict suitable for reporting."""
        _validate_int("tick", tick)
        usage = self._resources.current_usage(tick=tick)
        return usage.to_dict()

    # ----------------------------------------------------------------- #
    # Worker utilisation snapshot
    # ----------------------------------------------------------------- #

    def worker_utilization(self) -> dict[str, Any]:
        """Per-worker statistics as a dict."""
        stats = self._workers.statistics()
        return {"workers": [s.to_dict() for s in stats]}