"""Structured, fail-fast exception hierarchy for the pipeline.

Every exception carries a stable machine-readable ``code`` plus a human
``message``. The orchestrator translates these into the shared failure shape
``{"status": "failed", "reason": ...}`` for JSON stage handoffs.
"""

from __future__ import annotations

from typing import Any


class PipelineError(Exception):
    """Base class for all pipeline exceptions."""

    code: str = "pipeline_error"

    def __init__(self, message: str, *, detail: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_failure(self) -> dict[str, Any]:
        """Return the shared failure JSON shape from PIPELINE_SPEC.md."""
        payload: dict[str, Any] = {"status": "failed", "reason": self.message}
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


class ConfigurationError(PipelineError):
    """Invalid or missing engine configuration."""

    code = "config_error"


class PromptLoadError(PipelineError):
    """A prompt file could not be loaded or parsed."""

    code = "prompt_load_error"


class PromptNotFoundError(PipelineError):
    """A requested prompt file does not exist in the prompt catalog."""

    code = "prompt_not_found"


class ModelValidationError(PipelineError):
    """A stage contract model failed validation."""

    code = "model_validation_error"


class ContractViolationError(PipelineError):
    """A stage output violated the declared output model contract."""

    code = "contract_violation"


class StageNotFoundError(PipelineError):
    """A stage identifier is not registered."""

    code = "stage_not_found"


class StageRegistrationError(PipelineError):
    """A stage could not be registered (duplicate, invalid contract, etc.)."""

    code = "stage_registration_error"


class PipelineDependencyError(PipelineError):
    """Stage dependency graph is invalid (missing dep, cycle, ordering)."""

    code = "pipeline_dependency_error"


class PromptVersionError(PipelineError):
    """A prompt failed a version verification check."""

    code = "prompt_version_error"


class StageNotImplementedError(PipelineError):
    """A stage has not been implemented yet (skeleton placeholder)."""

    code = "stage_not_implemented"


class ProviderNotConfiguredError(PipelineError):
    """No AI provider is configured or the provider cannot serve a request."""

    code = "provider_not_configured"


class StageExecutionError(PipelineError):
    """A stage failed while executing."""

    code = "stage_execution_error"


class ArtifactIOError(PipelineError):
    """Reading or writing a JSON artifact failed."""

    code = "artifact_io_error"


class JobAbortedError(PipelineError):
    """The pipeline run was aborted by a fail-fast stage failure."""

    code = "job_aborted"
