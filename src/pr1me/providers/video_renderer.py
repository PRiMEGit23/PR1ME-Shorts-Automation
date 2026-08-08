"""Video rendering provider (configurable encoding backend).

Everything that turns an assembly timeline into final encoded bytes lives
here:

- :class:`VideoRenderer` -- the transport seam for an encoding engine
- :class:`FFmpegVideoRenderer` -- a concrete backend that drives a
  configurable ``ffmpeg`` binary (loop images + concat + mux the master audio)
- :class:`VideoRendererProvider` -- owns the retry policy, the per-call
  timeout, structured logging, file persistence, and typed response building

The provider is transport-only and concept-agnostic: it knows nothing about
manifests or assembly plans. The stage layer translates the plan into a
:class:`VideoRenderRequest` and decides where the deliverable lands. It
deliberately does **not** extend :class:`~pr1me.providers.base_provider
.BaseProvider`, which is the LLM completion interface; encoding is a different
capability.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
import shlex
import shutil
import struct
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pr1me.core.errors import PipelineError, ProviderNotConfiguredError
from pr1me.core.logging import get_logger
from pr1me.providers.voice import _env_float, _env_int, _first

_ENV_PROVIDER = "PR1ME_RENDER_PROVIDER"
_ENV_FFMPEG = "PR1ME_RENDER_FFMPEG_BIN"
_ENV_TIMEOUT = "PR1ME_RENDER_TIMEOUT_SECONDS"
_ENV_MAX_RETRIES = "PR1ME_RENDER_MAX_RETRIES"

_DEFAULT_PROVIDER = "ffmpeg"
_DEFAULT_FFMPEG = "ffmpeg"
_DEFAULT_CONTAINER = "mp4"
_DEFAULT_CODEC = "libx264"
_DEFAULT_PIXEL_FORMAT = "yuv420p"
_DEFAULT_CRF = 20
_DEFAULT_AUDIO_CODEC = "aac"
_DEFAULT_AUDIO_BITRATE_KBPS = 192

_DEFAULT_REQUEST_TIMEOUT = 600.0
_DEFAULT_TIMEOUT = 1200.0
_DEFAULT_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0
_RETRY_MAX_DELAY = 30.0

#: The MP4 brand box every ffmpeg-produced file carries.
_FTYP_MAGIC = b"ftyp"


class VideoRenderError(PipelineError):
    """Base class for every video rendering provider failure."""

    code = "video_render_error"


class VideoRenderFailure(VideoRenderError):
    """The encoding backend failed to produce a deliverable."""

    code = "video_render_failure"

    def __init__(self, message: str, *, detail: Any | None = None, retryable: bool = False) -> None:
        super().__init__(message, detail=detail)
        self.retryable = retryable


class VideoRenderTimeoutError(VideoRenderError):
    """Rendering did not complete within the configured timeout."""

    code = "video_render_timeout_error"


# ------------------------------------------------------------------ typed API -


class RenderSegment(BaseModel):
    """One image clip on the timeline (provider-agnostic)."""

    file: str = Field(..., min_length=1)
    duration_seconds: float = Field(..., gt=0.0)


class VideoRenderRequest(BaseModel):
    """A provider-agnostic encoding request for one vertical Short."""

    segments: list[RenderSegment] = Field(min_length=1)
    audio: str = Field(..., min_length=1)
    fps: int = Field(..., ge=1, le=240)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    codec: str = _DEFAULT_CODEC
    container: str = _DEFAULT_CONTAINER
    pixel_format: str = _DEFAULT_PIXEL_FORMAT
    crf: int = Field(_DEFAULT_CRF, ge=0, le=51)
    audio_codec: str = _DEFAULT_AUDIO_CODEC
    audio_bitrate_kbps: int = Field(_DEFAULT_AUDIO_BITRATE_KBPS, ge=16, le=1024)


class VideoRender(BaseModel):
    """One finalized encoded video file saved to disk."""

    file: str
    fps: int
    width: int
    height: int
    duration_seconds: float
    size_bytes: int
    checksum: str


# ------------------------------------------------------------------ utilities -


def _resolve_command(binary: str | list[str] | None) -> list[str]:
    if isinstance(binary, str):
        return shlex.split(binary)
    if binary is not None:
        return list(binary)
    return shlex.split(os.getenv(_ENV_FFMPEG) or _DEFAULT_FFMPEG)


def _iter_boxes(data: bytes) -> list[tuple[bytes, bytes]]:
    """Yield ``(box_type, box_bytes)`` for the top-level MP4 boxes."""
    boxes: list[tuple[bytes, bytes]] = []
    pos = 0
    while pos + 8 <= len(data):
        size = struct.unpack_from(">I", data, pos)[0]
        box_type = data[pos + 4 : pos + 8]
        header = 8
        if size == 1:
            if pos + 16 > len(data):
                break
            size = struct.unpack_from(">Q", data, pos + 8)[0]
            header = 16
        elif size == 0:
            size = len(data) - pos
        if size < header or pos + size > len(data):
            break
        boxes.append((box_type, data[pos : pos + size]))
        pos += size
    return boxes


def mp4_duration(data: bytes) -> float:
    """Return the duration (seconds) declared by the MP4 ``moov/mvhd`` box.

    Reads only the container header: zero for anything that is not a valid
    version-0 MP4. Returns ``0.0`` for unknown structures.
    """
    if len(data) < 12 or data[4:8] != _FTYP_MAGIC:
        return 0.0
    for box_type, box in _iter_boxes(data):
        if box_type != b"moov":
            continue
        for inner_type, inner in _iter_boxes(box[8:]):
            if inner_type != b"mvhd":
                continue
            payload = inner[8:]
            if len(payload) < 20 or payload[0] != 0:
                return 0.0
            timescale = struct.unpack_from(">I", payload, 12)[0]
            duration = struct.unpack_from(">I", payload, 16)[0]
            if timescale == 0:
                return 0.0
            return duration / timescale
    return 0.0


def build_render_command(command: list[str], request: VideoRenderRequest) -> list[str]:
    """Assemble the FFmpeg argv for one deterministic render pass.

    Every segment image is looped for its exact duration, concatenated in
    order, and muxed with the master audio. The encoded bytes are written to
    the process's stdout (``pipe:1``) so the backend can capture the file
    without touching a temp path.
    """
    argv = list(command) + ["-y", "-hide_banner", "-loglevel", "error"]
    for segment in request.segments:
        argv += ["-loop", "1", "-t", f"{segment.duration_seconds:g}", "-i", segment.file]
    argv += ["-i", request.audio]
    n = len(request.segments)
    labels = "".join(f"[{i}:v]" for i in range(n))
    argv += [
        "-filter_complex",
        f"{labels}concat=n={n}:v=1:a=0[vout]",
        "-map",
        "[vout]",
        "-map",
        f"{n}:a",
        "-c:v",
        request.codec,
        "-preset",
        "medium",
        "-crf",
        str(request.crf),
        "-pix_fmt",
        request.pixel_format,
        "-r",
        str(request.fps),
        "-c:a",
        request.audio_codec,
        "-b:a",
        f"{request.audio_bitrate_kbps}k",
        "-f",
        request.container,
        "pipe:1",
    ]
    return argv


# ------------------------------------------------------------------- backend --


class VideoRenderer(ABC):
    """Transport seam for a video encoding engine.

    Concrete backends (FFmpeg, a cloud encoder, a local SDK) implement
    :meth:`render` and return the encoded bytes (MP4 by default); the provider
    layer adds retries, timeouts, and typed responses on top.
    """

    name: str = "base"

    @abstractmethod
    async def render(self, request: VideoRenderRequest) -> bytes:
        """Return the encoded video bytes."""

    async def close(self) -> None:
        """Release any resources owned by this backend."""


class FFmpegVideoRenderer(VideoRenderer):
    """Concrete backend that encodes through the ``ffmpeg`` CLI.

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
        self._logger = get_logger("pr1me.providers.video_renderer.backend", binary=first)

    async def render(self, request: VideoRenderRequest) -> bytes:
        argv = build_render_command(self._command, request)
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise VideoRenderFailure(
                f"could not start encoding backend: {exc}",
                detail={"command": self._command},
                retryable=True,
            ) from exc
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._request_timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise VideoRenderFailure(
                f"encoding backend did not finish within {self._request_timeout:g}s",
                detail={"command": self._command},
                retryable=True,
            ) from None
        if process.returncode != 0:
            message = stderr.decode("utf-8", errors="replace")
            raise VideoRenderFailure(
                f"encoding backend exited with code {process.returncode}",
                detail={"stderr": message[-500:]},
                retryable=True,
            )
        if not stdout:
            raise VideoRenderFailure("encoding backend returned empty output", retryable=True)
        self._logger.info(
            "event=video_renderer.backend.completed",
            segments=len(request.segments),
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


_AVAILABLE_BACKENDS: dict[str, type[VideoRenderer]] = {"ffmpeg": FFmpegVideoRenderer}


def build_render_backend(provider: str | None = None) -> VideoRenderer:
    """Instantiate the configured render backend from ``PR1ME_RENDER_PROVIDER``."""
    name = provider or os.getenv(_ENV_PROVIDER) or _DEFAULT_PROVIDER
    try:
        cls = _AVAILABLE_BACKENDS[name]
    except KeyError as exc:
        raise ProviderNotConfiguredError(
            f"render provider {name!r} is not available; available: {sorted(_AVAILABLE_BACKENDS)}"
        ) from exc
    return cls()


# ------------------------------------------------------------------ provider --


class VideoRendererProvider:
    """Async client for a configurable video encoding backend.

    Configuration comes from explicit constructor arguments or the
    ``PR1ME_RENDER_*`` environment variables. The actual encoder is injected
    as a :class:`VideoRenderer` (never hardcoded here).
    """

    name = "video_renderer"

    def __init__(
        self,
        *,
        backend: VideoRenderer | None = None,
        codec: str | None = None,
        container: str | None = None,
        crf: int | None = None,
        audio_codec: str | None = None,
        audio_bitrate_kbps: int | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_base_delay: float | None = None,
        retry_max_delay: float | None = None,
    ) -> None:
        self._backend = backend if backend is not None else build_render_backend()
        self._codec = codec or _DEFAULT_CODEC
        self._container = (container or _DEFAULT_CONTAINER).lstrip(".")
        self._crf = crf or _DEFAULT_CRF
        self._audio_codec = audio_codec or _DEFAULT_AUDIO_CODEC
        self._audio_bitrate_kbps = audio_bitrate_kbps or _DEFAULT_AUDIO_BITRATE_KBPS
        self._timeout = _first(timeout_seconds, _env_float(_ENV_TIMEOUT), _DEFAULT_TIMEOUT)
        self._max_retries = _first(max_retries, _env_int(_ENV_MAX_RETRIES), _DEFAULT_MAX_RETRIES)
        self._retry_base_delay = _first(retry_base_delay, None, _RETRY_BASE_DELAY)
        self._retry_max_delay = _first(retry_max_delay, None, _RETRY_MAX_DELAY)
        self._logger = get_logger(
            "pr1me.providers.video_renderer",
            backend=self._backend.name,
            codec=self._codec,
            container=self._container,
        )

    # ------------------------------------------------------------ entry ----

    async def render(
        self,
        request: VideoRenderRequest,
        *,
        output_dir: str | Path,
        filename: str = "short.mp4",
    ) -> VideoRender:
        """Encode ``request`` into one deliverable saved under ``output_dir``.

        :param request: the provider-agnostic timeline encoding request.
        :param output_dir: destination folder (created on demand).
        :param filename: the deliverable name (``short.mp4`` by default).
        :raises VideoRenderError: validation, backend, or timeout failures.
            Fail-fast: no partial result is ever returned.
        """
        await self._validate_inputs(request)
        self._logger.info(
            "event=video_render.submitted",
            segments=len(request.segments),
            audio=request.audio,
            fps=request.fps,
            width=request.width,
            height=request.height,
        )
        data = await self._retried_render(request)
        render = await asyncio.to_thread(self._write, request, Path(output_dir), filename, data)
        self._logger.info(
            "event=video_render.completed",
            file=render.file,
            bytes=len(data),
            duration_seconds=render.duration_seconds,
            fps=render.fps,
        )
        return render

    async def close(self) -> None:
        """Release the resources owned by the configured backend."""
        await self._backend.close()

    @property
    def provider_name(self) -> str:
        """Identifier of the configured encoding backend (for provenance)."""
        return self._backend.name

    # ----------------------------------------------------------- internals --

    async def _validate_inputs(self, request: VideoRenderRequest) -> None:
        def _check() -> None:
            for label, path in (
                ("audio", request.audio),
                *[(f"segment[{index}]", segment.file) for index, segment in enumerate(request.segments)],
            ):
                if not Path(path).is_file():
                    raise VideoRenderFailure(
                        f"render input missing: {label} {path}",
                        retryable=False,
                    )

        await asyncio.to_thread(_check)

    async def _retried_render(self, request: VideoRenderRequest) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return await asyncio.wait_for(self._backend.render(request), timeout=self._timeout)
            except TimeoutError:
                last_error = VideoRenderTimeoutError(
                    f"video rendering did not complete within {self._timeout:g}s",
                    detail={"audio": request.audio},
                )
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason="timeout")
            except VideoRenderFailure as exc:
                last_error = exc
                if not exc.retryable:
                    raise exc
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason=exc.message)
        if isinstance(last_error, VideoRenderError):
            raise last_error
        raise VideoRenderFailure(f"video rendering failed: {last_error}")

    def _should_retry_attempt(self, attempt: int) -> bool:
        return attempt < self._max_retries

    async def _backoff(self, attempt: int, *, reason: str) -> None:
        delay = min(self._retry_base_delay * (2 ** (attempt - 1)), self._retry_max_delay)
        jittered = delay * (0.5 + random.random())
        self._logger.warning(
            "event=video_render.retry",
            attempt=attempt,
            reason=reason,
            delay_ms=round(jittered * 1000, 1),
        )
        await asyncio.sleep(jittered)

    @staticmethod
    def _write(
        request: VideoRenderRequest,
        output_dir: Path,
        filename: str,
        data: bytes,
    ) -> VideoRender:
        """Persist the encoded bytes and return the deliverable descriptor."""
        if len(data) < 12 or data[4:8] != _FTYP_MAGIC:
            raise VideoRenderFailure(
                "encoding backend produced a non-MP4 container",
                retryable=False,
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / filename
        target.write_bytes(data)
        return VideoRender(
            file=str(target),
            fps=request.fps,
            width=request.width,
            height=request.height,
            duration_seconds=mp4_duration(data),
            size_bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
        )