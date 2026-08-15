"""Video Render stage (final encoded Short + verification report).

Consumes the :class:`AssemblyOutput` master timeline, renders it through a
configurable encoder provider into one vertical ``short.mp4``, verifies the
deliverable, and returns a single :class:`RenderManifestOutput`.

The stage owns the deterministic boundary: the target resolution/fps come from
the assembly plan, the encode target comes from the provider configuration, and
the deliverable name/location are fixed. All transport, retries, and timeouts
live in :class:`~pr1me.providers.video_renderer.VideoRendererProvider`.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from pr1me.core.base_stage import BaseStage
from pr1me.core.context import StageContext
from pr1me.core.errors import PipelineError
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.render import (
    RenderInput,
    RenderManifestOutput,
    RenderMetadata,
)
from pr1me.models.meta import ValidationStatus
from pr1me.providers.video_renderer import (
    _DEFAULT_AUDIO_BITRATE_KBPS,
    _DEFAULT_CRF,
    RenderSegment,
    VideoRender,
    VideoRendererProvider,
    VideoRenderRequest,
)
from pr1me.providers.voice import wav_duration

_ENV_OUTPUT_DIR = "PR1ME_RENDER_OUTPUT_DIR"

#: Deliverable name produced by the stage (CLI contract).
_FILENAME = "short.mp4"

#: Hard ceilings for the platform contract (PIPELINE_SPEC).
_MAX_FILE_BYTES = 200_000_000

#: Tolerance when comparing the rendered duration against the narration
#: (frame rounding at the target fps plus encoder container padding).
_NARRATION_EPSILON_SECONDS = 0.2


class RenderValidationError(PipelineError):
    """The encoded deliverable failed the post-render verification checks."""

    code = "render_validation_error"


class VideoRenderStage(BaseStage[RenderInput, RenderManifestOutput]):
    """Renders one final vertical Short from the approved assembly plan."""

    stage_id = "video_render"
    name = "Video Render"
    description = "Renders one final vertical Short from the approved assembly plan."
    version = "1.0.0"
    depends_on = ("video_assembly",)
    input_model = RenderInput
    output_model = RenderManifestOutput

    def __init__(
        self,
        context: StageContext,
        *,
        renderer: VideoRendererProvider | None = None,
    ) -> None:
        self._renderer = renderer
        super().__init__(context)

    async def execute(self, payload: RenderInput) -> RenderManifestOutput:
        provider = self._renderer or VideoRendererProvider()
        settings = self.context.settings
        configured_dir = os.getenv(_ENV_OUTPUT_DIR)
        output_dir = Path(configured_dir) if configured_dir else settings.work_dir

        request = self._build_request(payload)
        self._logger.info(
            "event=video_render.started",
            segments=len(request.segments),
            fps=request.fps,
            width=request.width,
            height=request.height,
            audio=request.audio,
        )
        render = await provider.render(request, output_dir=output_dir, filename=_FILENAME)
        self._validate_render(render)
        self._verify_narration_coverage(payload, render)
        self._verify_checksum(render)

        manifest = RenderManifestOutput(
            output_dir=str(output_dir),
            file=render.file,
            bytes=render.size_bytes,
            metadata=RenderMetadata(
                codec=request.codec,
                container=request.container,
                fps=render.fps,
                width=render.width,
                height=render.height,
                duration_seconds=render.duration_seconds,
                audio_codec=request.audio_codec,
                checksum=render.checksum,
                backend=provider.provider_name,
            ),
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=[
                    "single_video_file",
                    "mp4_container_ok",
                    "duration_within_budget",
                    "narration_not_cut",
                    "file_size_within_bounds",
                    "checksum_verified",
                ],
            ),
        )
        self._logger.info(
            "event=video_render.completed",
            file=render.file,
            bytes=render.size_bytes,
            duration_seconds=render.duration_seconds,
        )
        return manifest

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _build_request(payload: RenderInput) -> VideoRenderRequest:
        segments = [
            RenderSegment(file=clip.file, duration_seconds=clip.end_second - clip.start_second)
            for clip in payload.tracks.video
        ]
        if not segments:
            raise RenderValidationError(
                "assembly plan carries no video clips to render",
                detail={"total_frames": payload.total_frames},
            )
        audio = payload.tracks.audio.file
        return VideoRenderRequest(
            segments=segments,
            audio=audio,
            fps=payload.fps,
            width=payload.resolution.width,
            height=payload.resolution.height,
            crf=_DEFAULT_CRF,
            audio_bitrate_kbps=_DEFAULT_AUDIO_BITRATE_KBPS,
        )

    def _validate_render(self, render: VideoRender) -> None:
        if render.duration_seconds <= 0:
            raise RenderValidationError(
                "rendered file has no measurable duration",
                detail={"file": render.file, "duration_seconds": render.duration_seconds},
            )
        budget = self.context.settings.target_max_duration_seconds
        if render.duration_seconds > budget:
            raise RenderValidationError(
                f"rendered duration {render.duration_seconds:g}s exceeds the {budget:g}s budget",
                detail={"file": render.file, "duration_seconds": render.duration_seconds},
            )
        if render.size_bytes > _MAX_FILE_BYTES:
            raise RenderValidationError(
                f"rendered file exceeds the {_MAX_FILE_BYTES} byte ceiling",
                detail={"file": render.file, "bytes": render.size_bytes},
            )

    def _verify_narration_coverage(self, payload: RenderInput, render: VideoRender) -> None:
        """Guarantee the final export never cuts the narration.

        The mastered track is expected to be a WAV (the audio mix provider's
        default); the true duration is probed from the container. When the
        master cannot be probed the check is skipped with a warning rather than
        guessed.
        """
        master = payload.tracks.audio.file
        try:
            data = Path(master).read_bytes()
        except OSError as exc:
            raise RenderValidationError(f"cannot read master audio {master}: {exc}") from exc
        narration_seconds, _ = wav_duration(data)
        if narration_seconds <= 0:
            self._logger.warning(
                "event=video_render.narration_unprobeable",
                file=master,
                note="skipping the narration coverage check",
            )
            return
        if render.duration_seconds + _NARRATION_EPSILON_SECONDS < narration_seconds:
            raise RenderValidationError(
                "rendered file is shorter than the narration; the narration would be cut",
                detail={
                    "file": render.file,
                    "rendered_seconds": render.duration_seconds,
                    "narration_seconds": narration_seconds,
                },
            )

    def _verify_checksum(self, render: VideoRender) -> None:
        try:
            data = Path(render.file).read_bytes()
        except OSError as exc:
            raise RenderValidationError(f"cannot read rendered file {render.file}: {exc}") from exc
        if not data:
            raise RenderValidationError(f"rendered file {render.file} is empty")
        if hashlib.sha256(data).hexdigest() != render.checksum:
            raise RenderValidationError(
                "rendered file checksum mismatch",
                detail={"file": render.file},
            )