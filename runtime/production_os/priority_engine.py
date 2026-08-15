"""Priority engine: deterministic scheduling scores and dispatch order.

The factory never leaves scheduling to chance.  Every job receives a priority
score in ``[0, 100]`` derived from its stated priority, its deadline headroom
and its estimated runtime; dispatch order is the stable tuple
``(priority desc, deadline asc, runtime asc, project id, stage index)`` so
equal jobs break ties deterministically.
"""

from __future__ import annotations

from .production_models import (
    DAY_TICKS,
    STAGE_INDEX,
    JobStatus,
    ProductionJob,
    _validate_int,
)

URGENCY_WINDOW_TICKS: int = DAY_TICKS
RUNTIME_SCALE_TICKS: int = DAY_TICKS // 10


def clamp01(value: float) -> float:
    """Clamp a float into ``[0.0, 1.0]``."""
    return max(0.0, min(1.0, value))


def deadline_headroom(deadline_tick: int, now_tick: int, *, horizon_ticks: int = URGENCY_WINDOW_TICKS) -> float:
    """Fraction of scheduling window remaining before the deadline.

    ``1.0`` when the deadline is at or beyond ``horizon_ticks`` from now;
    ``0.0`` when the deadline has already passed.
    """
    _validate_int("deadline_tick", deadline_tick)
    _validate_int("now_tick", now_tick)
    _validate_int("horizon_ticks", horizon_ticks, minimum=1)
    remaining = deadline_tick - now_tick
    if remaining <= 0:
        return 0.0
    if remaining >= horizon_ticks:
        return 1.0
    return round(remaining / horizon_ticks, 6)


def runtime_efficiency(estimated_runtime_ticks: int, *, scale_ticks: int = RUNTIME_SCALE_TICKS) -> float:
    """Short jobs score higher than long ones (same-size work fits more into
    a deadline window).  ``1.0`` for instant work, decaying toward ``0.0``."""
    _validate_int("estimated_runtime_ticks", estimated_runtime_ticks, minimum=1)
    _validate_int("scale_ticks", scale_ticks, minimum=1)
    return round(1.0 / (1.0 + estimated_runtime_ticks / scale_ticks), 6)


def priority_score(
    *,
    priority: int,
    deadline_tick: int,
    estimated_runtime_ticks: int,
    now_tick: int,
) -> float:
    """Deterministic ``[0, 100]`` scheduling score.

    Weights: 50% declared priority, 30% deadline urgency, 20% runtime
    efficiency.  A job whose deadline is due or whose priority is 100 is
    always at the top of its class.
    """
    _validate_int("priority", priority)
    _validate_int("deadline_tick", deadline_tick)
    _validate_int("estimated_runtime_ticks", estimated_runtime_ticks, minimum=1)
    _validate_int("now_tick", now_tick)
    headroom = deadline_headroom(deadline_tick, now_tick)
    urgency = 1.0 - headroom
    efficiency = runtime_efficiency(estimated_runtime_ticks)
    score = 50.0 * (priority / 100.0) + 30.0 * urgency + 20.0 * efficiency
    return round(clamp01(score / 100.0) * 100.0, 2)


def dispatch_key(job: ProductionJob) -> tuple[int, int, int, str, int]:
    """Stable sort key for dispatch: priority desc, deadline asc, runtime asc,
    project id asc, stage order asc.  Total order over all jobs."""
    return (
        -job.priority,
        job.deadline_tick,
        job.estimated_runtime_ticks,
        job.project_id,
        STAGE_INDEX[job.job_type],
    )


def sort_jobs(jobs: tuple[ProductionJob, ...]) -> tuple[ProductionJob, ...]:
    """Return jobs sorted by the deterministic dispatch key."""
    return tuple(sorted(jobs, key=dispatch_key))


def rank_eligible(
    jobs: tuple[ProductionJob, ...],
    *,
    now_tick: int,
    statuses: tuple[JobStatus, ...] = (JobStatus.PENDING, JobStatus.PAUSED, JobStatus.RETRY),
) -> tuple[ProductionJob, ...]:
    """Deterministic dispatch order of the given jobs at ``now_tick``.

    Jobs whose status is not in ``statuses`` are excluded; the remainder are
    sorted by :func:`dispatch_key` (a strict total order).  This is the single
    source of truth for worker dispatch, so executions are reproducible.
    """
    _validate_int("now_tick", now_tick)
    eligible = tuple(job for job in jobs if job.status in statuses)
    return sort_jobs(eligible)


def score_report(job: ProductionJob, *, now_tick: int) -> dict[str, float]:
    """Breakdown of a job's score for dashboards and tests."""
    score = priority_score(
        priority=job.priority,
        deadline_tick=job.deadline_tick,
        estimated_runtime_ticks=job.estimated_runtime_ticks,
        now_tick=now_tick,
    )
    headroom = deadline_headroom(job.deadline_tick, now_tick)
    return {
        "score": score,
        "priority_component": round(50.0 * (job.priority / 100.0), 2),
        "urgency_component": round(30.0 * (1.0 - headroom), 2),
        "efficiency_component": round(20.0 * runtime_efficiency(job.estimated_runtime_ticks), 2),
        "headroom": headroom,
    }
