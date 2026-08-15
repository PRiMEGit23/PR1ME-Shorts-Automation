"""Batch planner: deterministic grouping of topics into projects by kind."""

from __future__ import annotations

from typing import Sequence

from .production_models import (
    BatchKind,
    ClaimsEstimator,
    _default_claims_estimator,
    ProductionProject,
    _validate_int,
)


# ------------------------------------------------------------------- #
# Tick constants
# ------------------------------------------------------------------- #

DAY_TICKS: int = 86_400
WEEK_TICKS: int = 7 * DAY_TICKS
MONTH_TICKS: int = 30 * DAY_TICKS


# ------------------------------------------------------------------- #
# Deterministic topic slug (used for stable ordering)
# ------------------------------------------------------------------- #

def _topic_slug(topic: str) -> str:
    cleaned = "".join(c if c.isalnum() else "-" for c in topic.lower())
    return "-".join(part for part in cleaned.split("-") if part)


# ------------------------------------------------------------------- #
# Public API
# ------------------------------------------------------------------- #


def plan(
    topics: Sequence[dict[str, Any]],
    *,
    batch_kind: BatchKind = BatchKind.SINGLE,
    priority: int = 50,
    base_tick: int = 0,
    disk_budget_mb: int = 0,
    claim_estimator: ClaimsEstimator | None = None,
) -> tuple[ProductionProject, ...]:
    """Plan projects from *topics* according to *batch_kind*.

    Every call produces the same projects for the same inputs — the
    schedule is fully deterministic, so checkpoints and replays are
    reproducible.

    The returned projects have their eight stage jobs already built (but
    not yet enqueued); the caller (usually :class:`ProductionManager`)
    will add them to the execution queue.
    """
    _validate_int("priority", priority)
    _validate_int("base_tick", base_tick, minimum=0)
    _validate_int("disk_budget_mb", disk_budget_mb, minimum=0)

    estimator = claim_estimator or _default_claims_estimator
    projects: list[ProductionProject] = []
    seen_ids: set[str] = set()

    for i, topic in enumerate(topics):
        topic_name = topic.get("topic", f"topic-{i}")
        # Ensure a stable project id even for repeated topics.
        slug = _topic_slug(topic_name)
        project_id = f"p-{batch_kind.value}-{slug}-{i:04d}"
        if project_id in seen_ids:
            # Duplicate project id (same topic repeated); skip to avoid
            # ambiguous scheduling; the manager may still enqueue the
            # job if the caller wishes, but the planner avoids it.
            continue
        seen_ids.add(project_id)

        row = {
            "topic": topic_name,
            "category": topic.get("category", ""),
            "keywords": topic.get("keywords", ""),
            "scene_count": topic.get("scene_count", 5),
        }

        # Plan the project and its eight stage jobs.
        pm = ProjectManager.create(claim_estimator=estimator)
        project, jobs = pm.plan_project(
            project_id=project_id,
            topic=topic_name,
            batch_kind=batch_kind,
            priority=priority,
            deadline_tick=0,  # will be overridden below
            schedule_tick=0,
            disk_budget_mb=disk_budget_mb,
            row=row,
        )

        # Override deadline and schedule according to batch kind.
        if batch_kind == BatchKind.SINGLE:
            project = project.with_stats(
                project.stats._replace(
                    total_jobs=len(jobs),
                )
            )
            project = project._replace(
                deadline_tick=base_tick + WEEK_TICKS,
                schedule_tick=base_tick,
            )
        elif batch_kind == BatchKind.DAILY:
            # each project gets its own day; wrap after 30 days for safety.
            day_offset = i * DAY_TICKS
            schedule_tick = base_tick + day_offset
            deadline_tick = schedule_tick + DAY_TICKS
            project = project._replace(deadline_tick=deadline_tick, schedule_tick=schedule_tick)
        elif batch_kind == BatchKind.WEEKLY:
            week_offset = i * WEEK_TICKS
            schedule_tick = base_tick + week_offset
            deadline_tick = schedule_tick + WEEK_TICKS
            project = project._replace(deadline_tick=deadline_tick, schedule_tick=schedule_tick)
        elif batch_kind == BatchKind.MONTHLY:
            month_offset = i * MONTH_TICKS
            schedule_tick = base_tick + month_offset
            deadline_tick = schedule_tick + MONTH_TICKS
            project = project._replace(deadline_tick=deadline_tick, schedule_tick=schedule_tick)

        # Rebuild project with corrected deadline/schedule (ProductionProject
        # is immutable, so we replace it).
        project = ProductionProject(
            project_id=project.project_id,
            topic=project.topic,
            batch_kind=project.batch_kind,
            priority=project.priority,
            deadline_tick=project.deadline_tick,
            schedule_tick=project.schedule_tick,
            knowledge_row_key=project.knowledge_row_key,
            disk_budget_mb=project.disk_budget_mb,
            job_ids=project.job_ids,
            published=project.published,
            publish_tick=project.publish_tick,
            learning_events=project.learning_events,
            asset_count=project.asset_count,
            stats=project.stats,
        )
        projects.append(project)

    return tuple(projects)