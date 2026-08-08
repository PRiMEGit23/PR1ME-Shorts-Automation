"""Voice Generation stage (narration synthesis).

Consumes the approved :class:`ScriptOutput`, converts the four narration blocks
into exactly one audio file through a configurable TTS backend, and returns a
single :class:`VoiceManifestOutput`.

The stage owns the deterministic boundary: the exact narration text (the four
script blocks preserved verbatim), the output location, and post-synthesis
validation. All transport, retries, and timeouts live in
:class:`~pr1me.providers.voice.VoiceProvider`.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from pr1me.core.base_stage import BaseStage
from pr1me.core.context import StageContext
from pr1me.core.errors import PipelineError
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.voice import (
    VoiceAsset,
    VoiceInput,
    VoiceManifestOutput,
    VoiceMetadata,
)
from pr1me.models.meta import ValidationStatus
from pr1me.providers.voice import VoiceProvider, VoiceRender

_ENV_OUTPUT_DIR = "PR1ME_VOICE_OUTPUT_DIR"


class VoiceGenerationError(PipelineError):
    """A generated narration failed the post-synthesis validation checks."""

    code = "voice_generation_error"


class VoiceGenerationStage(BaseStage[VoiceInput, VoiceManifestOutput]):
    """Synthesizes one narration audio file for the approved script."""

    stage_id = "voice_generation"
    name = "Voice Generation"
    description = "Synthesizes the narration audio for the approved script."
    version = "1.0.0"
    depends_on = ("image_generation", "script")
    input_model = VoiceInput
    output_model = VoiceManifestOutput

    def __init__(
        self,
        context: StageContext,
        *,
        voice_provider: VoiceProvider | None = None,
    ) -> None:
        self._voice = voice_provider
        super().__init__(context)

    async def execute(self, payload: VoiceInput) -> VoiceManifestOutput:
        provider = self._voice or VoiceProvider()
        settings = self.context.settings
        configured_dir = os.getenv(_ENV_OUTPUT_DIR)
        audio_dir = Path(configured_dir) if configured_dir else settings.work_dir / "audio"

        narration = payload.full_text()
        self._logger.info("event=voice_generation.started", chars=len(narration))

        render = await provider.synthesize(narration, output_dir=audio_dir)
        self._validate_render(render)

        asset = self._build_asset(render, narration, provider)
        manifest = VoiceManifestOutput(
            output_dir=str(audio_dir),
            assets=[asset],
            total=1,
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=[
                    "single_narration_file",
                    "script_preserved_exactly",
                    "valid_audio_file",
                ],
            ),
        )
        self._logger.info(
            "event=voice_generation.completed",
            file=asset.file,
            duration_seconds=asset.metadata.duration_seconds,
        )
        return manifest

    # ------------------------------------------------------------ internals --

    def _validate_render(self, render: VoiceRender) -> None:
        if render.format == "wav" and render.duration_seconds <= 0:
            raise VoiceGenerationError(
                "narration is not a valid audio file",
                detail={"file": render.file, "format": render.format},
            )

    def _build_asset(
        self,
        render: VoiceRender,
        narration: str,
        provider: VoiceProvider,
    ) -> VoiceAsset:
        checksum, size = self._inspect(render.file)
        if checksum != render.checksum:
            raise VoiceGenerationError(
                "narration checksum mismatch",
                detail={"file": render.file},
            )
        metadata = VoiceMetadata(
            text=narration,
            voice=render.voice,
            sample_rate=render.sample_rate,
            format=render.format,
            duration_seconds=render.duration_seconds,
            provider=provider.provider_name,
            checksum=checksum,
        )
        return VoiceAsset(
            file=render.file,
            bytes=size,
            checksum=checksum,
            metadata=metadata,
        )

    def _inspect(self, path: str) -> tuple[str, int]:
        """Read the saved narration and return checksum + size."""
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            raise VoiceGenerationError(f"cannot read narration {path}: {exc}") from exc
        if not data:
            raise VoiceGenerationError(f"narration {path} is empty")
        return hashlib.sha256(data).hexdigest(), len(data)
