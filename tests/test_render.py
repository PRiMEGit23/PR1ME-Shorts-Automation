"""Tests for the Video Render subsystem (encoder provider + stage)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import struct
import sys
from pathlib import Path

import pytest

from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.common import Resolution
from pr1me.models.contracts.assembly import (
    AssemblyOutput,
    AssemblyTracks,
    AudioTrack,
    VideoClip,
    VoiceTrack,
)
from pr1me.models.contracts.render import RenderManifestOutput, RenderMetadata
from pr1me.pipeline.runner import PipelineRunner
from pr1me.providers.video_renderer import (
    FFmpegVideoRenderer,
    RenderSegment,
    VideoRender,
    VideoRenderer,
    VideoRendererProvider,
    VideoRenderError,
    VideoRenderFailure,
    VideoRenderRequest,
    VideoRenderTimeoutError,
    build_render_command,
    mp4_duration,
)
from pr1me.stages.video_render_stage import RenderValidationError, VideoRenderStage

logger = logging.getLogger("test-video-render")

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_WAV = b"RIFF" + b"\x00" * 8 + b"WAVE" + b"\x00" * 40


def _mp4_bytes(duration: float = 1.0) -> bytes:
    """A minimal valid MP4: ftyp + moov/mvhd with ``duration`` seconds."""
    mvhd = (
        b"\x00\x00\x00\x00"
        + struct.pack(">II", 0, 0)
        + struct.pack(">II", 1000, int(duration * 1000))
        + struct.pack(">I", 0x00010000)
        + struct.pack(">H", 0x0100)
        + b"\x00" * 10
        + b"\x00" * 36
        + b"\x00" * 24
        + struct.pack(">I", 2)
    )
    ftyp = struct.pack(">I", 8 + 20) + b"ftyp" + b"isom" + struct.pack(">I", 0x200) + b"isomiso2mp41"
    mvhd_box = struct.pack(">I", 8 + len(mvhd)) + b"mvhd" + mvhd
    moov = struct.pack(">I", 8 + len(mvhd_box)) + b"moov" + mvhd_box
    return ftyp + moov


def _assets(tmp_path: Path) -> tuple[Path, Path]:
    image = tmp_path / "shot_001.png"
    image.write_bytes(_PNG)
    audio = tmp_path / "master.wav"
    audio.write_bytes(_WAV)
    return image, audio


def _assembly(tmp_path: Path) -> AssemblyOutput:
    image, audio = _assets(tmp_path)
    return AssemblyOutput(
        total_frames=6 * 30,
        fps=30,
        resolution=Resolution(width=1080, height=1920),
        tracks=AssemblyTracks(
            video=[
                VideoClip(
                    shot_id=1,
                    file=str(image),
                    start_frame=0,
                    end_frame=6 * 30,
                    start_second=0.0,
                    end_second=6.0,
                    transition="cut",
                )
            ],
            voice=VoiceTrack(file=str(audio), start_frame=0, end_frame=6 * 30, volume=1.0),
            audio=AudioTrack(
                file=str(audio),
                start_frame=0,
                end_frame=6 * 30,
                volume=1.0,
                duck_during_voice=False,
            ),
            overlays=[],
        ),
        files=[],
        cut_list=[],
    )


def _request(tmp_path: Path) -> VideoRenderRequest:
    image, audio = _assets(tmp_path)
    return VideoRenderRequest(
        segments=[RenderSegment(file=str(image), duration_seconds=6.0)],
        audio=str(audio),
        fps=30,
        width=1080,
        height=1920,
    )


def _payload(tmp_path: Path) -> dict:
    return {**_assembly(tmp_path).model_dump(mode="json"), "ignored_extra": 1}


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "work")


def _context(tmp_path: Path, settings: Settings) -> StageContext:
    return StageContext(
        settings=settings,
        logger=logger,
        prompt_loader=PromptLoader(tmp_path / "prompts"),
    )


# ------------------------------------------------------------ provider API ---


def test_mp4_duration_reads_mvhd() -> None:
    assert mp4_duration(_mp4_bytes(2.5)) == pytest.approx(2.5)
    assert mp4_duration(b"nope") == 0.0
    assert mp4_duration(_mp4_bytes()[:12]) == 0.0
    assert mp4_duration(b"RIFF" + b"\x00" * 40) == 0.0


def test_build_render_command_structure(tmp_path: Path) -> None:
    request = _request(tmp_path)
    argv = build_render_command(["ffmpeg"], request)
    assert argv[:2] == ["ffmpeg", "-y"]
    assert argv.count("-i") == 2
    assert argv[argv.index("-f") + 1] == "mp4"
    assert argv[-1] == "pipe:1"
    graph = argv[argv.index("-filter_complex") + 1]
    assert graph == "[0:v]concat=n=1:v=1:a=0[vout]"
    assert argv[argv.index("-r") + 1] == "30"
    assert argv[argv.index("-crf") + 1] == "20"


# ------------------------------------------------------------------ provider --


class _FakeVideoRenderer(VideoRenderer):
    """Recording backend seam with configurable failure modes."""

    name = "fake"

    def __init__(self, *, fail_first: int = 0, timeout_every: bool = False, garbage: bool = False) -> None:
        self.calls: list[VideoRenderRequest] = []
        self.failures_left = fail_first
        self.timeout_every = timeout_every
        self.garbage = garbage

    async def render(self, request: VideoRenderRequest) -> bytes:
        self.calls.append(request)
        if self.failures_left > 0:
            self.failures_left -= 1
            raise VideoRenderFailure("boom", retryable=True)
        if self.timeout_every:
            raise TimeoutError()
        if self.garbage:
            return b"not an mp4"
        return _mp4_bytes(2.5)

    async def close(self) -> None:
        return None


def test_provider_persists_encoded_mp4(tmp_path: Path) -> None:
    backend = _FakeVideoRenderer()
    provider = VideoRendererProvider(backend=backend, max_retries=1)
    out = tmp_path / "out"
    render = asyncio.run(provider.render(_request(tmp_path), output_dir=out, filename="short.mp4"))
    target = out / "short.mp4"
    data = target.read_bytes()
    assert data[4:8] == b"ftyp"
    assert render.file == str(target)
    assert render.duration_seconds == pytest.approx(2.5)
    assert render.size_bytes == len(data)
    assert render.checksum == hashlib.sha256(data).hexdigest()


def test_provider_retries_then_succeeds(tmp_path: Path) -> None:
    backend = _FakeVideoRenderer(fail_first=1)
    provider = VideoRendererProvider(
        backend=backend,
        max_retries=3,
        retry_base_delay=0.01,
        retry_max_delay=0.02,
    )
    render = asyncio.run(provider.render(_request(tmp_path), output_dir=tmp_path / "out"))
    assert render.duration_seconds == pytest.approx(2.5)
    assert len(backend.calls) == 2


def test_provider_gives_up_after_retries(tmp_path: Path) -> None:
    backend = _FakeVideoRenderer(fail_first=2)
    provider = VideoRendererProvider(
        backend=backend,
        max_retries=2,
        retry_base_delay=0.01,
        retry_max_delay=0.02,
    )
    with pytest.raises(VideoRenderFailure, match="boom"):
        asyncio.run(provider.render(_request(tmp_path), output_dir=tmp_path / "out"))
    assert len(backend.calls) == 2


def test_provider_raises_timeout_when_exhausted(tmp_path: Path) -> None:
    backend = _FakeVideoRenderer(timeout_every=True)
    provider = VideoRendererProvider(
        backend=backend,
        max_retries=1,
        retry_base_delay=0.01,
        retry_max_delay=0.02,
        timeout_seconds=0.1,
    )
    with pytest.raises(VideoRenderTimeoutError):
        asyncio.run(provider.render(_request(tmp_path), output_dir=tmp_path / "out"))


def test_provider_rejects_non_mp4_container(tmp_path: Path) -> None:
    backend = _FakeVideoRenderer(garbage=True)
    provider = VideoRendererProvider(backend=backend, max_retries=1)
    with pytest.raises(VideoRenderError, match="non-MP4"):
        asyncio.run(provider.render(_request(tmp_path), output_dir=tmp_path / "out"))


def test_provider_fails_fast_on_missing_input(tmp_path: Path) -> None:
    image, _audio = _assets(tmp_path)
    request = VideoRenderRequest(
        segments=[RenderSegment(file=str(image), duration_seconds=6.0)],
        audio=str(tmp_path / "missing.wav"),
        fps=30,
        width=1080,
        height=1920,
    )
    backend = _FakeVideoRenderer()
    provider = VideoRendererProvider(backend=backend, max_retries=2)
    with pytest.raises(VideoRenderFailure, match="input missing"):
        asyncio.run(provider.render(request, output_dir=tmp_path / "out"))
    assert backend.calls == []


def test_real_ffmpeg_backend_renders(tmp_path: Path) -> None:
    stub = tmp_path / "ffmpeg_stub.py"
    stub.write_text(
        "import struct, sys\n"
        "def box(t, payload):\n"
        "    return struct.pack('>I', 8 + len(payload)) + t.encode() + payload\n"
        "mvhd = box('mvhd', b'\\x00' * 4 + struct.pack('>II', 0, 0)\n"
        "    + struct.pack('>II', 1000, 2500) + struct.pack('>I', 0x00010000)\n"
        "    + struct.pack('>H', 0x0100) + b'\\x00' * 10 + b'\\x00' * 36\n"
        "    + b'\\x00' * 24 + struct.pack('>I', 2))\n"
        "data = box('ftyp', b'isom' + struct.pack('>I', 0x200) + b'isomiso2mp41') + box('moov', mvhd)\n"
        "sys.stdout.buffer.write(data)\n",
        encoding="utf-8",
    )
    backend = FFmpegVideoRenderer(binary=[sys.executable, str(stub)], request_timeout=30.0)
    provider = VideoRendererProvider(backend=backend, max_retries=1)
    render = asyncio.run(provider.render(_request(tmp_path), output_dir=tmp_path / "out"))
    assert render.duration_seconds == pytest.approx(2.5)
    assert Path(render.file).read_bytes()[4:8] == b"ftyp"


# ------------------------------------------------------------- stage ---------


class _FakeRendererProvider:
    """Stage-level fake renderer that saves a real MP4 like the provider."""

    provider_name = "fake"

    def __init__(self, *, duration: float = 1.0) -> None:
        self.duration = duration
        self.requests: list[VideoRenderRequest] = []

    async def render(
        self,
        request: VideoRenderRequest,
        *,
        output_dir: str | Path,
        filename: str = "short.mp4",
    ) -> VideoRender:
        self.requests.append(request)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
        data = _mp4_bytes(self.duration)
        target = out / filename
        target.write_bytes(data)
        return VideoRender(
            file=str(target),
            fps=request.fps,
            width=request.width,
            height=request.height,
            duration_seconds=self.duration,
            size_bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
        )


def _stage(tmp_path: Path, renderer: _FakeRendererProvider) -> VideoRenderStage:
    return VideoRenderStage(context=_context(tmp_path, _settings(tmp_path)), renderer=renderer)


def test_stage_renders_and_reports_manifest(tmp_path: Path) -> None:
    fake = _FakeRendererProvider()
    stage = _stage(tmp_path, fake)

    async def go() -> None:
        result: RenderManifestOutput = await stage.run(_payload(tmp_path))
        assert result.validation.status.value == "ok"
        assert result.file == str(_settings(tmp_path).work_dir / "short.mp4")
        assert result.metadata.container == "mp4"
        assert result.metadata.fps == 30
        assert result.metadata.width == 1080
        assert result.metadata.height == 1920
        assert result.metadata.backend == "fake"
        assert fake.requests[0].segments[0].duration_seconds == 6.0
        assert fake.requests[0].audio.endswith("master.wav")

    asyncio.run(go())


def test_stage_fails_when_plan_has_no_clips(tmp_path: Path) -> None:
    fake = _FakeRendererProvider()
    stage = _stage(tmp_path, fake)
    payload = _payload(tmp_path)
    payload["tracks"]["video"] = []

    async def go() -> None:
        with pytest.raises(RenderValidationError, match="no video clips"):
            await stage.run(payload)

    asyncio.run(go())


def test_stage_fails_when_duration_exceeds_budget(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.target_max_duration_seconds = 45.0
    fake = _FakeRendererProvider(duration=46.0)
    stage = VideoRenderStage(context=_context(tmp_path, settings), renderer=fake)

    async def go() -> None:
        with pytest.raises(RenderValidationError, match="exceeds"):
            await stage.run(_payload(tmp_path))

    asyncio.run(go())


def test_stage_fails_on_checksum_mismatch(tmp_path: Path) -> None:
    class _CorruptFake(_FakeRendererProvider):
        async def render(  # noqa: D102
            self,
            request: VideoRenderRequest,
            *,
            output_dir: str | Path,
            filename: str = "short.mp4",
        ) -> VideoRender:
            render = await super().render(request, output_dir=output_dir, filename=filename)
            return render.model_copy(update={"checksum": "bad"})

    fake = _CorruptFake()
    stage = _stage(tmp_path, fake)

    async def go() -> None:
        with pytest.raises(RenderValidationError, match="checksum mismatch"):
            await stage.run(_payload(tmp_path))

    asyncio.run(go())


# ------------------------------------------------------------- runner --------


def test_runner_writes_render_after_assembly(tmp_path: Path) -> None:
    from pr1me.core.base_stage import BaseStage
    from pr1me.models.contracts.base import StageInput

    settings = _settings(tmp_path)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    context = _context(tmp_path, settings)

    class StubInput(StageInput):
        model_config = {"extra": "ignore"}
        topic: str | None = None

    class AssemblyStub(BaseStage[StubInput, AssemblyOutput]):
        stage_id = "video_assembly"
        name = "Assembly Stub"
        depends_on: tuple = ()
        input_model = StubInput
        output_model = AssemblyOutput

        async def execute(self, payload: StubInput) -> AssemblyOutput:
            return _assembly(tmp_path)

    fake = _FakeRendererProvider()

    async def go() -> None:
        registry = StageRegistry(context=context)
        registry.register(AssemblyStub(context=context))
        registry.register(VideoRenderStage(context=context, renderer=fake))
        runner = PipelineRunner(registry, context=context, artifact_dir=settings.work_dir)
        seed = _payload(tmp_path)
        seed["topic"] = "Layer Height"
        report = await runner.run(seed, job_id="job-render")
        assert report.run_status.value == "complete"
        assert [record.stage_id for record in report.stages] == ["video_assembly", "video_render"]
        artifact = json.loads(
            (settings.work_dir / "job-render_video_render.json").read_text(encoding="utf-8")
        )
        assert artifact["metadata"]["fps"] == 30
        assert artifact["validation"]["status"] == "ok"
        assert Path(settings.work_dir / "short.mp4").is_file()  # noqa: ASYNC240

    asyncio.run(go())


# ------------------------------------------------------------ contract --------


def test_render_metadata_rejects_zero_fps() -> None:
    with pytest.raises(ValueError):
        RenderMetadata(
            codec="libx264",
            container="mp4",
            fps=0,
            width=1080,
            height=1920,
            duration_seconds=1.0,
            audio_codec="aac",
            checksum="a",
            backend="ffmpeg",
        )


def test_render_manifest_requires_file() -> None:
    with pytest.raises(ValueError):
        RenderManifestOutput(
            output_dir="out",
            file="",
            bytes=0,
            metadata=RenderMetadata(
                codec="libx264",
                container="mp4",
                fps=30,
                width=1080,
                height=1920,
                duration_seconds=1.0,
                audio_codec="aac",
                checksum="a",
                backend="ffmpeg",
            ),
        )