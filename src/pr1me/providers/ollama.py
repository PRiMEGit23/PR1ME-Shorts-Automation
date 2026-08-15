"""Ollama provider (OpenAI-compatible chat completions API on localhost).

Implements the provider-agnostic :class:`~pr1me.providers.base_provider.BaseProvider`
interface so the pipeline can run fully locally against an Ollama server
(``http://127.0.0.1:11434`` by default). No prompts live here; prompts come
from the stage layer through ``CompletionRequest.messages``.

Unlike the DeepSeek provider, Ollama needs no API key, so construction never
fails on missing credentials. Configuration comes from explicit constructor
arguments or ``PR1ME_OLLAMA_*`` environment variables.
"""

from __future__ import annotations

import asyncio
import os
import random
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import httpx

from pr1me.core.errors import PipelineError, PromptLoadError
from pr1me.core.logging import get_logger
from pr1me.providers.base_provider import (
    BaseProvider,
    Completion,
    CompletionRequest,
    Usage,
)
from pr1me.providers.deepseek import (
    complete_metadata_output,
    complete_script_output,
    complete_visual_shots,
    strip_code_fence,
    substitute_variables,
)

if TYPE_CHECKING:
    from pr1me.core.prompt_loader import PromptLoader

_ENV_BASE_URL = "PR1ME_OLLAMA_BASE_URL"
_ENV_MODEL = "PR1ME_OLLAMA_MODEL"
_ENV_API_KEY = "PR1ME_OLLAMA_API_KEY"

_DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
_DEFAULT_MODEL = "qwen2.5:7b"
_CHAT_PATH = "/chat/completions"

#: HTTP statuses that are safe to retry (client can do nothing about these).
_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}

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


class OllamaProviderError(PipelineError):
    """An Ollama API call failed at the transport or HTTP level."""

    code = "ollama_provider_error"


class OllamaProvider(BaseProvider):
    """Async provider for a local Ollama server's OpenAI-compatible API."""

    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
        prompt_loader: PromptLoader | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url or os.getenv(_ENV_BASE_URL) or _DEFAULT_BASE_URL).rstrip("/")
        self._model = model or os.getenv(_ENV_MODEL) or _DEFAULT_MODEL
        self._api_key = api_key or os.getenv(_ENV_API_KEY) or ""
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay
        self._prompt_loader = prompt_loader
        self._http_client = http_client
        self._owns_client = http_client is None
        self._logger = get_logger("pr1me.providers.ollama", model=self._model)

    # -------------------------------------------------------------- API -----

    async def generate(self, request: CompletionRequest) -> Completion:
        """Post one chat-completion request and return a typed :class:`Completion`."""
        payload = self._build_payload(request)
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        self._logger.debug(
            "event=ollama.request",
            model=payload.get("model"),
            n_messages=len(payload.get("messages", [])),
        )
        client = self._http_client or self._ensure_client()
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

            last_error = OllamaProviderError(
                f"Ollama API returned HTTP {response.status_code}",
                detail={"status": response.status_code, "body": response.text[:300]},
            )
            if response.status_code not in _RETRYABLE_STATUSES or not self._should_retry_attempt(attempt):
                break
            await self._backoff(attempt, reason=f"http {response.status_code}")

        if isinstance(last_error, OllamaProviderError):
            raise last_error
        raise OllamaProviderError(
            f"Ollama request failed: {last_error}",
            detail={"stage": None, "exc_type": type(last_error).__name__},
        ) from last_error

    async def render(self, prompt_file: str, variables: Mapping[str, Any]) -> str:
        """Load a prompt through the configured loader and substitute variables.

        :raises PromptLoadError: when no prompt loader is configured.
        """
        if self._prompt_loader is None:
            raise PromptLoadError("no prompt loader configured for the Ollama provider")
        doc = await self._prompt_loader.load(prompt_file)
        return substitute_variables(doc.content, variables)

    async def health(self) -> bool:
        """A local Ollama backend is healthy when the server answers."""
        client = self._http_client or self._ensure_client()
        try:
            response = await client.get(self._base_url.rsplit("/v1", 1)[0] + "/api/tags")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

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
            "event=ollama.retry",
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
            raise OllamaProviderError(
                "Ollama response missing choices",
                detail={"body": str(data)[:300]},
            ) from exc
        text = complete_metadata_output(
            complete_script_output(
                complete_visual_shots(
                    strip_code_fence(str((choice.get("message") or {}).get("content") or ""))
                )
            )
        )
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