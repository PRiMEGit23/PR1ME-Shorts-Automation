"""Core cross-cutting infrastructure: config, errors, logging, stages, prompts."""

from pr1me.core.base_stage import BaseStage, StageMetadata
from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.errors import (
    ArtifactIOError,
    ConfigurationError,
    ContractViolationError,
    JobAbortedError,
    ModelValidationError,
    PipelineDependencyError,
    PipelineError,
    PromptLoadError,
    PromptNotFoundError,
    PromptVersionError,
    ProviderNotConfiguredError,
    StageExecutionError,
    StageNotFoundError,
    StageNotImplementedError,
    StageRegistrationError,
)
from pr1me.core.logging import get_logger, setup_logging
from pr1me.core.prompt_loader import PromptDocument, PromptLoader
from pr1me.core.stage_registry import StageRegistry

__all__ = [
    "ArtifactIOError",
    "BaseStage",
    "ConfigurationError",
    "ContractViolationError",
    "JobAbortedError",
    "ModelValidationError",
    "PipelineDependencyError",
    "PipelineError",
    "PromptDocument",
    "PromptLoadError",
    "PromptLoader",
    "PromptNotFoundError",
    "PromptVersionError",
    "ProviderNotConfiguredError",
    "Settings",
    "StageContext",
    "StageExecutionError",
    "StageMetadata",
    "StageNotFoundError",
    "StageNotImplementedError",
    "StageRegistrationError",
    "StageRegistry",
    "get_logger",
    "setup_logging",
]