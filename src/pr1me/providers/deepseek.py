"""DeepSeek AI provider (OpenAI-compatible chat completions API).

Implements the provider-agnostic :class:`~pr1me.providers.base_provider.BaseProvider`
interface. No prompt text lives here; prompts come from the stage layer through
the ``CompletionRequest.messages``. Configuration comes from explicit
constructor arguments or ``PR1ME_DEEPSEEK_*`` environment variables.

Transport is retried with exponential backoff for transient network errors and
retryable HTTP statuses (408/429/5xx) so short bursts of instability do not
fail an entire run.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import httpx

from pr1me.core.errors import (
    PipelineError,
    PromptLoadError,
    ProviderNotConfiguredError,
)
from pr1me.core.logging import get_logger
from pr1me.providers.base_provider import (
    BaseProvider,
    Completion,
    CompletionRequest,
    Usage,
)

if TYPE_CHECKING:
    from pr1me.core.prompt_loader import PromptLoader

_ENV_API_KEY = "PR1ME_DEEPSEEK_API_KEY"
_ENV_BASE_URL = "PR1ME_DEEPSEEK_BASE_URL"
_ENV_MODEL = "PR1ME_DEEPSEEK_MODEL"

_DEFAULT_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"
_CHAT_PATH = "/chat/completions"

#: HTTP statuses that are safe to retry (client can do nothing about these).
_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}

#: ``{identifier}`` placeholders used for prompt variable substitution.
_VARIABLE_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

#: Keys of CompletionRequest handled explicitly; everything left in ``extra``
#: is passed through verbatim (top_p, response_format, json_mode, ...).
_KNOWN_REQUEST_FIELDS = {
    "model",
    "messages",
    "temperature",
    "max_tokens",
    "stop",
    "frequency_penalty",
    "presence_penalty",
}


def substitute_variables(text: str, variables: Mapping[str, Any]) -> str:
    """Replace ``{name}`` placeholders with ``variables`` (unknown left intact)."""
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in variables:
            return str(variables[key])
        return match.group(0)

    return _VARIABLE_RE.sub(_replace, text)


class DeepSeekProviderError(PipelineError):
    """A DeepSeek API call failed at the transport or HTTP level."""

    code = "deepseek_provider_error"


class DeepSeekProvider(BaseProvider):
    """Async provider for DeepSeek's OpenAI-compatible chat API.

    Fails fast at construction when no API key is available so a misconfigured
    backend never silently produces empty results.
    """

    name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
        prompt_loader: PromptLoader | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv(_ENV_API_KEY) or os.getenv("DEEPSEEK_API_KEY")
        if not self._api_key:
            raise ProviderNotConfiguredError(
                f"DeepSeek API key missing; set {_ENV_API_KEY} or pass api_key="
            )
        self._base_url = (base_url or os.getenv(_ENV_BASE_URL) or _DEFAULT_BASE_URL).rstrip("/")
        self._model = model or os.getenv(_ENV_MODEL) or _DEFAULT_MODEL
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay
        self._prompt_loader = prompt_loader
        self._http_client = http_client
        self._owns_client = http_client is None
        self._logger = get_logger("pr1me.providers.deepseek", model=self._model)

    # -------------------------------------------------------------- API -----

    async def generate(self, request: CompletionRequest) -> Completion:
        """Post one chat-completion request and return a typed :class:`Completion`."""
        payload = self._build_payload(request)
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        self._logger.debug(
            "event=deepseek.request",
            model=payload.get("model"),
            n_messages=len(payload.get("messages", [])),
        )
        client = self._ensure_client() if self._owns_client else (self._http_client or self._ensure_client())
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.post(
                    f"{self._base_url}{_CHAT_PATH}", json=payload, headers=headers
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason=f"transport {type(exc).__name__}")
                continue

            if response.status_code == 200:
                data: dict[str, Any] = response.json()
                return self._to_completion(request, data)

            last_error = DeepSeekProviderError(
                f"DeepSeek API returned HTTP {response.status_code}",
                detail={"status": response.status_code, "body": response.text[:300]},
            )
            if response.status_code not in _RETRYABLE_STATUSES or not self._should_retry_attempt(attempt):
                break
            await self._backoff(attempt, reason=f"http {response.status_code}")

        if isinstance(last_error, DeepSeekProviderError):
            raise last_error
        raise DeepSeekProviderError(
            f"DeepSeek request failed: {last_error}",
            detail={"stage": None, "exc_type": type(last_error).__name__},
        ) from last_error

    async def render(self, prompt_file: str, variables: Mapping[str, Any]) -> str:
        """Load a prompt through the configured loader and substitute variables.

        :raises PromptLoadError: when no prompt loader is configured.
        """
        if self._prompt_loader is None:
            raise PromptLoadError("no prompt loader configured for the DeepSeek provider")
        doc = await self._prompt_loader.load(prompt_file)
        return substitute_variables(doc.content, variables)

    async def health(self) -> bool:
        """A configured DeepSeek backend is considered healthy."""
        return True

    async def close(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()

    # ------------------------------------------------------------ internals --

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self._timeout)
        return self._http_client

    def _should_retry_attempt(self, attempt: int) -> bool:
        return attempt < self._max_retries

    async def _backoff(self, attempt: int, *, reason: str) -> None:
        delay = min(self._retry_base_delay * (2 ** (attempt - 1)), self._retry_max_delay)
        jittered = delay * (0.5 + random.random())
        self._logger.warning(
            "event=deepseek.retry",
            attempt=attempt,
            reason=reason,
            delay_ms=round(jittered * 1000, 1),
        )
        await asyncio.sleep(jittered)

    def _build_payload(self, request: CompletionRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model or self._model,
            "messages": request.messages,
        }
        for field in ("temperature", "max_tokens", "frequency_penalty", "presence_penalty"):
            value = getattr(request, field)
            if value is not None:
                payload[field] = value
        if request.stop:
            payload["stop"] = request.stop
        for key, value in request.extra.items():
            if key not in _KNOWN_REQUEST_FIELDS:
                payload[key] = value
        return payload

    def _to_completion(self, request: CompletionRequest, data: dict[str, Any]) -> Completion:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            raise DeepSeekProviderError(
                "DeepSeek response missing choices",
                detail={"body": str(data)[:300]},
            ) from exc
        text = str((choice.get("message") or {}).get("content") or "")
        usage_raw = data.get("usage") or {}
        return Completion(
            request=request,
            text=text,
            finish_reason=choice.get("finish_reason"),
            usage=Usage(
                prompt_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
                total_tokens=int(usage_raw.get("total_tokens", 0) or 0),
            ),
            raw=data,
        )