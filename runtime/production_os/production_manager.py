"""Production manager: the facade that wires together all OS components.

The manager's execution loop is the deterministic tick-based simulation that
drives the factory from start to finish.  It accepts an executor (simulated or
real) and advances tick by tick, finalising jobs, starting new ones and
recording checkpoints.

Every entity is typed, documented and tested; the same inputs always produce
the same timeline, the same checkpoints and the same 6 JSON exports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .batch_planner import plan as batch_plan
from .dependency_graph import DependencyGraph
from .execution_monitor import ExecutionMonitor
from .executor import JobExecutor, RealExecutor, SimulatedExecutor
from .failure_recovery import FailureRecovery
from .priority_engine import rank_eligible
from .production_models import (
    BatchKind,
    JobOutcome,
    JobStatus,
    ProductionJob,
    ProductionProject,
    ProjectStatistics,
    _validate_int,
)
from .production_models import (
    DEFAULT_MAX_RETRIES,
    DAY_TICKS,
    DEFAULT_PRIORITY,
    DEFAULT_LIMITS,
    DEFAULT_WORKERS,
    PRODUCTION_OS_VERSION,
    ResourceClaims,
    ResourceUsage,
    WorkerStatistics,
    WorkerType,
    _validate_float,
)
from .queue import ExecutionQueue
from .resource_manager import ResourceManager
from .scheduler import Scheduler
from .worker_pool import WorkerPool


class ProductionManager:
    """High-level facade of the PR1ME Operating System factory."""

    def __init__(
        self,
        *,
        workers: tuple[WorkerSpec, ...] = DEFAULT_WORKERS,
        limits: ResourceClaims | None = None,
        asset_engine=None,
        learning_engine=None,
        claim_estimator=None,
    ) -> None:
        # --- core state ---
        self._limits: ResourceClaims = limits or DEFAULT_LIMITS
        self._workers: WorkerPool = WorkerPool(workers)
        self._resources: ResourceManager = ResourceManager(limits=self._limits, workers=workers)
        self._queue: ExecutionQueue = ExecutionQueue()
        self._projects: dict[str, ProductionProject] = {}
        self._asset_engine = asset_engine
        self._learning_engine = learning_engine

        # --- derived structures ---
        self._graph: DependencyGraph | None = None
        self._scheduler: Scheduler | None = None
        self._monitor: ExecutionMonitor | None = None

        # --- tick & history ---
        self._tick: int = 0
        self._history: list[dict] = []

        # ----------------------------------------------------------------- #
        # Rebuild the dependency graph from the current queue
        # ----------------------------------------------------------------- #

    def _rebuild_graph(self) -> None:
        jobs = self._queue.jobs()
        self._graph = DependencyGraph(jobs)
        # rebuild scheduler ready set from scratch
        if self._scheduler is not None:
            self._scheduler.sync_from_queue()

    # ----------------------------------------------------------------- #
    # Project / batch management
    # ----------------------------------------------------------------- #

    def plan_batch(
        self,
        topics: tuple[dict[str, Any], ...],
        *,
        batch_kind: BatchKind = BatchKind.SINGLE,
        priority: int = DEFAULT_PRIORITY,
        base_tick: int = 0,
        disk_budget_mb: int = 0,
        claim_estimator: type | None = None,
    ) -> tuple[ProductionProject, ...]:
        """Plan one or more projects from *topics* using *batch_kind*.

        The returned projects have their eight stage jobs already built; the
        caller must add them to the execution queue (via ``self.queue().enqueue``)
        before calling ``execute``.
        """
        _validate_int("priority", priority)
        projects = batch_plan(
            topics,
            batch_kind=batch_kind,
            priority=priority,
            base_tick=base_tick,
            disk_budget_mb=disk_budget_mb,
            claim_estimator=claim_estimator,
        )
        for project in projects:
            self._projects[project.project_id] = project
        return projects

    def project(self, project_id: str) -> ProductionProject | None:
        return self._projects.get(project_id)

    def projects(self) -> tuple[ProductionProject, ...]:
        return tuple(self._projects.values())

    # ----------------------------------------------------------------- #
    # Execution queue access
    # ----------------------------------------------------------------- #

    def queue(self) -> ExecutionQueue:
        return self._queue

    # ----------------------------------------------------------------- #
    # Scheduler, monitor, resources setup
    # ----------------------------------------------------------------- #

    def _ensure_scheduler(self) -> None:
        if self._scheduler is None:
            jobs = self._queue.jobs()
            self._graph = DependencyGraph(jobs)
            self._scheduler = Scheduler(
                queue=self._queue,
                graph=self._graph,
                workers=self._workers,
                resources=self._resources,
            )
            self._monitor = ExecutionMonitor(
                queue=self._queue,
                scheduler=self._scheduler,
                resources=self._resources,
                workers=self._workers,
                projects=self,
            )

    # ----------------------------------------------------------------- #
    # Executor protocol
    # ----------------------------------------------------------------- #

    def _make_executor(self, kind: str = "sim") -> JobExecutor:
        if kind == "real":
            return RealExecutor(
                asset_engine=self._asset_engine,
                learning_engine=self._learning_engine,
                film_params=self._film_params if hasattr(self, "_film_params") else {},
            )
        return SimulatedExecutor()

    # ----------------------------------------------------------------- #
    # Core tick loop
    # ----------------------------------------------------------------- #

    def execute(
        self,
        executor: JobExecutor | str = "sim",
        *,
        until_tick: int | None = None,
        max_ticks: int | None = None,
        checkpoint_every: int | None = None,
    ) -> ProductionSummary:
        """Run the factory simulation until *until_tick* or *max_ticks* limit.

        *executor* may be ``"sim"`` (default, deterministic hash-based),
        ``"real`` (uses the Phase 11/12 production stack collectors), or a
        concrete :class:`JobExecutor` instance.
        """
        if isinstance(executor, str):
            job_executor = self._make_executor(executor)
        else:
            job_executor = executor

        self._ensure_scheduler()
        # Record initial state for history / checkpoints
        self._history.append(self._snapshot())

        tick = self._tick
        events_since_checkpoint = 0

        while True:
            # 1. finalize running jobs whose window has elapsed
            completed = self._scheduler.finalize_due_jobs(tick)

            # 2. requeue retries as pending
            self._scheduler.requeue_retries(tick)

            # 3. start eligible jobs
            started = self._scheduler.start_jobs_at(tick)

            # 4. execute each started job via the executor; attach outcomes
            for job in started:
                outcome = job_executor.execute(job, self._context(job))
                if outcome.success:
                    self._scheduler.attach_outcome(job, outcome)
                else:
                    self._scheduler.handle_failure(job, outcome, tick)

            # 5. record resource snapshot for statistics
            self._resources.record_snapshot(tick=tick)
            self._history.append(self._snapshot())

            # 6. advance tick
            nxt = self._monitor.next_event_tick(tick)
            if nxt is None:
                # No running jobs left; check if there is still work
                if not self._has_pending_work():
                    break  # factory idle — simulation complete
                # Blocked work (e.g. failed deps) — stop deterministically
                # (blocked jobs remain in the queue for export reporting)
                break

            if until_tick is not None and tick >= until_tick:
                break
            if max_ticks is not None and (tick - self._tick) >= max_ticks:
                break

            tick = nxt
            events_since_checkpoint += 1

            if checkpoint_every is not None and events_since_checkpoint >= checkpoint_every:
                self._save_checkpoint_internal()

        self._tick = tick
        return self._final_summary(tick)

    def _context(self, job: ProductionJob) -> dict[str, Any]:
        """Minimal execution context passed to the executor."""
        return {
            "tick": self._tick,
            "project": self._projects.get(job.project_id),
            "queue": self._queue,
            "asset_engine": self._asset_engine,
            "learning_engine": self._learning_engine,
        }

    def _has_pending_work(self) -> bool:
        """True when there is at least one job that is not completed/cancelled/failed."""
        for job in self._queue.jobs():
            if job.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.PAUSED, JobStatus.RETRY):
                return True
        return False

    def _snapshot(self) -> dict[str, Any]:
        """Deterministic snapshot of manager state for checkpoint / history."""
        return {
            "tick": self._tick,
            "queue": self._queue.snapshot(),
            "resources": self._resources.current_usage(tick=self._tick).to_dict(),
            "workers": self._workers.statistics(),
            "projects": {
                pid: proj.to_dict() for pid, proj in self._projects.items()
            },
        }

    def _final_summary(self, tick: int) -> ProductionSummary:
        return self._monitor.summary(tick)

    # ----------------------------------------------------------------- #
    # Checkpoint / resume
    # ----------------------------------------------------------------- #

    def save_checkpoint(self, path: str | Path) -> Path:
        """Write a deterministic checkpoint file (sorted JSON, byte-identical)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self._snapshot()
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True, indent=2)
        return p

    @classmethod
    def load_checkpoint(cls, path: str | Path, *, claim_estimator=None) -> "ProductionManager":
        """Restore a ProductionManager from a previously saved checkpoint."""
        p = Path(path)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Reconstruct the minimal state
        if isinstance(data["workers"], list):
            workers = tuple(WorkerSpec(**w) for w in data["workers"][0]["capacity"].values())
        else:
            workers = DEFAULT_WORKERS
        mgr = cls(
            workers=workers,
            limits=ResourceClaims(**data["resources"].get("limits", {})) if data.get("resources") else DEFAULT_LIMITS,
        )
        # Restore queue
        mgr._queue = ExecutionQueue()
        # Re-enqueue jobs from saved queue snapshot
        for jq in data["queue"]["jobs"]:
            from .production_models import ProductionJob
            job = ProductionJob.from_dict(jq)
            mgr._queue.enqueue(job)
        # Restore graph & scheduler
        mgr._rebuild_graph()
        # Restore tick
        mgr._tick = data["tick"]
        # Restore history (optional)
        return mgr

    # ----------------------------------------------------------------- #
    # Exports
    # ----------------------------------------------------------------- #

    def export(self, output_dir: str | Path) -> dict[str, Path]:
        """Write the six deterministic JSON exports required by the mission."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        summary = self._monitor.summary(self._tick)

        # 1. production_report.json
        report_path = out / "production_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary.to_dict(), f, sort_keys=True, indent=2)

        # 2. dashboard.json
        dashboard_path = out / "dashboard.json"
        # Build a compact dashboard dict from monitor + queue
        dashboard_data = {
            "version": PRODUCTION_OS_VERSION,
            "tick": self._tick,
            "project_count": summary.project_count,
            "job_count": summary.job_count,
            "completed": summary.completed_jobs,
            "failed": summary.failed_jobs,
            "mean_qa": summary.mean_qa,
            "throughput_per_day": summary.throughput_per_day,
            "batch_counts": dict(sorted(summary.batch_counts.items())),
        }
        with open(dashboard_path, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, sort_keys=True, indent=2)

        # 3. queue.json
        queue_path = out / "queue.json"
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(self._queue.snapshot(), f, sort_keys=True, indent=2)

        # 4. projects.json
        projects_path = out / "projects.json"
        proj_data = {
            "version": PRODUCTION_OS_VERSION,
            "projects": [
                p.to_dict() for p in self._projects.values()
            ],
        }
        with open(projects_path, "w", encoding="utf-8") as f:
            json.dump(proj_data, f, sort_keys=True, indent=2)

        # 5. worker_statistics.json
        worker_path = out / "worker_statistics.json"
        ws_data = {
            "version": PRODUCTION_OS_VERSION,
            "workers": [w.to_dict() for w in self._workers.statistics()],
        }
        with open(worker_path, "w", encoding="utf-8") as f:
            json.dump(ws_data, f, sort_keys=True, indent=2)

        # 6. resource_statistics.json
        res_path = out / "resource_statistics.json"
        # Use the history captured during execution (if any); otherwise zeros.
        history = self._history if self._history else [summary.to_dict()]
        resource_hist = [h.get("resources", {}) for h in history]
        res_data = {
            "version": PRODUCTION_OS_VERSION,
            "limits": self._limits.to_dict(),
            "history": resource_hist,
            "peak": {
                "gpu_units": max((h.get("gpu_units", 0) for h in resource_hist), default=0),
                "vram_mb": max((h.get("vram_mb", 0) for h in resource_hist), default=0),
                "ram_mb": max((h.get("ram_mb", 0) for h in resource_hist), default=0),
                "cpu_units": max((h.get("cpu_units", 0) for h in resource_hist), default=0),
                "disk_mb": max((h.get("disk_mb", 0) for h in resource_hist), default=0),
            },
        }
        with open(res_path, "w", encoding="utf-8") as f:
            json.dump(res_data, f, sort_keys=True, indent=2)

        return {
            "production_report": report_path,
            "dashboard": dashboard_path,
            "queue": queue_path,
            "projects": projects_path,
            "worker_statistics": worker_path,
            "resource_statistics": res_path,
        }

    # ----------------------------------------------------------------- #
    # Resume helpers
    # ----------------------------------------------------------------- #

    def resume_project(self, project_id: str) -> None:
        """Reset unfinished jobs of *project_id* to PENDING; completed stay
        completed (never duplicated)."""
        project = self._projects.get(project_id)
        if project is None:
            return
        for job_id in project.job_ids:
            job = self._queue.require(job_id)
            if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED):
                # Never re-run completed, cancelled or permanently failed work.
                continue
            # Reset to PENDING (retryable)
            updated = job.with_status(JobStatus.PENDING, failure_reason="")
            self._queue.update(updated)
            # Re-add to scheduler ready set
            if self._scheduler is not None:
                self._scheduler._add_ready(updated)

    def resume_stage(self, project_id: str, stage_key: str) -> None:
        """Reset one specific stage job to PENDING (if it is not already
        completed).  All other stages of the project are untouched."""
        job_id = f"{project_id}/{stage_key}"
        job = self._queue.require(job_id)  # may raise if unknown
        if job.status == JobStatus.COMPLETED:
            # mission: never duplicate completed work → silently skip
            return
        updated = job.with_status(JobStatus.PENDING, failure_reason="")
        self._queue.update(updated)
        if self._scheduler is not None:
            self._scheduler._add_ready(updated)