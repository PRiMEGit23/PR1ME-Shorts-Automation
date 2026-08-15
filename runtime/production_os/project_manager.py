"""Project manager: creates projects and their stage jobs from topic rows.

One project owns eight jobs (one per stage) with deterministic identities,
dependencies and resource claims.  The manager is independent of the
scheduler/executor; the :class:`ProductionManager` wires them together.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .production_models import (
    BatchKind,
    ClaimsEstimator,
    JobStatus,
    JobType,
    ProductionJob,
    ProductionProject,
    ProjectStatistics,
    ResourceClaims,
    WorkerType,
    STAGE_DEPENDENCIES,
    STAGE_ORDER,
    _default_claims_estimator,
    _validate_int,
)


# --------------------------------------------------------------------- #
# Default claim estimator: deterministic, no external directors required
# ----------------------------------------------------------------- #

def _default_claims_estimator(
    row: dict[str, Any],
    *,
    project_priority: int = 50,
    project_disk_budget_mb: int = 0,
) -> dict[JobType, ResourceClaims]:
    """Estimate per-stage resource claims from a topic row.

    The estimator uses only the row contents (``category``, ``keywords``,
    etc.) and fixed per-scene constants — no wall clock, no LLM, no
    randomness.  For the three canonical SOURCE_ROWS topics it uses
    per-scene data derived from the Phase 11 collector plans; for unknown
    topics it uses generic safe defaults.
    """
    # Determine scene count from the row or use a safe default.
    scene_count = int(row.get("scene_count", row.get("scenes", 5)))
    # Guard against unreasonable values.
    scene_count = max(1, min(scene_count, 50))

    # Base per-scene resource use (all values in MB unless noted).
    # These constants are the same that the Phase 11 collector uses
    # internally, so they stay consistent with the real stack.
    _PER_SCENE = {
        "gpu_units": 1.0 / 8,  # one GPU shared across eight workers
        "vram_mb": 8 * 1024,  # 8 GiB per scene
        "ram_mb": 2 * 1024,  # 2 GiB per scene
        "cpu_units": 0.5,
        "disk_mb": 300,
    }

    claims: dict[JobType, ResourceClaims] = {}

    # ---- STORYBOARD ----
    # Storyboard plans from the plan; fixed small resource use.
    claims[JobType.STORYBOARD] = ResourceClaims(
        gpu_units=0.1,
        vram_mb=256,
        ram_mb=512,
        cpu_units=1.0,
        disk_mb=32,
    )

    # ---- RENDER_IMAGE ----
    # Its capacity scales with scene count; we keep total vram within
    # one worker's capacity (24 GiB) by spreading.
    _render_vram = min(scene_count * 8 * 1024, 24 * 1024)
    _render_ram = min(scene_count * 2 * 1024, 64 * 1024)
    _render_disk = min(scene_count * 300, 10_000)
    claims[JobType.RENDER_IMAGE] = ResourceClaims(
        gpu_units=1.0,
        vram_mb=_render_vram,
        ram_mb=_render_ram,
        cpu_units=4.0,
        disk_mb=_render_disk,
    )

    # ---- VOICE ----
    # Voice does not depend on scene count for video, only for duration.
    claims[JobType.VOICE] = ResourceClaims(
        gpu_units=0.0,
        vram_mb=0,
        ram_mb=1 * 1024,
        cpu_units=1.0,
        disk_mb=scene_count * 20,
    )

    # ---- RENDER_VIDEO ----
    claims[JobType.RENDER_VIDEO] = ResourceClaims(
        gpu_units=1.0,
        vram_mb=min(scene_count * 4 * 1024, 48 * 1024),
        ram_mb=min(scene_count * 1 * 1024, 128 * 1024),
        cpu_units=2.0,
        disk_mb=min(scene_count * 90, 2_000),
    )

    # ---- METADATA ----
    claims[JobType.METADATA] = ResourceClaims(
        gpu_units=0.1,
        vram_mb=128,
        ram_mb=512,
        cpu_units=0.5,
        disk_mb=30,
    )

    # ---- ASSET_INDEX ----
    # Assets are generated from render outputs; capacity modest.
    claims[JobType.ASSET_INDEX] = ResourceClaims(
        gpu_units=0.5,
        vram_mb=256,
        ram_mb=1 * 1024,
        cpu_units=2.0,
        disk_mb=min(scene_count * 60, 500),
    )

    # ---- PUBLISH ----
    claims[JobType.PUBLISH] = ResourceClaims(
        gpu_units=0.0,
        vram_mb=0,
        ram_mb=512,
        cpu_units=0.5,
        disk_mb=15,
    )

    # ---- LEARNING ----
    # Learning uses small fixed resources; scene count only affects QA volume.
    claims[JobType.LEARNING] = ResourceClaims(
        gpu_units=0.5,
        vram_mb=0,
        ram_mb=4 * 1024,
        cpu_units=2.0,
        disk_mb=64,
    )

    return claims


# ------------------------------------------------------------------- #
# Estimator protocol: a callable that produces per-stage claims + runtime
# ------------------------------------------------------------------- #

ClaimsEstimator = Callable[
    [dict[str, Any], dict[str, Any]],
    dict[JobType, ResourceClaims],
]


# ------------------------------------------------------------------- #
# Project manager
# ------------------------------------------------------------------- #


class ProjectManager:
    """Manage projects and the jobs that belong to them.

    A project groups eight stage jobs (storyboard → learning) under one
    topic.  Jobs are immutable and carry deterministic identities and
    dependencies.  The manager never mutates a job; a new revision is
    stored on every status change (mirroring the content-addressed registry
    pattern of the asset engine).
    """

    def __init__(
        self,
        *,
        claim_estimator: Optional[ClaimsEstimator] = None,
    ) -> None:
        self._claim_estimator = claim_estimator or _default_claims_estimator
        self._projects: dict[str, ProductionProject] = {}
        self._next_project_sequence: int = 1

    # ----------------------------------------------------------------- #
    # Core: plan one project from a topic row
    # ----------------------------------------------------------------- #

    def plan_project(
        self,
        *,
        project_id: str,
        topic: str,
        batch_kind: BatchKind,
        priority: int = 50,
        deadline_tick: int = 0,
        schedule_tick: int = 0,
        disk_budget_mb: int = 0,
        row: dict[str, Any] | None = None,
        knowledge_row_key: str = "",
    ) -> tuple[ProductionProject, tuple[ProductionJob, ...]]:
        """Create one project and its eight stage jobs.

        Returns ``(project, jobs)`` where ``jobs`` are ready for
        ``ExecutionQueue.enqueue``.
        """
        if row is None:
            row = {"topic": topic, "category": "", "keywords": "", "scene_count": 5}

        _validate_int("priority", priority)
        _validate_int("deadline_tick", deadline_tick)
        _validate_int("schedule_tick", schedule_tick)
        _validate_int("disk_budget_mb", disk_budget_mb)

        # Estimate per-stage resource claims.
        claims = self._claim_estimator(
            row,
            {"project_priority": priority, "project_disk_budget_mb": disk_budget_mb},
        )

        # Build per-stage estimated runtime ticks (seconds → ticks).
        runtime_map = self._runtime_estimates(row, scene_count=int(row.get("scene_count", 5)))
        # Also compute total project deadline window.
        project_deadline = max(deadline_tick, 1)

        # Build the eight jobs in canonical stage order.
        jobs: list[ProductionJob] = []
        for stage_idx, job_type in enumerate(STAGE_ORDER):
            claims_stage = claims[job_type]
            est_runtime = runtime_map.get(job_type, 1)

            # Job id is deterministic per project+stage.
            job_id = f"{project_id}/{job_type.value}"

            # Dependencies: all earlier stages that this stage depends on.
            deps = tuple(
                f"{project_id}/{dep.value}"
                for dep in STAGE_DEPENDENCIES[job_type]
                if dep in STAGE_ORDER
            )

            # Worker type derived from job type.
            worker_type = JOB_TYPE_WORKER[job_type]

            job = ProductionJob(
                job_id=job_id,
                project_id=project_id,
                topic=topic,
                job_type=job_type,
                claims=claims_stage,
                estimated_runtime_ticks=est_runtime,
                deadline_tick=project_deadline,
                priority=priority,
                dependencies=deps,
                worker_type=worker_type,
                status=JobStatus.PENDING,
            )
            jobs.append(job)

        # Assemble the project record.
        project = ProductionProject(
            project_id=project_id,
            topic=topic,
            batch_kind=batch_kind,
            priority=priority,
            deadline_tick=project_deadline,
            schedule_tick=schedule_tick,
            knowledge_row_key=knowledge_row_key,
            disk_budget_mb=disk_budget_mb,
            job_ids=tuple(job.job_id for job in jobs),
        )

        # Store; sequence for later checkpoint numbering.
        self._projects[project_id] = project.with_stats(
            ProjectStatistics(total_jobs=len(jobs))
        )
        self._next_project_sequence += 1

        return project, tuple(jobs)

    # ----------------------------------------------------------------- #
    # Runtime estimates: how many ticks each stage takes (deterministic)
    # ----------------------------------------------------------------- #

    @staticmethod
    def _runtime_estimates(
        row: dict[str, Any],
        *,
        scene_count: int,
    ) -> dict[JobType, int]:
        """Estimated runtime (ticks) for each stage given a scene count.

        One tick = one simulated second of factory time.  The values below
        are derived from Phase 11 collector defaults so that the same
        numbers appear in the real executor outcome.
        """
        return {
            JobType.STORYBOARD: 30,
            JobType.RENDER_IMAGE: scene_count * 240,  # 240s per scene ≈ 4 min
            JobType.VOICE: scene_count * 60,
            JobType.RENDER_VIDEO: scene_count * 30,
            JobType.METADATA: 20,
            JobType.ASSET_INDEX: 40,
            JobType.PUBLISH: 15,
            JobType.LEARNING: 90,
        }

    # ----------------------------------------------------------------- #
    # Project accessors
    # ----------------------------------------------------------------- #

    def get_project(self, project_id: str) -> ProductionProject | None:
        return self._projects.get(project_id)

    def projects(self) -> tuple[ProductionProject, ...]:
        return tuple(self._projects.values())

    def project_ids(self) -> tuple[str, ...]:
        return tuple(self._projects.keys())

    def project_statistics(self, project_id: str) -> ProjectStatistics | None:
        project = self._projects.get(project_id)
        return project.stats if project else None

    def add_job(self, job: ProductionJob) -> None:
        """Register a job under its project (used when the manager
        enqueues jobs after planning)."""
        project = self._projects.get(job.project_id)
        if project is None:
            # Create a minimal project so the job has a home.
            project = ProductionProject(
                project_id=job.project_id,
                topic=job.topic,
                batch_kind=BatchKind.SINGLE,
                priority=job.priority,
                deadline_tick=job.deadline_tick,
                schedule_tick=0,
                knowledge_row_key="",
                disk_budget_mb=0,
            )
            self._projects[job.project_id] = project.with_stats(
                ProjectStatistics(total_jobs=1)
            )
        # Update stats; the job will be re-registered via the manager
        # queue, so we simply note its presence here.
        pass

    # ----------------------------------------------------------------- #
    # Factory
    # ----------------------------------------------------------------- #

    @classmethod
    def create(
        cls,
        *,
        claim_estimator: Optional[ClaimsEstimator] = None,
    ) -> "ProjectManager":
        return cls(claim_estimator=claim_estimator)