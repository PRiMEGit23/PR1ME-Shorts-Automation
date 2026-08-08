"""Dependency injection context for stages.

A small, immutable bundle of shared services injected into every stage. The
engine has no globals and no singletons: each stage receives whatever it needs
through its constructor via an optional ``StageContext``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pr1me.core.config import Settings

if TYPE_CHECKING:
    from pr1me.core.prompt_loader import PromptLoader
    from pr1me.providers.base_provider import BaseProvider


@dataclass(frozen=True, slots=True)
class StageContext:
    """Immutable service bundle shared by all stages in one run.

    Everything a stage may need (config, logging, prompts, the AI provider) is
    injected here. Optional fields default to ``None`` so stages that do not
    need an LLM (asset managers, validators, renderers) can still be built.
    """

    settings: Settings
    logger: logging.LoggerAdapter
    prompt_loader: PromptLoader | None = None
    provider: BaseProvider | None = None

    #: Pinned cross-cutting identifiers for this run (optional).
    job_id: str | None = None
    run_id: str | None = None