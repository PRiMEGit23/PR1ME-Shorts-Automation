"""Tests for the Audio Mixing subsystem (mixing provider + stage)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import struct
import sys
from pathlib import Path
from typing import Any

import pytest

from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.errors import ProviderNotConfiguredError
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.contracts.audio import AudioManifestOutput
from pr1me.models.contracts.image import ImageManifestOutput
from pr1me.models.contracts.voice import VoiceAsset, VoiceManifestOutput, VoiceMetadata
from pr1me.pipeline.runner import PipelineRunner
from pr1me.providers.audio import (
    AudioMixer,
    AudioMixError,
    AudioMixRequest,
    AudioProvider,
    AudioTimeoutError,
    FFmpegAudioMixer,
    build_mix_command,
    build_mix_filter,
)
from pr1me.providers.voice import wav_duration
from pr1me.stages.audio_mix_stage import AudioMixStage

logger = logging.getLogger("test-audio")


def _wav_bytes(sample_rate: int = 48000, seconds: float = 0.05) -> bytes:
    channels = 1
    bits = 16
    block_align = channels * bits // 8
    data_size = int(seconds * sample_rate) * block_align
    byte_rate = sample_rate * block_align
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<HH", 1, channels)
        + struct.pack("<II", sample_rate, byte_rate)
        + struct.pack("<HH", block_align, bits)
        + b"data"
        + struct.pack("<I", data_size)
        + bytes(data_size)
    )


_FFMPEG_STUB = (
    "import struct, sys\n"
    "wav = (\n"
    "    b'RIFF' + struct.pack('<I', 36 + 2000) + b'WAVE'\n"
    "    + b'fmt ' + struct.pack('<I', 16) + struct.pack('<HH', 1, 1)\n"
    "    + struct.pack('<II', 48000, 96000) + struct.pack('<HH', 2, 16)\n"
    "    + b'data' + struct.pack('<I', 2000) + bytes(2000)\n"
    ")\n"
    "sys.stdout.buffer.write(wav)\n"
    "sys.stdout.buffer.flush()\n"
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "work", assets_dir=tmp_path / "assets")


def _context(tmp_path: Path, settings: Settings) -> StageContext:
    return StageContext(
        settings=settings,
        logger=logger,
        prompt_loader=PromptLoader(tmp_path / "prompts"),
    )


# ---------------------------------------------------------------- builders ---


def test_build_mix_filter_ducks_bgm_and_normalizes() -> None:
    graph = build_mix_filter(True, True, -14, 48000)
    assert "sidechaincompress=threshold=0.05:ratio=20" in graph
    assert "amix=inputs=2:duration=first:normalize=0" in graph
    assert "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]" in graph
    assert graph.endswith("[aout]")


def test_build_mix_filter_without_bed_has_no_sidechain() -> None:
    graph = build_mix_filter(False, True, -16, 44100)
    assert "sidechaincompress" not in graph
    assert "aresample=44100" in graph


def test_build_mix_command_includes_optional_inputs() -> None:
    argv = build_mix_command(
        ["ffmpeg"],
        narration="n.wav",
        bgm="b.mp3",
        sfx="s.wav",
        graph="[aout]",
    )
    assert argv[:2] == ["ffmpeg", "-y"]
    assert "-i" in argv
    assert argv.count("-i") == 3
    assert "-filter_complex" in argv
    assert argv[argv.index("-f") + 1] == "wav"
    assert argv[-1] == "pipe:1"


# ------------------------------------------------------------------ provider --


def _provider(
    backend: AudioMixer,
    *,
    max_retries: int = 1,
    retry_base_delay: float = 0.01,
    timeout_seconds: float | None = None,
) -> AudioProvider:
    return AudioProvider(
        backend=backend,
        max_retries=max_retries,
        retry_base_delay=retry_base_delay,
        timeout_seconds=timeout_seconds,
    )


class _FakeAudioMixer(AudioMixer):
    name = "fake"

    def __init__(self, *, failures: int = 0, fail_retryable: bool = False, sleep_s: float = 0.0) -> None:
        self.calls = 0
        self.failures = failures
        self.fail_retryable = fail_retryable
        self.sleep_s = sleep_s

    async def mix(self, request: AudioMixRequest) -> bytes:
        self.calls += 1
        if self.sleep_s:
            await asyncio.sleep(self.sleep_s)
        if self.calls <= self.failures:
            raise AudioMixError("transient backend failure", retryable=self.fail_retryable)
        return _wav_bytes()


def _write_narration(tmp_path: Path) -> Path:
    narration = tmp_path / "narration.wav"
    narration.write_bytes(_wav_bytes())
    return narration


def test_provider_mixes_and_saves_master(tmp_path: Path) -> None:
    narration = _write_narration(tmp_path)
    holder: list[Any] = []

    async def go() -> None:
        provider = _provider(_FakeAudioMixer())
        render = await provider.mix(narration, output_dir=tmp_path / "out", target_lufs=-14)
        assert render.duration_seconds > 0
        assert render.sample_rate == 48000
        assert render.target_lufs == -14
        holder.append(render)
        await provider.close()

    asyncio.run(go())
    path = Path(holder[0].file)
    assert path.name == "master.wav"
    assert path.is_file()
    assert path.read_bytes() == _wav_bytes()


def test_mix_retries_transient_failure(tmp_path: Path) -> None:
    narration = _write_narration(tmp_path)
    backend = _FakeAudioMixer(failures=1, fail_retryable=True)

    async def go() -> None:
        provider = _provider(backend, max_retries=3)
        render = await provider.mix(narration, output_dir=tmp_path / "out")
        assert render.checksum
        await provider.close()

    asyncio.run(go())
    assert backend.calls == 2


def test_mix_fails_fast_on_non_retryable(tmp_path: Path) -> None:
    narration = _write_narration(tmp_path)

    async def go() -> None:
        provider = _provider(_FakeAudioMixer(failures=1, fail_retryable=False), max_retries=3)
        with pytest.raises(AudioMixError, match="transient backend failure"):
            await provider.mix(narration, output_dir=tmp_path / "out")
        await provider.close()

    asyncio.run(go())


def test_missing_input_fails_fast(tmp_path: Path) -> None:
    async def go() -> None:
        provider = _provider(_FakeAudioMixer())
        with pytest.raises(AudioMixError, match="input missing"):
            await provider.mix(tmp_path / "missing.wav", output_dir=tmp_path / "out")
        await provider.close()

    asyncio.run(go())


def test_timeout_raises(tmp_path: Path) -> None:
    narration = _write_narration(tmp_path)

    async def go() -> None:
        provider = _provider(_FakeAudioMixer(sleep_s=5), timeout_seconds=0.05)
        with pytest.raises(AudioTimeoutError):
            await provider.mix(narration, output_dir=tmp_path / "out")
        await provider.close()

    asyncio.run(go())


def test_ffmpeg_missing_binary_fails_fast() -> None:
    with pytest.raises(ProviderNotConfiguredError, match="FFmpeg binary not found"):
        FFmpegAudioMixer(binary="definitely-not-a-ffmpeg-xyz")


def test_ffmpeg_backend_end_to_end(tmp_path: Path) -> None:
    stub = tmp_path / "ffmpeg_stub.py"
    stub.write_text(_FFMPEG_STUB, encoding="utf-8")
    narration = _write_narration(tmp_path)
    expected = _stub_bytes()
    renders: list[Any] = []

    async def go() -> None:
        backend = FFmpegAudioMixer(binary=f'"{sys.executable}" "{stub}"', request_timeout=30)
        provider = _provider(backend)
        render = await provider.mix(narration, output_dir=tmp_path / "out")
        assert render.duration_seconds > 0
        assert render.sample_rate == 48000
        renders.append(render)
        await provider.close()

    asyncio.run(go())
    path = Path(renders[0].file)
    assert path.read_bytes() == expected


def _stub_bytes() -> bytes:
    return (
        b"RIFF"
        + struct.pack("<I", 36 + 2000)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<HH", 1, 1)
        + struct.pack("<II", 48000, 96000)
        + struct.pack("<HH", 2, 16)
        + b"data"
        + struct.pack("<I", 2000)
        + bytes(2000)
    )


# ---------------------------------------------------------------- stage ------


class FakeAudioProvider(AudioProvider):
    """Records mix calls and returns a tiny WAV for every request."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return "fake"

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
    ) -> Any:
        dest = Path(output_dir)
        await asyncio.to_thread(dest.mkdir, parents=True, exist_ok=True)
        data = _wav_bytes()
        target = dest / f"master.{format_ or 'wav'}"
        await asyncio.to_thread(target.write_bytes, data)
        duration, rate = wav_duration(data)
        self.calls.append(
            {
                "narration": str(narration),
                "bgm": str(bgm) if bgm is not None else None,
                "sfx": str(sfx) if sfx is not None else None,
                "target_lufs": target_lufs,
                "sample_rate": sample_rate,
                "format": format_,
            }
        )
        from pr1me.providers.audio import AudioRender

        return AudioRender(
            file=str(target),
            format=format_ or "wav",
            sample_rate=rate,
            duration_seconds=duration,
            checksum=hashlib.sha256(data).hexdigest(),
            target_lufs=target_lufs or -14,
        )


def _voice_manifest(narration: str) -> VoiceManifestOutput:
    return VoiceManifestOutput(
        output_dir=str(Path(narration).parent),
        assets=[
            VoiceAsset(
                file=narration,
                bytes=0,
                checksum="a" * 64,
                metadata=VoiceMetadata(
                    text="demo",
                    voice="default",
                    sample_rate=22050,
                    format="wav",
                    duration_seconds=2.0,
                    provider="fake",
                    checksum="a" * 64,
                ),
            )
        ],
        total=1,
    )


def test_stage_mixes_narration_with_bgm_and_sfx(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.assets_dir.mkdir(parents=True, exist_ok=True)
    music = settings.assets_dir / "music"
    sfx_dir = settings.assets_dir / "sfx"
    music.mkdir()
    sfx_dir.mkdir()
    (music / "a.mp3").write_bytes(_wav_bytes())
    (sfx_dir / "b.wav").write_bytes(_wav_bytes())

    context = _context(tmp_path, settings)
    narration = tmp_path / "work" / "audio" / "narration.wav"
    narration.parent.mkdir(parents=True)
    narration.write_bytes(_wav_bytes())
    fake = FakeAudioProvider()
    stage = AudioMixStage(context=context, audio_provider=fake)

    async def go() -> None:
        payload = _voice_manifest(str(narration)).model_dump(mode="json")
        result: AudioManifestOutput = await stage.run(payload)
        assert result.total == 1
        assert result.validation.status.value == "ok"
        assert fake.calls[0]["narration"] == str(narration)
        assert fake.calls[0]["bgm"] == str(music / "a.mp3")
        assert fake.calls[0]["sfx"] == str(sfx_dir / "b.wav")
        assert result.assets[0].metadata.bgm_file == str(music / "a.mp3")

    asyncio.run(go())


def test_stage_mix_no_bgm_or_sfx(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    context = _context(tmp_path, settings)
    narration = tmp_path / "work" / "audio" / "narration.wav"
    narration.parent.mkdir(parents=True)
    narration.write_bytes(_wav_bytes())
    fake = FakeAudioProvider()
    stage = AudioMixStage(context=context, audio_provider=fake)

    async def go() -> None:
        payload = _voice_manifest(str(narration)).model_dump(mode="json")
        result: AudioManifestOutput = await stage.run(payload)
        assert result.assets[0].metadata.bgm_file is None
        assert result.assets[0].metadata.sfx_file is None

    asyncio.run(go())


def test_stage_fails_when_no_narration(tmp_path: Path) -> None:
    from pr1me.stages.audio_mix_stage import AudioMixValidationError

    settings = _settings(tmp_path)
    stage = AudioMixStage(context=_context(tmp_path, settings), audio_provider=FakeAudioProvider())

    async def go() -> None:
        with pytest.raises(AudioMixValidationError, match="no narration"):
            await stage.run({"assets": [], "images": []})

    asyncio.run(go())


# ------------------------------------------------------------- runner --------


def test_runner_includes_audio_mix_last(tmp_path: Path) -> None:
    from pr1me.core.base_stage import BaseStage
    from pr1me.models.contracts.base import StageInput, StageOutput

    settings = _settings(tmp_path)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    context = _context(tmp_path, settings)
    narration = settings.work_dir / "audio" / "narration.wav"
    narration.parent.mkdir(parents=True)
    narration.write_bytes(_wav_bytes())
    voice_manifest = _voice_manifest(str(narration))

    class VoiceInputStub(StageInput):
        model_config = {"extra": "ignore"}

    class VoiceOutputStub(StageOutput):
        model_config = {"extra": "ignore"}
        output_dir: str
        assets: list[Any] = []
        total: int = 1

    class ImageOutputStub(StageOutput):
        model_config = {"extra": "ignore"}
        output_dir: str

    class VoiceStub(BaseStage[VoiceInputStub, VoiceOutputStub]):
        stage_id = "voice_generation"
        name = "Voice Stub"
        depends_on: tuple = ()
        input_model = VoiceInputStub
        output_model = VoiceOutputStub

        async def execute(self, payload):  # noqa: ARG002
            return voice_manifest

    class ImageStub(BaseStage[VoiceInputStub, ImageOutputStub]):
        stage_id = "image_generation"
        name = "Image Stub"
        depends_on: tuple = ()
        input_model = VoiceInputStub
        output_model = ImageOutputStub

        async def execute(self, payload):  # noqa: ARG002
            return ImageManifestOutput(output_dir="", images=[], total=0)

    registry = StageRegistry(context=context)
    registry.register(VoiceStub(context=context))
    registry.register(ImageStub(context=context))
    registry.register(AudioMixStage(context=context, audio_provider=FakeAudioProvider()))
    runner = PipelineRunner(registry, context=context, artifact_dir=settings.work_dir)

    async def go() -> None:
        job_input = {"assets": [voice_manifest.assets[0].model_dump(mode="json")]}
        report = await runner.run(job_input, job_id="job-audio")
        assert report.run_status.value == "complete"
        assert [record.stage_id for record in report.stages] == [
            "voice_generation",
            "image_generation",
            "audio_mix",
        ]
        assert (settings.work_dir / "audio" / "master.wav").is_file()

    asyncio.run(go())
