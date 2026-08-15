"""Shared context and LLM plumbing for the Visual Intelligence Architecture.

Every engine accepts a frozen :class:`VisualContext` (provider, strictness,
sampling constants, and the ComfyUI geometry). LLM-backed stages funnel their
generation through :func:`llm_or_fallback`: when no provider is configured, or
when the model returns something that fails the contract or the content
predicate, the deterministic core of the stage is used instead. In ``strict``
mode those failures raise instead of falling back, so the architecture can be
embedded as a hard gate.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from pr1me.core.errors import PipelineError
from pr1me.core.logging import get_logger
from pr1me.models.common import StableModel
from pr1me.providers.base_provider import BaseProvider, CompletionRequest

T = TypeVar("T", bound=StableModel)

__all__ = ["VisualContext", "llm_or_fallback", "script_text", "strip_json_fence"]

#: Default sampling policy for the creative stages (mirrors the visual stage).
_DEFAULT_TEMPERATURE = 0.7
_DEFAULT_MAX_TOKENS = 2000


@dataclass(frozen=True, slots=True)
class VisualContext:
    """Immutable service bundle for every engine in the architecture."""

    provider: BaseProvider | None = None
    strict: bool = False
    temperature: float = _DEFAULT_TEMPERATURE
    max_tokens: int = _DEFAULT_MAX_TOKENS
    target_width: int = 1080
    target_height: int = 1920
    regeneration_attempts: int = 2


async def llm_or_fallback(
    *,
    context: VisualContext,
    logger: logging.LoggerAdapter,
    template: str,
    variables: dict[str, Any],
    output_model: type[T],
    fallback: Callable[[], T],
    predicate: Callable[[T], bool] | None = None,
) -> T:
    """Generate ``output_model`` from ``template``, or run the deterministic core.

    The fallback is used when no provider is configured, when the provider
    errors, or when the parsed model fails ``predicate`` (a content-level
    sanity check). In ``strict`` mode any of those conditions raises instead.
    """
    provider = context.provider
    if provider is None:
        logger.info("event=visual_architecture.deterministic", reason="no_provider")
        return fallback()
    request = CompletionRequest(
        model=None,
        messages=[
            {"role": "system", "content": template},
            {"role": "user", "content": json.dumps(variables, default=str)},
        ],
        temperature=context.temperature,
        max_tokens=context.max_tokens,
    )
    try:
        structured = await provider.generate_json(request, output_model)
    except PipelineError as exc:
        logger.warning(
            "event=visual_architecture.llm_failed",
            error=exc.message,
            reason="falling_back_to_deterministic",
        )
        if context.strict:
            raise
        return fallback()
    value = structured.value
    if predicate is not None and not predicate(value):
        logger.warning(
            "event=visual_architecture.llm_rejected",
            reason="content_predicate_failed",
        )
        if context.strict:
            raise VisualArchitectureError(
                "LLM output failed the stage content predicate",
                detail={"stage": template.splitlines()[0]},
            )
        return fallback()
    return value


def script_text(topic: str, *, hook: str, explanation: str, practical_insight: str, ending: str) -> str:
    """Flatten the approved narration blocks into one searchable string."""
    return " ".join((topic, hook, explanation, practical_insight, ending)).lower()


def strip_json_fence(text: str) -> str:
    """Remove ```json ... ``` fences some models wrap around JSON in."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


class VisualArchitectureError(PipelineError):
    """A stage of the visual intelligence chain failed hard (strict mode)."""

    code = "visual_architecture_error"


def make_logger(stage: str) -> logging.LoggerAdapter:
    """Build the logger every engine shares (bound to its stage name)."""
    return get_logger(f"pr1me.visual_architecture.{stage}")


def model_dump_safe(value: BaseModel) -> dict[str, Any]:
    """JSON-safe dump for variables passed into prompt templates."""
    return value.model_dump(mode="json")
