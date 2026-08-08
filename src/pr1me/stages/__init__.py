"""Stage implementations package.

Every stage lives in its own module and inherits from ``BaseStage``. Stages
are registered through a ``StageRegistry``; the :func:`register_auto` helper
registers every exported stage in one call so wiring is a single line.
"""

from __future__ import annotations

from typing import TypeVar

from pr1me.core.stage_registry import StageRegistry
from pr1me.stages.topic_stage import TopicStage

#: Every concrete stage in this package, in registration order.
AUTO_STAGES: tuple = (TopicStage,)

__all__ = ["AUTO_STAGES", "TopicStage", "register_auto"]

StageT = TypeVar("StageT")


def register_auto(registry: StageRegistry) -> None:
    """Register all stages in this package into ``registry``."""
    for stage_cls in AUTO_STAGES:
        registry.register(stage_cls)