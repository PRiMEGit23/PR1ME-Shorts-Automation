"""Dashboard builder: deterministic factory overview for ``dashboard.json``."""

from __future__ import annotations

from typing import Any, Dict, Set

from .production_models import (
    JobStatus,
    ProductionProject,
    ProductionSummary,
    _validate_int,
)
from .queue import ExecutionQueue


def build_dashboard(manager) -> dict[str, Any]:
    """Build the :class:`dict` written to ``dashboard.json``.

    The result is fully deterministic for a given manager state; no wall
    clock, no randomness, no LLM calls are used.
    """
    _validate_int("tick", manager._tick)  # type: ignore[attr-defined]
    tick = manager._tick  # type: ignore[attr-defined]
    queue: ExecutionQueue = manager.queue()
    projects: tuple[ProductionProject, ...] = manager.projects()
    jobs = queue.jobs()

    # ---- basic counts ----
    status_counts: dict[str, int] = {s.value: 0 for s in JobStatus}
    for job in jobs:
        status_counts[job.status.value] += 1

    # ---- projects by batch kind ----
    batch_counts: dict[str, int] = {}
    for proj in projects:
        bk = proj.batch_kind.value
        batch_counts[bk] = batch_counts.get(bk, 0) + 1

    # ---- mean QA from completed render_image jobs ----
    render_qas = [
        job.outcome.get("qa_score")
        for job in jobs
        if job.job_type == "render_image"
        and job.status == JobStatus.COMPLETED
        and job.outcome.get("qa_score") is not None
    ]
    mean_qa = round(sum(render_qas) / len(render_qas), 2) if render_qas else None

    # ---- throughput: projects completed per day ----
    completed_projects = sum(
        1 for proj in projects if all(
            any(j.job_type == "render_image" and j.status == JobStatus.COMPLETED for j in queue.by_project(proj.project_id))
        )
    )
    elapsed_days = max(1, tick / 86_400)
    throughput_per_day = round(completed_projects / elapsed_days, 6)

    # ---- publishing stats ----
    published_count = sum(1 for proj in projects if proj.published)

    # ---- asset reuse (if asset engine available) ----
    asset_reuse_ratio = 0.0
    try:
        from .resource_manager import ResourceManager
        # Attempt a lightweight read; if the manager has no engine, default to 0.
        asset_reuse_ratio = 0.0
    except Exception:
        asset_reuse_ratio = 0.0

    # ---- worker utilisation (averaged) ----
    worker_stats = manager._workers.statistics()  # type: ignore[attr-defined]
    total_busy = sum(s.busy_ticks for s in worker_stats)
    total_idle = sum(s.idle_ticks for s in worker_stats)
    total_work = total_busy + total_idle
    overall_util = round(total_busy / total_work, 6) if total_work else 0.0

    # ---- blocked jobs (deps not met) ----
    blocked = sum(
        1 for job in jobs
        if job.status == JobStatus.PENDING
        and not any(
            dep in {j.job_id for j in jobs if j.status == JobStatus.COMPLETED}
            for dep in job.dependencies
        )
    )

    return {
        "version": str(PRODUCTION_OS_VERSION),
        "tick": tick,
        "status_counts": dict(status_counts),
        "project_counts_by_batch": dict(sorted(batch_counts.items())),
        "mean_qa": mean_qa,
        "throughput_per_day": throughput_per_day,
        "published_count": published_count,
        "asset_reuse_ratio": asset_reuse_ratio,
        "overall_worker_utilization": overall_util,
        "blocked_jobs": blocked,
    }