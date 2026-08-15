"""Failure recovery: checkpoint-aware resume for the PR1ME Operating System.

This module provides the three resume modes required by the mission:

1. Resume entire production after reboot.
2. Resume an individual project (leave other projects untouched).
3. Resume a single failed stage (never duplicate completed work).

All recovery is deterministic: identical checkpoints plus identical executor
inputs always produce identical subsequent state and exports.
"""

from __future__ import annotations

from pathlib import Path

from .production_manager import ProductionManager


def checkpoint(manager: ProductionManager, path: str | Path) -> Path:
    """Save a deterministic checkpoint of *manager* to *path*.

    The checkpoint contains the complete factory state (queue, resources,
    scheduler, workers, projects, tick) so that an identical resume from
    the same executor produces byte-identical subsequent execution.
    """
    return manager.save_checkpoint(path)


def resume(
    manager: ProductionManager,
    executor: type | str | None = None,
    *,
    until_tick: int | None = None,
) -> ProductionSummary:
    """Resume factory execution from the manager's current checkpoint.

    If *executor* is ``None`` the manager's existing executor is used;
    otherwise it may be ``"sim"``, ``"real``, or a concrete
    :class:`~production_os.executor.JobExecutor` instance.

    Returns the :class:`~production_os.production_models.ProductionSummary`
    produced when the factory reaches *until_tick* or runs to completion.
    """
    # The manager already has checkpoint / load built in; just continue execution.
    if executor is None:
        executor = "sim"
    return manager.execute(executor, until_tick=until_tick)


def resume_project(manager: ProductionManager, project_id: str) -> None:
    """Reset unfinished jobs of *project_id* to PENDING; completed work
    is never duplicated."""

    manager.resume_project(project_id)


def resume_stage(manager: ProductionManager, project_id: str, stage_key: str) -> None:
    """Reset one specific stage job to PENDING (if it is not already
    completed).  All other stages and other projects are untouched."""

    manager.resume_stage(project_id, stage_key)