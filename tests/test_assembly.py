"""Tests for the Video Assembly subsystem (master timeline / EDL builder)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.contracts.assembly import AssemblyOutput, VideoClip
from pr1me.models.contracts.audio import AudioAsset, AudioManifestOutput, AudioMetadata
from pr1me.models.contracts.image import (
    ImageAsset,
    ImageManifestOutput,
    ImageMetadata,
    ImageSamplerSettings,
)
from pr1me.models.contracts.motion import (
    MotionGraphicsOutput,
    MotionOverlay,
    MotionOverlayStyle,
    MotionStyleUsed,
)
from pr1me.models.contracts.voice import VoiceManifestOutput
from pr1me.pipeline.runner import PipelineRunner
from pr1me.stages.video_assembly_stage import AssemblyValidationError, VideoAssemblyStage

logger = logging.getLogger("test-video-assembly")

_FPS = 30

#: A tiny body is enough: the stage only checks file existence.
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_WAV = b"RIFF" + b"\x00" * 8 + b"WAVE" + b"\x00" * 40

_OVERLAY_STYLE = {"font": "Inter_Bold", "size_px": 96, "color": "#FFFFFF", "accent": "#00E5FF"}


def _image(tmp_path: Path, shot_id: int, start: float, end: float) -> ImageAsset:
    path = tmp_path / f"shot_{shot_id:03d}.png"
    path.write_bytes(_PNG)
    return ImageAsset(
        shot_id=shot_id,
        file=str(path),
        width=1080,
        height=1920,
        checksum="image-checksum",
        metadata=ImageMetadata(
            shot_id=shot_id,
            block="hook",
            start_second=start,
            end_second=end,
            width=1080,
            height=1920,
            positive_prompt="prompt",
            negative_prompt="negative",
            sampler_settings=ImageSamplerSettings(
                steps=28, cfg=7.0, sampler="euler_a", scheduler="karras", seed=1
            ),
            render_priority="Balanced",
            workflow="mock",
            comfyui_prompt_id="mock-prompt-1",
        ),
    )


def _audio_assets(tmp_path: Path, duration: float = 12.0) -> AudioAsset:
    master = tmp_path / "master.wav"
    master.write_bytes(_WAV)
    narration = tmp_path / "narration.wav"
    narration.write_bytes(_WAV)
    return AudioAsset(
        file=str(master),
        bytes=len(_WAV),
        sample_rate=48000,
        duration_seconds=duration,
        checksum="audio-checksum",
        metadata=AudioMetadata(
            narration_file=str(narration),
            bgm_file=None,
            sfx_file=None,
            target_lufs=-14,
            target_sample_rate=48000,
            duration_seconds=duration,
            backend="ffmpeg",
            checksum="audio-checksum",
        ),
    )


def _overlay() -> MotionOverlay:
    return MotionOverlay(
        id=1,
        text="WHY DOES THE",
        start_second=1.0,
        end_second=5.0,
        duration_seconds=4.0,
        pos_x=120.0,
        pos_y=120.0,
        style=MotionOverlayStyle(**_OVERLAY_STYLE),
    )


def _input_payload(tmp_path: Path) -> dict:
    return {
        "images": [
            _image(tmp_path, 1, 0.0, 6.0).model_dump(mode="json"),
            _image(tmp_path, 2, 6.0, 12.0).model_dump(mode="json"),
        ],
        "assets": [_audio_assets(tmp_path).model_dump(mode="json")],
        "overlays": [_overlay().model_dump(mode="json")],
        "ignored_extra_field": "must not break input validation",
    }


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "work")


def _context(tmp_path: Path, settings: Settings) -> StageContext:
    return StageContext(
        settings=settings,
        logger=logger,
        prompt_loader=PromptLoader(tmp_path / "prompts"),
    )


def _stage(tmp_path: Path) -> VideoAssemblyStage:
    return VideoAssemblyStage(context=_context(tmp_path, _settings(tmp_path)))


# --------------------------------------------------------------- stage ------


def test_stage_builds_master_timeline_from_manifests(tmp_path: Path) -> None:
    stage = _stage(tmp_path)

    async def go() -> None:
        result: AssemblyOutput = await stage.run(_input_payload(tmp_path))
        assert result.total_frames == 12 * _FPS
        assert result.fps == _FPS
        assert result.validation.status.value == "ok"
        assert [clip.shot_id for clip in result.tracks.video] == [1, 2]
        assert result.tracks.video[0].start_frame == 0
        assert result.tracks.video[0].end_frame == 6 * _FPS
        assert result.tracks.video[0].file == str(tmp_path / "shot_001.png")
        assert result.tracks.voice.start_frame == 0
        assert result.tracks.voice.file == str(tmp_path / "narration.wav")
        assert result.tracks.audio.file == str(tmp_path / "master.wav")
        assert result.tracks.audio.duck_during_voice is False
        assert len(result.cut_list) == 1
        assert result.cut_list[0].cut_at_frame == 6 * _FPS
        assert result.cut_list[0].from_shot == 1
        assert result.cut_list[0].to_shot == 2
        assert [f.kind for f in result.files] == ["video", "video", "voice", "audio"]

    asyncio.run(go())


def test_stage_pins_overlays_to_their_shot(tmp_path: Path) -> None:
    stage = _stage(tmp_path)

    async def go() -> None:
        result: AssemblyOutput = await stage.run(_input_payload(tmp_path))
        assert len(result.tracks.overlays) == 1
        overlay = result.tracks.overlays[0]
        assert overlay.track_index == 0
        assert overlay.text == "WHY DOES THE"
        assert overlay.start_frame == 1 * _FPS
        assert overlay.end_frame == 5 * _FPS
        assert overlay.style.font == "Inter_Bold"

    asyncio.run(go())


def test_stage_fails_without_images(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    payload = _input_payload(tmp_path)
    payload["images"] = []

    async def go() -> None:
        with pytest.raises(AssemblyValidationError, match="no rendered images"):
            await stage.run(payload)

    asyncio.run(go())


def test_stage_fails_when_timeline_has_a_gap(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    payload = _input_payload(tmp_path)
    payload["images"] = [
        _image(tmp_path, 1, 0.0, 6.0).model_dump(mode="json"),
        _image(tmp_path, 2, 7.0, 12.0).model_dump(mode="json"),
    ]

    async def go() -> None:
        with pytest.raises(AssemblyValidationError, match="gap or overlap"):
            await stage.run(payload)

    asyncio.run(go())


def test_stage_fails_when_order_is_not_strictly_increasing(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    payload = _input_payload(tmp_path)
    payload["images"] = [
        _image(tmp_path, 2, 0.0, 6.0).model_dump(mode="json"),
        _image(tmp_path, 1, 6.0, 12.0).model_dump(mode="json"),
    ]

    async def go() -> None:
        with pytest.raises(AssemblyValidationError, match="ascending shot order"):
            await stage.run(payload)

    asyncio.run(go())


def test_stage_fails_without_mastered_audio(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    payload = _input_payload(tmp_path)
    payload["assets"] = []

    async def go() -> None:
        with pytest.raises(AssemblyValidationError, match="no mastered track"):
            await stage.run(payload)

    asyncio.run(go())


def test_stage_fails_when_referenced_image_is_missing(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    payload = _input_payload(tmp_path)
    payload["images"] = [_image(tmp_path, 9, 0.0, 6.0).model_dump(mode="json")]
    Path(payload["images"][0]["file"]).unlink()

    async def go() -> None:
        with pytest.raises(AssemblyValidationError, match="image file does not exist"):
            await stage.run(payload)

    asyncio.run(go())


def test_stage_fails_when_overlay_straddles_a_cut(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    payload = _input_payload(tmp_path)
    payload["overlays"] = [
        MotionOverlay(
            id=99,
            text="SPANS THE CUT",
            start_second=5.0,
            end_second=7.0,
            duration_seconds=2.0,
            pos_x=120.0,
            pos_y=120.0,
            style=MotionOverlayStyle(**_OVERLAY_STYLE),
        ).model_dump(mode="json")
    ]

    async def go() -> None:
        with pytest.raises(AssemblyValidationError, match="straddles a shot boundary"):
            await stage.run(payload)

    asyncio.run(go())


# ------------------------------------------------------------- runner --------


def test_runner_writes_assembly_after_its_dependencies(tmp_path: Path) -> None:
    from pr1me.core.base_stage import BaseStage
    from pr1me.models.contracts.base import StageInput

    settings = _settings(tmp_path)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    context = _context(tmp_path, settings)

    class StubInput(StageInput):
        model_config = {"extra": "ignore"}
        images: list[ImageAsset] = []
        overlays: list[MotionOverlay] = []
        assets: list[AudioAsset] = []

    class ImageStub(BaseStage[StubInput, ImageManifestOutput]):
        stage_id = "image_generation"
        name = "Image Stub"
        depends_on: tuple = ()
        input_model = StubInput
        output_model = ImageManifestOutput

        async def execute(self, payload: StubInput) -> ImageManifestOutput:
            return ImageManifestOutput(
                output_dir=str(tmp_path),
                images=payload.images,
                total=len(payload.images),
            )

    class VoicelessStub(BaseStage[StubInput, VoiceManifestOutput]):
        stage_id = "voice_generation"
        name = "Voice Stub"
        depends_on: tuple = ()
        input_model = StubInput
        output_model = VoiceManifestOutput

        async def execute(self, payload: StubInput) -> VoiceManifestOutput:
            return VoiceManifestOutput(output_dir=str(tmp_path), assets=[], total=0)

    class AudioStub(BaseStage[StubInput, AudioManifestOutput]):
        stage_id = "audio_mix"
        name = "Audio Stub"
        depends_on: tuple = ()
        input_model = StubInput
        output_model = AudioManifestOutput

        async def execute(self, payload: StubInput) -> AudioManifestOutput:
            return AudioManifestOutput(
                output_dir=str(tmp_path),
                assets=payload.assets,
                total=len(payload.assets),
            )

    class MotionStub(BaseStage[StubInput, MotionGraphicsOutput]):
        stage_id = "motion_graphics"
        name = "Motion Stub"
        depends_on: tuple = ()
        input_model = StubInput
        output_model = MotionGraphicsOutput

        async def execute(self, payload: StubInput) -> MotionGraphicsOutput:
            return MotionGraphicsOutput(
                overlays=payload.overlays,
                total_overlays=len(payload.overlays),
                style_used=MotionStyleUsed(
                    font="Inter_Bold",
                    size_px=96,
                    color="#FFFFFF",
                    safe_margin_px=120,
                ),
            )

    async def go() -> None:
        registry = StageRegistry(context=context)
        registry.register(ImageStub(context=context))
        registry.register(VoicelessStub(context=context))
        registry.register(AudioStub(context=context))
        registry.register(MotionStub(context=context))
        registry.register(VideoAssemblyStage(context=context))
        runner = PipelineRunner(registry, context=context, artifact_dir=settings.work_dir)
        report = await runner.run(_input_payload(tmp_path), job_id="job-assembly")
        assert report.run_status.value == "complete"
        assert [record.stage_id for record in report.stages] == [
            "image_generation",
            "voice_generation",
            "audio_mix",
            "motion_graphics",
            "video_assembly",
        ]
        artifact = json.loads(
            (settings.work_dir / "job-assembly_video_assembly.json").read_text(encoding="utf-8")
        )
        assert artifact["total_frames"] == 12 * _FPS
        assert artifact["validation"]["status"] == "ok"

    asyncio.run(go())


# ------------------------------------------------------------ contract -----


def test_video_clip_contract_rejects_zero_frame_span() -> None:
    with pytest.raises(ValueError):
        VideoClip(
            shot_id=1,
            file="shot_001.png",
            start_frame=10,
            end_frame=10,
            start_second=0.0,
            end_second=6.0,
            transition="cut",
        )