"""Audio Mixing stage (mastered audio track).

Consumes the narration produced by the voice stage, loads the optional BGM and
SFX, ducks the BGM beneath the narration, normalizes the master, and returns a
single :class:`AudioManifestOutput`.

The stage owns the deterministic boundary: which BGM/SFX files are optional,
the output location, and the post-mix validation. All transport, retries, and
timeouts live in :class:`~pr1me.providers.audio.AudioProvider`.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

from pr1me.core.base_stage import BaseStage
from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.errors import PipelineError
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.audio import (
    AudioAsset,
    AudioManifestOutput,
    AudioMetadata,
    AudioMixInput,
)
from pr1me.models.meta import ValidationStatus
from pr1me.providers.audio import AudioProvider, AudioRender

_ENV_OUTPUT_DIR = "PR1ME_AUDIO_OUTPUT_DIR"
_ENV_BGM_DIR = "PR1ME_AUDIO_BGM_DIR"
_ENV_SFX_DIR = "PR1ME_AUDIO_SFX_DIR"

#: Extensions considered when discovering the optional BGM/SFX beds.
_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".opus"}


class AudioMixValidationError(PipelineError):
    """A generated master failed the post-mix validation checks."""

    code = "audio_mix_validation_error"


class AudioMixStage(BaseStage[AudioMixInput, AudioManifestOutput]):
    """Mixes narration, optional BGM/SFX, and masters one audio track."""

    stage_id = "audio_mix"
    name = "Audio Mixing"
    description = "Mixes narration, music, and sound effects into one mastered track."
    version = "1.0.0"
    depends_on = ("voice_generation", "image_generation")
    input_model = AudioMixInput
    output_model = AudioManifestOutput

    def __init__(
        self,
        context: StageContext,
        *,
        audio_provider: AudioProvider | None = None,
    ) -> None:
        self._audio = audio_provider
        super().__init__(context)

    async def execute(self, payload: AudioMixInput) -> AudioManifestOutput:
        provider = self._audio or AudioProvider()
        settings = self.context.settings
        configured_dir = os.getenv(_ENV_OUTPUT_DIR)
        audio_dir = Path(configured_dir) if configured_dir else settings.work_dir / "audio"
        await asyncio.to_thread(_ensure_dir, audio_dir)

        narration = self._resolve_narration(payload)
        bgm = await asyncio.to_thread(_pick_audio, self._bgm_dir(settings))
        sfx = await asyncio.to_thread(_pick_audio, self._sfx_dir(settings))

        self._logger.info(
            "event=audio_mix.started",
            narration=narration,
            bgm=bgm,
            sfx=sfx,
            audio_dir=str(audio_dir),
        )
        render = await provider.mix(narration, output_dir=audio_dir, bgm=bgm, sfx=sfx)
        self._validate_render(render)

        asset = self._build_asset(render, narration, bgm, sfx, provider)
        manifest = AudioManifestOutput(
            output_dir=str(audio_dir),
            assets=[asset],
            total=1,
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=[
                    "single_master_file",
                    "narration_preserved",
                    "valid_audio_file",
                ],
            ),
        )
        self._logger.info(
            "event=audio_mix.completed",
            file=asset.file,
            duration_seconds=asset.metadata.duration_seconds,
            bgm=bgm,
            sfx=sfx,
        )
        return manifest

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _bgm_dir(settings: Settings) -> Path:
        configured = os.getenv(_ENV_BGM_DIR)
        if configured:
            return Path(configured)
        return settings.assets_dir / "music"

    @staticmethod
    def _sfx_dir(settings: Settings) -> Path:
        configured = os.getenv(_ENV_SFX_DIR)
        if configured:
            return Path(configured)
        return settings.assets_dir / "sfx"

    def _resolve_narration(self, payload: AudioMixInput) -> str:
        if not payload.assets:
            raise AudioMixValidationError(
                "voice manifest carries no narration asset to mix",
                detail={"image_total": len(payload.images)},
            )
        return payload.assets[0].file

    def _validate_render(self, render: AudioRender) -> None:
        if render.format == "wav" and render.duration_seconds <= 0:
            raise AudioMixValidationError(
                "mastered audio is not a valid wav file",
                detail={"file": render.file, "format": render.format},
            )

    def _build_asset(
        self,
        render: AudioRender,
        narration: str,
        bgm: str | None,
        sfx: str | None,
        provider: AudioProvider,
    ) -> AudioAsset:
        checksum, size = self._inspect(render.file)
        if checksum != render.checksum:
            raise AudioMixValidationError("master checksum mismatch", detail={"file": render.file}) from None
        metadata = AudioMetadata(
            narration_file=narration,
            bgm_file=bgm,
            sfx_file=sfx,
            target_lufs=render.target_lufs,
            target_sample_rate=render.sample_rate,
            duration_seconds=render.duration_seconds,
            backend=provider.provider_name,
            checksum=checksum,
        )
        return AudioAsset(
            file=render.file,
            bytes=size,
            sample_rate=render.sample_rate,
            duration_seconds=render.duration_seconds,
            checksum=checksum,
            metadata=metadata,
        )

    def _inspect(self, path: str) -> tuple[str, int]:
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            raise AudioMixValidationError(f"cannot read master {path}: {exc}") from exc
        if not data:
            raise AudioMixValidationError(f"master {path} is empty")
        return hashlib.sha256(data).hexdigest(), len(data)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _pick_audio(directory: Path) -> str | None:
    """Return the first (deterministically ordered) audio file in ``directory``."""
    if not directory.is_dir():
        return None
    candidates = sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in _AUDIO_EXTENSIONS
    )
    return str(candidates[0]) if candidates else None
