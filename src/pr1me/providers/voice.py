"""Voice provider (configurable text-to-speech backend).

Everything that synthesizes narration audio lives here:

- :class:`VoiceBackend` -- the transport seam for a TTS engine
- :class:`HTTPVoiceBackend` -- a generic, configurable ``POST text -> audio
  bytes`` backend (base URL + path come from configuration, never hardcoded)
- :class:`VoiceProvider` -- owns the retry policy, the per-call timeout,
  structured logging, file persistence, and typed response building

The provider is transport-only and concept-agnostic: it knows nothing about
scripts or narration blocks. The stage layer builds the exact narration text
and decides where the audio file lands. It deliberately does **not** extend
:class:`~pr1me.providers.base_provider.BaseProvider`, which is the LLM
completion interface; speech synthesis is a different capability.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
import struct
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from pr1me.core.errors import PipelineError, ProviderNotConfiguredError
from pr1me.core.logging import get_logger

_ENV_PROVIDER = "PR1ME_VOICE_PROVIDER"
_ENV_VOICE = "PR1ME_VOICE_VOICE"
_ENV_SAMPLE_RATE = "PR1ME_VOICE_SAMPLE_RATE"
_ENV_TIMEOUT = "PR1ME_VOICE_TIMEOUT_SECONDS"
_ENV_MAX_RETRIES = "PR1ME_VOICE_MAX_RETRIES"
_ENV_BASE_URL = "PR1ME_VOICE_BASE_URL"
_ENV_PATH = "PR1ME_VOICE_PATH"

_DEFAULT_PROVIDER = "http"
_DEFAULT_VOICE = "default"
_DEFAULT_SAMPLE_RATE = 22050
_DEFAULT_FORMAT = "wav"
_DEFAULT_PATH = "/v1/tts"

_DEFAULT_REQUEST_TIMEOUT = 60.0
_DEFAULT_TIMEOUT = 120.0
_DEFAULT_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0
_RETRY_MAX_DELAY = 30.0

#: HTTP statuses that are safe to retry (nothing to fix client-side).
_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}


class VoiceError(PipelineError):
    """Base class for every voice provider failure."""

    code = "voice_error"


class VoiceSynthesisError(VoiceError):
    """The TTS backend failed to produce audio."""

    code = "voice_synthesis_error"

    def __init__(self, message: str, *, detail: Any | None = None, retryable: bool = False) -> None:
        super().__init__(message, detail=detail)
        self.retryable = retryable


class VoiceTimeoutError(VoiceError):
    """Synthesis did not complete within the configured timeout."""

    code = "voice_timeout_error"


# ------------------------------------------------------------------ typed API -


class VoiceSynthesisRequest(BaseModel):
    """A provider-agnostic text-to-speech request."""

    text: str = Field(..., min_length=1)
    voice: str = _DEFAULT_VOICE
    sample_rate: int = Field(_DEFAULT_SAMPLE_RATE, ge=1, le=768000)
    format: str = _DEFAULT_FORMAT


class VoiceRender(BaseModel):
    """One finalized narration saved to disk."""

    file: str
    text: str
    voice: str
    sample_rate: int
    format: str
    duration_seconds: float
    checksum: str


# ------------------------------------------------------------------ utilities -


def wav_duration(data: bytes) -> tuple[float, int]:
    """Return ``(duration_seconds, sample_rate)`` for PCM WAV bytes.

    Walks the RIFF chunks to locate the ``fmt `` and ``data`` chunks; duration
    is ``data_size / byte_rate``. Returns ``(0.0, 0)`` for anything else.
    """
    if len(data) < 44 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        return 0.0, 0
    sample_rate = 0
    byte_rate = 0
    pos = 12
    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        if chunk_id == b"fmt ":
            if pos + 24 > len(data):
                return 0.0, 0
            audio_format, channels = struct.unpack_from("<HH", data, pos + 8)
            sample_rate, byte_rate = struct.unpack_from("<II", data, pos + 12)
            if audio_format != 1 or channels == 0 or byte_rate == 0:
                return 0.0, sample_rate
        elif chunk_id == b"data":
            if byte_rate <= 0:
                return 0.0, sample_rate
            return size / byte_rate, sample_rate
        pos += 8 + size + (size & 1)
    return 0.0, sample_rate


def _env_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _first(*values: object) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


# ------------------------------------------------------------------- backend --


class VoiceBackend(ABC):
    """Transport seam for a text-to-speech engine.

    Concrete backends (an HTTP service, a local binary, a cloud SDK) implement
    :meth:`synthesize` and return raw audio bytes; the provider layer adds
    retries, timeouts, and typed responses on top.
    """

    name: str = "base"

    @abstractmethod
    async def synthesize(self, request: VoiceSynthesisRequest) -> bytes:
        """Return the encoded narration audio (WAV by default)."""

    async def close(self) -> None:
        """Release any resources owned by this backend."""


class HTTPVoiceBackend(VoiceBackend):
    """Generic HTTP text-to-audio backend.

    POSTs the ``{text, voice, sample_rate, format}`` request as JSON to a
    configurable endpoint and returns the audio bytes from the response body.
    Transport errors and non-200 responses raise :class:`VoiceSynthesisError`;
    the retry policy lives in :class:`VoiceProvider`.
    """

    name = "http"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        path: str | None = None,
        request_timeout: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        base = (base_url or os.getenv(_ENV_BASE_URL) or "").rstrip("/")
        if not base:
            raise ProviderNotConfiguredError(
                f"no voice backend configured; set {_ENV_BASE_URL} or pass base_url="
            )
        self._base_url = base
        self._path = path or os.getenv(_ENV_PATH) or _DEFAULT_PATH
        self._request_timeout = _first(request_timeout, None, _DEFAULT_REQUEST_TIMEOUT)
        self._http_client = http_client
        self._owns_client = http_client is None

    async def synthesize(self, request: VoiceSynthesisRequest) -> bytes:
        client = self._ensure_client()
        try:
            response = await client.post(
                f"{self._base_url}{self._path}", json=request.model_dump(mode="json")
            )
        except httpx.HTTPError as exc:
            raise VoiceSynthesisError(
                f"voice backend transport error: {exc}",
                detail={"exc_type": type(exc).__name__},
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise VoiceSynthesisError(
                f"voice backend returned HTTP {response.status_code}",
                detail={"status": response.status_code, "body": response.text[:300]},
                retryable=response.status_code in _RETRYABLE_STATUSES,
            )
        data = response.content
        if not data:
            raise VoiceSynthesisError("voice backend returned empty audio")
        return data

    async def close(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self._request_timeout)
        return self._http_client


_AVAILABLE_BACKENDS: dict[str, type[VoiceBackend]] = {"http": HTTPVoiceBackend}


def build_backend(provider: str | None = None) -> VoiceBackend:
    """Instantiate the configured voice backend from ``PR1ME_VOICE_PROVIDER``."""
    name = provider or os.getenv(_ENV_PROVIDER) or _DEFAULT_PROVIDER
    try:
        cls = _AVAILABLE_BACKENDS[name]
    except KeyError as exc:
        raise ProviderNotConfiguredError(
            f"voice provider {name!r} is not available; available: {sorted(_AVAILABLE_BACKENDS)}"
        ) from exc
    return cls()


# ------------------------------------------------------------------ provider --


class VoiceProvider:
    """Async client for a configurable text-to-speech backend.

    Configuration comes from explicit constructor arguments or the
    ``PR1ME_VOICE_*`` environment variables. The actual TTS engine is injected
    as a :class:`VoiceBackend` (never hardcoded here); when none is supplied a
    backend is built from configuration, failing fast when none is available.
    """

    name = "voice"

    def __init__(
        self,
        *,
        backend: VoiceBackend | None = None,
        voice: str | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_base_delay: float | None = None,
        retry_max_delay: float | None = None,
    ) -> None:
        self._backend = backend if backend is not None else build_backend()
        self._voice = voice or os.getenv(_ENV_VOICE) or _DEFAULT_VOICE
        self._sample_rate = _first(sample_rate, _env_int(_ENV_SAMPLE_RATE), _DEFAULT_SAMPLE_RATE)
        self._format = (format_ or _DEFAULT_FORMAT).lstrip(".")
        self._timeout = _first(timeout_seconds, _env_float(_ENV_TIMEOUT), _DEFAULT_TIMEOUT)
        self._max_retries = _first(max_retries, _env_int(_ENV_MAX_RETRIES), _DEFAULT_MAX_RETRIES)
        self._retry_base_delay = _first(retry_base_delay, None, _RETRY_BASE_DELAY)
        self._retry_max_delay = _first(retry_max_delay, None, _RETRY_MAX_DELAY)
        self._logger = get_logger(
            "pr1me.providers.voice",
            backend=self._backend.name,
            voice=self._voice,
            sample_rate=self._sample_rate,
        )

    # ------------------------------------------------------------- entry ----

    async def synthesize(
        self,
        text: str,
        *,
        output_dir: str | Path,
        voice: str | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
    ) -> VoiceRender:
        """Synthesize ``text`` through the configured backend and save the audio.

        :param text: the exact narration text to speak.
        :param output_dir: destination folder (created on demand).
        :raises VoiceError: transport, backend, or timeout failures. Fail-fast:
            no partial result is ever returned.
        """
        request = VoiceSynthesisRequest(
            text=text,
            voice=voice or self._voice,
            sample_rate=sample_rate or self._sample_rate,
            format=(format_ or self._format).lstrip("."),
        )
        self._logger.info(
            "event=voice.synthesis.started",
            chars=len(text),
            voice=request.voice,
            sample_rate=request.sample_rate,
        )
        data = await self._retried_synthesize(request)
        render = await asyncio.to_thread(self._save, data, Path(output_dir), request)
        self._logger.info(
            "event=voice.synthesis.completed",
            file=render.file,
            bytes=len(data),
            duration_seconds=render.duration_seconds,
            sample_rate=render.sample_rate,
        )
        return render

    async def close(self) -> None:
        """Release the resources owned by the configured backend."""
        await self._backend.close()

    @property
    def provider_name(self) -> str:
        """Identifier of the configured TTS backend (for provenance)."""
        return self._backend.name

    # ------------------------------------------------------------- retries ---

    async def _retried_synthesize(self, request: VoiceSynthesisRequest) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return await asyncio.wait_for(self._backend.synthesize(request), timeout=self._timeout)
            except TimeoutError:
                last_error = VoiceTimeoutError(
                    f"voice synthesis did not complete within {self._timeout:g}s",
                    detail={"voice": request.voice, "chars": len(request.text)},
                )
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason="timeout")
            except VoiceSynthesisError as exc:
                last_error = exc
                if not exc.retryable:
                    raise exc
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason=exc.message)
        if isinstance(last_error, VoiceError):
            raise last_error
        raise VoiceSynthesisError(f"voice synthesis failed: {last_error}")

    def _should_retry_attempt(self, attempt: int) -> bool:
        return attempt < self._max_retries

    async def _backoff(self, attempt: int, *, reason: str) -> None:
        delay = min(self._retry_base_delay * (2 ** (attempt - 1)), self._retry_max_delay)
        jittered = delay * (0.5 + random.random())
        self._logger.warning(
            "event=voice.retry",
            attempt=attempt,
            reason=reason,
            delay_ms=round(jittered * 1000, 1),
        )
        await asyncio.sleep(jittered)

    def _save(self, data: bytes, output_dir: Path, request: VoiceSynthesisRequest) -> VoiceRender:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"narration.{request.format}"
        target.write_bytes(data)
        duration, actual_rate = wav_duration(data)
        return VoiceRender(
            file=str(target),
            text=request.text,
            voice=request.voice,
            sample_rate=actual_rate or request.sample_rate,
            format=request.format,
            duration_seconds=duration,
            checksum=hashlib.sha256(data).hexdigest(),
        )
