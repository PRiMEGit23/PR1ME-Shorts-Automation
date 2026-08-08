"""Pipeline orchestration package.

Exposes the run-report models and the :class:`PipelineRunner` that executes
registered stages in dependency order.
"""

from pr1me.pipeline.runner import PipelineRunner, RunReport, StageRunRecord

__all__ = ["PipelineRunner", "RunReport", "StageRunRecord"]