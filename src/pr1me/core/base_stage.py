"""Reusable base class for all pipeline stages.

Every future stage (Topic, Script, Fact Check, ...) inherits from
:class:`BaseStage`. The base class owns the cross-cutting concerns:

- async execution lifecycle
- input/output contract validation (fail-fast)
- structured logging
- timing
- error handling and exception translation
- stage metadata

Subclasses implement exactly one method: :meth:`BaseStage.execute`, which
receives a validated input model and must return the declared output model.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar, Generic

from pydantic import BaseModel, ValidationError

from pr1me.core.context import StageContext
from pr1me.core.errors import (
    ContractViolationError,
    ModelValidationError,
    PipelineError,
    StageExecutionError,
)
from pr1me.core.logging import get_logger
from pr1me.models.common import StableModel
from pr1me.models.contracts.base import InputT, OutputT


class StageMetadata(BaseModel):
    """Read-only structural metadata describing a registered stage."""

    stage_id: str
    name: str
    version: str
    description: str
    prompt_file: str | None
    input_model: str
    output_model: str
    depends_on: list[str]
    enabled_by_default: bool


class BaseStage(ABC, Generic[InputT, OutputT]):
    """Abstract base class every pipeline stage must inherit from.

    Declare the stage contract as class attributes::

        class TopicStage(BaseStage[TopicInput, TopicOutput]):
            stage_id = "topic"
            name = "Topic Generator"
            description = "Generates one premium 3D-printing topic."
            version = "1.0.0"
            prompt_file = "01_topic_generator.md"
            input_model = TopicInput
            output_model = TopicOutput

            async def execute(self, payload: TopicInput) -> TopicOutput:
                ...

    The public entrypoint is :meth:`run`. It validates the incoming JSON into
    ``input_model``, times and logs the execution, translates failures into
    structured exceptions, and re-validates the result into ``output_model``.
    """

    # -- Stage metadata (override in subclasses) --------------------------------

    stage_id: ClassVar[str]
    name: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    description: ClassVar[str] = ""
    prompt_file: ClassVar[str | None] = None
    depends_on: ClassVar[Sequence[str]] = ()
    enabled_by_default: ClassVar[bool] = True

    # Static type annotations are provided by the subclasses:
    input_model: ClassVar[type[InputT]]
    output_model: ClassVar[type[OutputT]]

    def __init__(self, context: StageContext) -> None:
        self._context = context
        self._logger = get_logger(
            f"pr1me.stages.{self.stage_id}",
            stage=self.stage_id,
            run_id=context.run_id,
            job_id=context.job_id,
        )
        self._verify_contract()

    # ------------------------------------------------------------------ API --

    async def run(self, payload: InputT | BaseModel | dict[str, Any]) -> OutputT:
        """Execute the stage against one JSON-serializable input.

        This is the only public entrypoint. It orchestrates validation, timing,
        logging, and error translation. Subclasses must not override it; they
        implement :meth:`execute` instead.
        """
        self._logger.info("stage.started")
        started = time.perf_counter()
        try:
            validated_input = self._validate_input(payload)
            output = await self.execute(validated_input)
            validated_output = self._validate_output(output)
        except PipelineError as exc:
            raise self._log_failure(exc, started) from exc
        except Exception as exc:  # pragma: no cover - defensive translation
            wrapped = StageExecutionError(
                f"stage {self.stage_id!r} failed: {exc}",
                detail={"stage": self.stage_id, "exc_type": type(exc).__name__},
            )
            raise self._log_failure(wrapped, started) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._logger.info(
            "stage",
            event="stage.completed",
            stage=self.stage_id,
            duration_ms=round(elapsed_ms, 2),
        )
        return validated_output

    @abstractmethod
    async def execute(self, payload: InputT) -> OutputT:
        """Implement the stage's single responsibility.

        Receives an already-validated ``input_model`` and must return a value
        that validates against ``output_model``.
        """

    # ------------------------------------------------------------- metadata --

    def metadata(self) -> StageMetadata:
        """Return the declared stage metadata as a typed model."""
        return StageMetadata(
            stage_id=self.stage_id,
            name=self.name,
            version=self.version,
            description=self.description,
            prompt_file=self.prompt_file,
            input_model=self.input_model.__name__,
            output_model=self.output_model.__name__,
            depends_on=list(self.depends_on),
            enabled_by_default=self.enabled_by_default,
        )

    @property
    def context(self) -> StageContext:
        """The injected service bundle for this run."""
        return self._context

    # ----------------------------------------------------------- internals ---

    def _validate_input(self, payload: Any) -> InputT:
        try:
            if isinstance(payload, BaseModel):
                payload = payload.model_dump(mode="json")
            return self.input_model.model_validate(payload)
        except ValidationError as exc:
            raise ModelValidationError(
                f"stage {self.stage_id!r} received invalid input: {exc.errors()[:3]}",
                detail={"stage": self.stage_id, "errors": exc.errors()[:3]},
            ) from exc

    def _validate_output(self, output: Any) -> OutputT:
        try:
            if isinstance(output, BaseModel):
                output = output.model_dump(mode="json")
            return self.output_model.model_validate(output)
        except ValidationError as exc:
            raise ContractViolationError(
                f"stage {self.stage_id!r} produced a contract violation: {exc.errors()[:3]}",
                detail={"stage": self.stage_id, "errors": exc.errors()[:3]},
            ) from exc
        except Exception as exc:
            raise ContractViolationError(
                f"stage {self.stage_id!r} produced a non-serializable output",
                detail={"stage": self.stage_id, "exc_type": type(exc).__name__},
            ) from exc

    def _verify_contract(self) -> None:
        """Fail fast at construction if the declared contract is incomplete."""
        required = ("stage_id", "name", "input_model", "output_model")
        missing = [attr for attr in required if not hasattr(self, attr)]
        if missing:
            raise PipelineError(
                f"stage {type(self).__name__!r} is missing required metadata: {missing}"
            )
        if not issubclass(self.input_model, StableModel) or not issubclass(self.output_model, StableModel):
            raise PipelineError(
                f"stage {self.stage_id!r} declares non-StableModel contracts."
            )

    def _log_failure(self, exc: PipelineError, started: float) -> PipelineError:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._logger.error(
            "stage",
            event="stage.failed",
            stage=self.stage_id,
            error=exc.code,
            message=exc.message,
            duration_ms=round(elapsed_ms, 2),
            detail=exc.detail,
        )
        return exc