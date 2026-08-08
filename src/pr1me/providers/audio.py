"""Audio mixing provider (configurable mastering backend).

Everything that masters narration into a single audio track lives here:

- :class:`AudioMixer` -- the transport seam for a mixing engine
- :class:`FFmpegAudioMixer` -- a concrete backend that drives a configurable
  ``ffmpeg`` binary (duck BGM beneath narration + loudness-normalize)
- :class:`AudioProvider` -- owns the retry policy, the per-call timeout,
  structured logging, file persistence, and typed response building

The provider is transport-only and concept-agnostic: it knows nothing about
manifests or shots. The stage layer decides which BGM/SFX files to use and
where the mastered file lands. It deliberately does **not** extend
:class:`~pr1me.providers.base_provider.BaseProvider`, which is the LLM
completion interface; audio mastering is a different capability.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
import shlex
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pr1me.core.errors import PipelineError, ProviderNotConfiguredError
from pr1me.core.logging import get_logger
from pr1me.providers.voice import _env_float, _env_int, _first, wav_duration

_ENV_PROVIDER = "PR1ME_AUDIO_PROVIDER"
_ENV_FFMPEG = "PR1ME_AUDIO_FFMPEG_BIN"
_ENV_LUFS = "PR1ME_AUDIO_TARGET_LUFS"
_ENV_SAMPLE_RATE = "PR1ME_AUDIO_SAMPLE_RATE"
_ENV_TIMEOUT = "PR1ME_AUDIO_TIMEOUT_SECONDS"
_ENV_MAX_RETRIES = "PR1ME_AUDIO_MAX_RETRIES"

_DEFAULT_PROVIDER = "ffmpeg"
_DEFAULT_FFMPEG = "ffmpeg"

#: Perceived loudness measured in LUFS (negative scale; -14 is the YouTube target).
_DEFAULT_LUFS = -14
_DEFAULT_SAMPLE_RATE = 48000
_DEFAULT_FORMAT = "wav"

_DEFAULT_REQUEST_TIMEOUT = 300.0
_DEFAULT_TIMEOUT = 600.0
_DEFAULT_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0
_RETRY_MAX_DELAY = 30.0


class AudioError(PipelineError):
    """Base class for every audio mixing provider failure."""

    code = "audio_error"


class AudioMixError(AudioError):
    """The mixing backend failed to produce a mastered track."""

    code = "audio_mix_error"

    def __init__(self, message: str, *, detail: Any | None = None, retryable: bool = False) -> None:
        super().__init__(message, detail=detail)
        self.retryable = retryable


class AudioTimeoutError(AudioError):
    """Mixing did not complete within the configured timeout."""

    code = "audio_timeout_error"


# ------------------------------------------------------------------ typed API -


class AudioMixRequest(BaseModel):
    """A provider-agnostic mastering request."""

    narration: str
    bgm: str | None = None
    sfx: str | None = None
    target_lufs: int = Field(_DEFAULT_LUFS, ge=-100, le=0)
    sample_rate: int = Field(_DEFAULT_SAMPLE_RATE, ge=1, le=768000)
    format: str = _DEFAULT_FORMAT


class AudioRender(BaseModel):
    """One finalized mastered audio file saved to disk."""

    file: str
    format: str
    sample_rate: int
    duration_seconds: float
    checksum: str
    target_lufs: int


# ------------------------------------------------------------------- builders -


def build_mix_filter(has_bgm: bool, has_sfx: bool, target_lufs: int, sample_rate: int) -> str:
    """Construct the FFmpeg filter graph for one mastering pass.

    Pipeline: narration (0) is split to drive a sidechain compressor against
    BGM (1) when present, then mixed with optional SFX (2), then loudness-
    normalized to ``target_lufs`` and resampled to ``sample_rate``.
    """
    parts = [
        f"[0:a]aresample={sample_rate}[voice0]",
        "[voice0]asplit=2[v_main][v_side]",
    ]
    if has_bgm:
        parts.append(
            f"[1:a]aresample={sample_rate}[bgm0]; "
            "[bgm0]volume=0.75[bgm_src]; "
            "[bgm_src][v_side]sidechaincompress=threshold=0.05:ratio=20:attack=10:release=600[bgm_duck]; "
            "[v_main][bgm_duck]amix=inputs=2:duration=first:normalize=0[stage_a]"
        )
    else:
        parts.append("[v_main]anull[stage_a]")
    if has_sfx:
        parts.append(
            f"[2:a]aresample={sample_rate}[sfx_raw]; "
            "[stage_a][sfx_raw]amix=inputs=2:duration=first:normalize=0[stage_b]"
        )
    else:
        parts.append("[stage_a]anull[stage_b]")
    parts.append(f"[stage_b]loudnorm=I={target_lufs}:TP=-1.5:LRA=11,aresample={sample_rate}[aout]")
    return "; ".join(parts)


def build_mix_command(
    command: list[str],
    *,
    narration: str,
    bgm: str | None = None,
    sfx: str | None = None,
    graph: str,
    output_format: str = "wav",
) -> list[str]:
    """Assemble the FFmpeg argv for one mastering pass.

    Audio is written to the process's stdout (``pipe:1``) so the backend can
    capture the mixed bytes without touching a temp file.
    """
    argv = list(command) + ["-y", "-hide_banner", "-loglevel", "error", "-i", narration]
    if bgm:
        argv += ["-i", bgm]
    if sfx:
        argv += ["-i", sfx]
    argv += [
        "-filter_complex",
        graph,
        "-map",
        "[aout]",
        "-f",
        output_format,
        "pipe:1",
    ]
    return argv


def _resolve_command(binary: str | list[str] | None) -> list[str]:
    if isinstance(binary, str):
        return shlex.split(binary)
    if binary is not None:
        return list(binary)
    return shlex.split(os.getenv(_ENV_FFMPEG) or _DEFAULT_FFMPEG)


# ------------------------------------------------------------------- backend --


class AudioMixer(ABC):
    """Transport seam for an audio mastering engine.

    Concrete backends (FFmpeg, a cloud mastering service, a local SDK) implement
    :meth:`mix` and return the mastered audio bytes; the provider layer adds
    retries, timeouts, and typed responses on top.
    """

    name: str = "base"

    @abstractmethod
    async def mix(self, request: AudioMixRequest) -> bytes:
        """Return the mastered audio bytes (WAV by default)."""

    async def close(self) -> None:
        """Release any resources owned by this backend."""


class FFmpegAudioMixer(AudioMixer):
    """Concrete backend that mixes audio through the ``ffmpeg`` CLI.

    The binary is configurable (a plain ``ffmpeg`` on ``PATH``, or any custom
    command prefix) and is validated to exist at construction, failing fast.
    """

    name = "ffmpeg"

    def __init__(
        self,
        *,
        binary: str | list[str] | None = None,
        request_timeout: float | None = None,
    ) -> None:
        self._command = _resolve_command(binary)
        first = self._command[0] if self._command else ""
        if not self._check_executable(first):
            raise ProviderNotConfiguredError(
                f"FFmpeg binary not found: {first!r}; set {_ENV_FFMPEG} or pass binary="
            )
        self._request_timeout = _first(request_timeout, None, _DEFAULT_REQUEST_TIMEOUT)
        self._logger = get_logger("pr1me.providers.audio.backend", binary=first)

    async def mix(self, request: AudioMixRequest) -> bytes:
        graph = build_mix_filter(
            request.bgm is not None,
            request.sfx is not None,
            request.target_lufs,
            request.sample_rate,
        )
        argv = build_mix_command(
            self._command,
            narration=request.narration,
            bgm=request.bgm,
            sfx=request.sfx,
            graph=graph,
            output_format=request.format,
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise AudioMixError(
                f"could not start audio mixing backend: {exc}",
                detail={"command": self._command},
                retryable=True,
            ) from exc
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._request_timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise AudioMixError(
                f"audio mixing backend did not finish within {self._request_timeout:g}s",
                detail={"command": self._command},
                retryable=True,
            ) from None
        if process.returncode != 0:
            message = stderr.decode("utf-8", errors="replace")
            raise AudioMixError(
                f"audio mixing backend exited with code {process.returncode}",
                detail={"stderr": message[-500:]},
                retryable=True,
            )
        if not stdout:
            raise AudioMixError("audio mixing backend returned empty output", retryable=True)
        self._logger.info(
            "event=audio.backend.completed",
            narration=request.narration,
            bytes=len(stdout),
        )
        return stdout

    async def close(self) -> None:
        return None

    @staticmethod
    def _check_executable(path: str) -> bool:
        if not path:
            return False
        candidate = Path(path)
        if candidate.is_file():
            return True
        return shutil.which(path) is not None


_AVAILABLE_BACKENDS: dict[str, type[AudioMixer]] = {"ffmpeg": FFmpegAudioMixer}


def build_audio_backend(provider: str | None = None) -> AudioMixer:
    """Instantiate the configured audio backend from ``PR1ME_AUDIO_PROVIDER``."""
    name = provider or os.getenv(_ENV_PROVIDER) or _DEFAULT_PROVIDER
    try:
        cls = _AVAILABLE_BACKENDS[name]
    except KeyError as exc:
        raise ProviderNotConfiguredError(
            f"audio provider {name!r} is not available; available: {sorted(_AVAILABLE_BACKENDS)}"
        ) from exc
    return cls()


# ------------------------------------------------------------------ provider --


class AudioProvider:
    """Async client for a configurable audio mastering backend.

    Configuration comes from explicit constructor arguments or the
    ``PR1ME_AUDIO_*`` environment variables. The actual mastering engine is
    injected as an :class:`AudioMixer` (never hardcoded here).
    """

    name = "audio"

    def __init__(
        self,
        *,
        backend: AudioMixer | None = None,
        target_lufs: int | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_base_delay: float | None = None,
        retry_max_delay: float | None = None,
    ) -> None:
        self._backend = backend if backend is not None else build_audio_backend()
        self._target_lufs = _first(target_lufs, _env_int(_ENV_LUFS), _DEFAULT_LUFS)
        self._sample_rate = _first(sample_rate, _env_int(_ENV_SAMPLE_RATE), _DEFAULT_SAMPLE_RATE)
        self._format = (format_ or _DEFAULT_FORMAT).lstrip(".")
        self._timeout = _first(timeout_seconds, _env_float(_ENV_TIMEOUT), _DEFAULT_TIMEOUT)
        self._max_retries = _first(max_retries, _env_int(_ENV_MAX_RETRIES), _DEFAULT_MAX_RETRIES)
        self._retry_base_delay = _first(retry_base_delay, None, _RETRY_BASE_DELAY)
        self._retry_max_delay = _first(retry_max_delay, None, _RETRY_MAX_DELAY)
        self._logger = get_logger(
            "pr1me.providers.audio",
            backend=self._backend.name,
            lufs=self._target_lufs,
            sample_rate=self._sample_rate,
        )

    # ------------------------------------------------------------ entry ----

    async def mix(
        self,
        narration: str | Path,
        *,
        output_dir: str | Path,
        bgm: str | Path | None = None,
        sfx: str | Path | None = None,
        target_lufs: int | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
    ) -> AudioRender:
        """Master ``narration`` (plus optional ``bgm``/``sfx``) into one file.

        :param narration: the narration audio to mount beneath the sidechain
            duck and loudness-normalize with the optional bed.
        :param output_dir: destination folder (created on demand).
        :raises AudioError: validation, backend, or timeout failures. Fail-fast:
            no partial result is ever returned.
        """
        request = AudioMixRequest(
            narration=str(narration),
            bgm=str(bgm) if bgm is not None else None,
            sfx=str(sfx) if sfx is not None else None,
            target_lufs=target_lufs if target_lufs is not None else self._target_lufs,
            sample_rate=sample_rate if sample_rate is not None else self._sample_rate,
            format=(format_ or self._format).lstrip("."),
        )
        await self._validate_inputs(request)
        self._logger.info(
            "event=audio.mix.submitted",
            narration=request.narration,
            bgm=request.bgm,
            sfx=request.sfx,
            lufs=request.target_lufs,
        )
        data = await self._retried_mix(request)
        render = await asyncio.to_thread(self._save, data, Path(output_dir), request)
        self._logger.info(
            "event=audio.mix.completed",
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
        """Identifier of the configured mixing backend (for provenance)."""
        return self._backend.name

    # ----------------------------------------------------------- internals --

    async def _validate_inputs(self, request: AudioMixRequest) -> None:
        def _check() -> None:
            for label, path in (
                ("narration", request.narration),
                ("bgm", request.bgm),
                ("sfx", request.sfx),
            ):
                if path is not None and not Path(path).is_file():
                    raise AudioMixError(f"audio mix input missing: {label} {path}", retryable=False)

        await asyncio.to_thread(_check)

    async def _retried_mix(self, request: AudioMixRequest) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return await asyncio.wait_for(self._backend.mix(request), timeout=self._timeout)
            except TimeoutError:
                last_error = AudioTimeoutError(
                    f"audio mixing did not complete within {self._timeout:g}s",
                    detail={"narration": request.narration},
                )
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason="timeout")
            except AudioMixError as exc:
                last_error = exc
                if not exc.retryable:
                    raise exc
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason=exc.message)
        if isinstance(last_error, AudioError):
            raise last_error
        raise AudioMixError(f"audio mixing failed: {last_error}")

    def _should_retry_attempt(self, attempt: int) -> bool:
        return attempt < self._max_retries

    async def _backoff(self, attempt: int, *, reason: str) -> None:
        delay = min(self._retry_base_delay * (2 ** (attempt - 1)), self._retry_max_delay)
        jittered = delay * (0.5 + random.random())
        self._logger.warning(
            "event=audio.retry",
            attempt=attempt,
            reason=reason,
            delay_ms=round(jittered * 1000, 1),
        )
        await asyncio.sleep(jittered)

    def _save(self, data: bytes, output_dir: Path, request: AudioMixRequest) -> AudioRender:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"master.{request.format}"
        target.write_bytes(data)
        duration, actual_rate = wav_duration(data)
        return AudioRender(
            file=str(target),
            format=request.format,
            sample_rate=actual_rate or request.sample_rate,
            duration_seconds=duration,
            checksum=hashlib.sha256(data).hexdigest(),
            target_lufs=request.target_lufs,
        )
