"""runtime.production_os - PR1ME Operating System (Autonomous Production Factory).

The operating system that manages an unlimited content factory:
unlimited projects, queues, scheduling, resource management,
worker pools, dependency graphs, checkpoint-aware failure recovery,
and six deterministic JSON exports.

All components are typed, documented and tested; the same inputs always
produce the same timeline, the same checkpoints and the same exports.
"""

from .production_models import (  # noqa: F401
    PRODUCTION_OS_VERSION,
    JobStatus,
    JobType,
    WorkerType,
    BatchKind,
    ResourceClaims,
    WorkerStatistics,
    ProductionJob,
    ProductionProject,
    ProjectStatistics,
    LearningEvent,
    Checkpoint,
    ResourceUsage,
)
from .queue import ExecutionQueue  # noqa: F401
from .priority_engine import rank_eligible  # noqa: F401
from .dependency_graph import DependencyGraph  # noqa: F401
from .resource_manager import ResourceManager  # noqa: F401
from .worker_pool import WorkerPool  # noqa: F401
from .scheduler import Scheduler  # noqa: F401
from .executor import JobExecutor, SimulatedExecutor, RealExecutor  # noqa: F401
from .project_manager import ProjectManager  # noqa: F401
from .batch_planner import plan as batch_plan  # noqa: F401
from .execution_monitor import ExecutionMonitor  # noqa: F401
from .failure_recovery import checkpoint, resume, resume_project, resume_stage  # noqa: F401
from .dashboard import build_dashboard  # noqa: F401
from .reporting import export_all  # noqa: F401
from .production_manager import ProductionManager  # noqa: F401

__all__ = [
    "PRODUCTION_OS_VERSION",
    "JobStatus",
    "JobType",
    "WorkerType",
    "BatchKind",
    "ResourceClaims",
    "WorkerStatistics",
    "ProductionJob",
    "ProductionProject",
    "ProjectStatistics",
    "LearningEvent",
    "Checkpoint",
    "ResourceUsage",
    "ExecutionQueue",
    "rank_eligible",
    "DependencyGraph",
    "ResourceManager",
    "WorkerPool",
    "Scheduler",
    "JobExecutor",
    "SimulatedExecutor",
    "RealExecutor",
    "ProjectManager",
    "batch_plan",
    "ExecutionMonitor",
    "checkpoint",
    "resume",
    "resume_project",
    "resume_stage",
    "build_dashboard",
    "export_all",
    "ProductionManager",
]