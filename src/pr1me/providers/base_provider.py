"""Provider-agnostic LLM abstraction.

The engine talks to every AI backend (DeepSeek, OpenAI, Claude, Gemini, local
models) through this single abstract interface. Concrete backends implement
:class:`BaseProvider`; the pipeline never imports provider SDKs or hardcodes
prompt text.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, ValidationError

from pr1me.core.errors import ContractViolationError, ProviderNotConfiguredError
from pr1me.models.contracts.base import OutputT

T = TypeVar("T", bound=BaseModel)

#: A chat message; ``{"role": ..., "content": ...}``.
Message = dict[str, str]


class CompletionRequest(BaseModel):
    """A generic, provider-agnostic completion request."""

    model: str | None = None
    messages: list[Message] = Field(default_factory=list)
    temperature: float | None = None
    max_tokens: int | None = None
    stop: list[str] = Field(default_factory=list)
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    """Token accounting returned by a provider (best-effort)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Completion(BaseModel):
    """A raw completion response from a provider."""

    request: CompletionRequest
    text: str = ""
    finish_reason: str | None = None
    usage: Usage = Field(default_factory=Usage)
    raw: dict[str, Any] = Field(default_factory=dict)

    def parse_json(self, model_cls: type[OutputT]) -> OutputT:
        """Parse ``text`` as JSON into an output contract model.

        :raises ContractViolationError: when the text is not valid JSON or does
            not validate against ``model_cls``.
        """
        try:
            data = json.loads(self.text)
        except json.JSONDecodeError as exc:
            raise ContractViolationError(
                "provider returned invalid JSON",
                detail={"error": str(exc), "snippet": self.text[:200]},
            ) from exc
        try:
            return model_cls.model_validate(data)
        except ValidationError as exc:
            raise ContractViolationError(
                "provider returned JSON that violates the output contract",
                detail={"errors": exc.errors()[:3]},
            ) from exc


class StructuredCompletion(Generic[OutputT]):
    """A completion that has been parsed and validated into an output model."""

    def __init__(self, *, completion: Completion, value: OutputT) -> None:
        self.completion = completion
        self.value = value


class BaseProvider(ABC):
    """Abstract interface every AI backend must implement.

    Subclasses are responsible for transport, authentication, retries, and any
    provider-specific response handling. The engine consumes only the generic
    methods defined here, so backends can be swapped freely.
    """

    name: str = "base"

    @abstractmethod
    async def generate(self, request: CompletionRequest) -> Completion:
        """Generate one completion for the given request."""

    async def generate_json(
        self,
        request: CompletionRequest,
        output_model: type[OutputT],
    ) -> StructuredCompletion[OutputT]:
        """Generate a completion and parse ``text`` into ``output_model``."""
        completion = await self.generate(request)
        value = completion.parse_json(output_model)
        return StructuredCompletion(completion=completion, value=value)

    async def generate_many(
        self, requests: list[CompletionRequest]
    ) -> list[Completion]:
        """Generate several completions (sequential by default)."""
        return [await self.generate(request) for request in requests]

    async def health(self) -> bool:
        """Return whether the provider is configured and reachable."""
        return True

    async def close(self) -> None:
        """Release any underlying resources (sessions, connections)."""


class NoopProvider(BaseProvider):
    """Placeholder provider used when no real backend is configured.

    Fails fast with :class:`ProviderNotConfiguredError` on any completion so the
    engine never silently continues without a model backend.
    """

    name = "noop"

    async def generate(self, request: CompletionRequest) -> Completion:
        raise ProviderNotConfiguredError(
            "no AI provider is configured; set PR1ME_PROVIDER to a real backend"
        )