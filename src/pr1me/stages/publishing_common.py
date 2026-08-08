"""Shared prompt handoff for the Publishing Assets stages.

Both publishing stages (Metadata and Thumbnail) follow the same flow: load
their prompt file, send one structured completion request carrying the
approved topic and script, and parse the reply into a typed contract. This is
that flow, implemented once; stage modules only add their deterministic
boundary (post-checks, rendering, manifests).
"""

from __future__ import annotations

from typing import TypeVar

from pr1me.core.context import StageContext
from pr1me.core.errors import PromptNotFoundError, ProviderNotConfiguredError
from pr1me.models.common import StableModel
from pr1me.models.contracts.publishing import PublishingInput
from pr1me.providers.base_provider import CompletionRequest

T = TypeVar("T", bound=StableModel)


async def generate_publishing_payload(
    context: StageContext,
    *,
    prompt_file: str,
    payload: PublishingInput,
    temperature: float | None,
    max_tokens: int | None,
    output_model: type[T],
) -> T:
    """Load ``prompt_file`` and turn ``payload`` into a typed completion.

    :raises PromptNotFoundError: when no prompt loader is configured.
    :raises ProviderNotConfiguredError: when no AI provider is configured.
    """
    loader = context.prompt_loader
    if loader is None:
        raise PromptNotFoundError(f"no prompt loader is configured for {prompt_file}")
    provider = context.provider
    if provider is None:
        raise ProviderNotConfiguredError(f"no AI provider is configured for {prompt_file}")

    doc = await loader.load(prompt_file)
    request = CompletionRequest(
        model=None,
        messages=[
            {"role": "system", "content": doc.content},
            {"role": "user", "content": payload.user_message()},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    structured = await provider.generate_json(request, output_model)
    return structured.value