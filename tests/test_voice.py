"""Tests for the Voice Generation subsystem (TTS provider + stage)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import struct
from pathlib import Path
from typing import Any

import httpx
import pytest

from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.errors import ProviderNotConfiguredError
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.contracts.script import ScriptOutput
from pr1me.models.contracts.visual import (
    VisualBranding,
    VisualPlanOutput,
    VisualScene,
    VisualShot,
)
from pr1me.models.contracts.voice import VoiceManifestOutput
from pr1me.pipeline.runner import PipelineRunner
from pr1me.providers.comfyui import ComfyUIRender
from pr1me.providers.voice import (
    HTTPVoiceBackend,
    VoiceBackend,
    VoiceProvider,
    VoiceRender,
    VoiceSynthesisError,
    VoiceSynthesisRequest,
    VoiceTimeoutError,
    wav_duration,
)
from pr1me.stages.image_generation_stage import ImageGenerationStage
from pr1me.stages.voice_generation_stage import VoiceGenerationStage

logger = logging.getLogger("test-voice")

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _wav_bytes(sample_rate: int = 22050, seconds: float = 0.5) -> bytes:
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


def _script() -> ScriptOutput:
    return ScriptOutput(
        hook="Why does the layer lift?",
        explanation="Warping cools uneven.",
        practical_insight="Add a brim.",
        ending="Try it.",
        word_count=12,
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "work")


def _context(tmp_path: Path, settings: Settings) -> StageContext:
    return StageContext(
        settings=settings,
        logger=logger,
        prompt_loader=PromptLoader(tmp_path / "prompts"),
    )


# -------------------------------------------------------------- wav parsing -


def test_wav_duration() -> None:
    duration, rate = wav_duration(_wav_bytes(seconds=0.5))
    assert duration == pytest.approx(0.5, abs=0.01)
    assert rate == 22050
    assert wav_duration(b"not a wav") == (0.0, 0)


# ---------------------------------------------------------------- provider ---


def _voice_transport(
    *,
    tries: int = 1,
    status: int = 200,
    body: bytes | None = None,
) -> httpx.MockTransport:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/tts":
            calls["n"] += 1
            if calls["n"] < tries:
                return httpx.Response(503, content=b"")
            return httpx.Response(status, content=body or _wav_bytes())
        return httpx.Response(404, content=b"")

    return httpx.MockTransport(handler)


def _provider(
    transport: httpx.MockTransport,
    *,
    max_retries: int = 3,
    retry_base_delay: float = 0.01,
    timeout_seconds: float | None = None,
) -> VoiceProvider:
    backend = HTTPVoiceBackend(
        base_url="http://voice.local",
        path="/v1/tts",
        http_client=httpx.AsyncClient(transport=transport),
    )
    return VoiceProvider(
        backend=backend,
        max_retries=max_retries,
        retry_base_delay=retry_base_delay,
        timeout_seconds=timeout_seconds,
    )


def test_synthesize_saves_audio_and_returns_typed_render(tmp_path: Path) -> None:
    render_holder: list[VoiceRender] = []

    async def go() -> None:
        provider = _provider(_voice_transport())
        render = await provider.synthesize("Why does the layer lift?", output_dir=tmp_path / "out")
        assert render.duration_seconds == pytest.approx(0.5, abs=0.01)
        assert render.sample_rate == 22050
        assert render.text == "Why does the layer lift?"
        assert render.checksum
        render_holder.append(render)
        await provider.close()

    asyncio.run(go())
    path = Path(render_holder[0].file)
    assert path.parent == tmp_path / "out"
    assert path.name == "narration.wav"
    assert path.is_file()
    assert path.read_bytes() == _wav_bytes()


def test_synthesize_uses_configured_voice_and_sample_rate(tmp_path: Path) -> None:
    async def go() -> None:
        provider = _provider(_voice_transport(body=_wav_bytes(sample_rate=44100, seconds=0.2)))
        render = await provider.synthesize(
            "x",
            output_dir=tmp_path,
            voice="frank",
            sample_rate=44100,
        )
        assert render.voice == "frank"
        assert render.sample_rate == 44100
        await provider.close()

    asyncio.run(go())


def test_queue_retries_transient_failure(tmp_path: Path) -> None:
    async def go() -> None:
        provider = _provider(_voice_transport(tries=2), max_retries=3)
        render = await provider.synthesize("x", output_dir=tmp_path)
        assert render.checksum
        await provider.close()

    asyncio.run(go())


def test_server_error_raises_after_retries(tmp_path: Path) -> None:
    async def go() -> None:
        provider = _provider(_voice_transport(status=500), max_retries=2)
        with pytest.raises(VoiceSynthesisError, match="HTTP 500"):
            await provider.synthesize("x", output_dir=tmp_path)
        await provider.close()

    asyncio.run(go())


def test_client_error_fails_fast(tmp_path: Path) -> None:
    async def go() -> None:
        provider = _provider(_voice_transport(status=400), max_retries=3)
        with pytest.raises(VoiceSynthesisError, match="HTTP 400"):
            await provider.synthesize("x", output_dir=tmp_path)
        await provider.close()

    asyncio.run(go())


class _SlowBackend(VoiceBackend):
    name = "slow"

    async def synthesize(self, request: VoiceSynthesisRequest) -> bytes:  # noqa: ARG002
        await asyncio.sleep(5)
        return b""


def test_timeout_raises() -> None:
    async def go() -> None:
        provider = VoiceProvider(backend=_SlowBackend(), timeout_seconds=0.05, max_retries=1)
        with pytest.raises(VoiceTimeoutError):
            await provider.synthesize("x", output_dir=Path("."))
        await provider.close()

    asyncio.run(go())


def test_missing_backend_config_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PR1ME_VOICE_BASE_URL", raising=False)
    with pytest.raises(ProviderNotConfiguredError, match="no voice backend configured"):
        VoiceProvider()


# ---------------------------------------------------------------- stage ------


class FakeVoiceProvider(VoiceProvider):
    """Records synthesize calls and returns a tiny WAV for every request."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return "fake"

    async def synthesize(
        self,
        text: str,
        *,
        output_dir: str | Path,
        voice: str | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
    ) -> VoiceRender:
        dest = Path(output_dir)
        await asyncio.to_thread(dest.mkdir, parents=True, exist_ok=True)
        data = _wav_bytes()
        target = dest / f"narration.{format_ or 'wav'}"
        await asyncio.to_thread(target.write_bytes, data)
        duration, rate = wav_duration(data)
        self.calls.append({"text": text, "voice": voice, "sample_rate": sample_rate, "format": format_})
        return VoiceRender(
            file=str(target),
            text=text,
            voice=voice or "default",
            sample_rate=rate,
            format=format_ or "wav",
            duration_seconds=duration,
            checksum=hashlib.sha256(data).hexdigest(),
        )


class MissingFileVoiceProvider(FakeVoiceProvider):
    async def synthesize(
        self,
        text: str,
        *,
        output_dir: str | Path,
        voice: str | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
    ) -> VoiceRender:
        self.calls.append({"text": text})
        return VoiceRender(
            file=str(Path(output_dir) / "does-not-exist.wav"),
            text=text,
            voice=voice or "default",
            sample_rate=sample_rate or 22050,
            format=format_ or "wav",
            duration_seconds=1.0,
            checksum="0" * 64,
        )


def test_stage_synthesizes_single_narration(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    context = _context(tmp_path, settings)
    fake = FakeVoiceProvider()
    stage = VoiceGenerationStage(context=context, voice_provider=fake)

    async def go() -> None:
        result: VoiceManifestOutput = await stage.run(_script().model_dump(mode="json"))
        assert result.total == 1
        assert len(result.assets) == 1
        assert result.validation.status.value == "ok"
        assert len(fake.calls) == 1
        expected = _script().full_text()
        assert fake.calls[0]["text"] == expected
        assert result.assets[0].metadata.text == expected

    asyncio.run(go())


def test_stage_preserves_script_exactly(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    stage = VoiceGenerationStage(
        context=_context(tmp_path, settings),
        voice_provider=FakeVoiceProvider(),
    )

    async def go() -> None:
        result: VoiceManifestOutput = await stage.run(_script().model_dump(mode="json"))
        assert result.assets[0].metadata.text == (
            "Why does the layer lift? Warping cools uneven. Add a brim. Try it."
        )
        assert (settings.work_dir / "audio" / "narration.wav").is_file()

    asyncio.run(go())


def test_stage_fails_when_narration_file_missing(tmp_path: Path) -> None:
    from pr1me.stages.voice_generation_stage import VoiceGenerationError

    settings = _settings(tmp_path)
    stage = VoiceGenerationStage(
        context=_context(tmp_path, settings),
        voice_provider=MissingFileVoiceProvider(),
    )

    async def go() -> None:
        with pytest.raises(VoiceGenerationError, match="cannot read narration"):
            await stage.run(_script().model_dump(mode="json"))

    asyncio.run(go())


def test_runner_includes_voice_generation_last(tmp_path: Path) -> None:
    from pr1me.core.base_stage import BaseStage
    from pr1me.models.contracts.base import StageInput, StageOutput

    settings = _settings(tmp_path)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    context = _context(tmp_path, settings)
    script = _script()

    class ScriptStubInput(StageInput):
        model_config = {"extra": "ignore"}
        topic: str | None = None

    class ScriptStubOutput(StageOutput):
        hook: str
        explanation: str
        practical_insight: str
        ending: str
        word_count: int = 12

    class ScriptStub(BaseStage[ScriptStubInput, ScriptStubOutput]):
        stage_id = "script"
        name = "Script Stub"
        depends_on: tuple = ()
        input_model = ScriptStubInput
        output_model = ScriptStubOutput

        async def execute(self, payload):  # noqa: ARG002
            return script

    class VisualStubInput(StageInput):
        model_config = {"extra": "ignore"}
        total_seconds: float
        shots: list[VisualShot] = []

    class VisualStubOutput(StageOutput):
        total_seconds: float
        shots: list[VisualShot] = []
        branding: VisualBranding = VisualBranding()

    class VisualStub(BaseStage[VisualStubInput, VisualStubOutput]):
        stage_id = "visual"
        name = "Visual Stub"
        depends_on: tuple = ()
        input_model = VisualStubInput
        output_model = VisualStubOutput

        async def execute(self, payload):  # noqa: ARG002
            return _plan()

    registry = StageRegistry(context=context)
    registry.register(ScriptStub(context=context))
    registry.register(VisualStub(context=context))
    registry.register(ImageGenerationStage(context=context, comfyui_provider=_FakeComfyUI()))
    registry.register(VoiceGenerationStage(context=context, voice_provider=FakeVoiceProvider()))
    runner = PipelineRunner(registry, context=context, artifact_dir=settings.work_dir)

    async def go() -> None:
        report = await runner.run(_plan().model_dump(mode="json"), job_id="job-voice")
        assert report.run_status.value == "complete"
        assert [record.stage_id for record in report.stages] == [
            "script",
            "visual",
            "image_generation",
            "voice_generation",
        ]
        assert (settings.work_dir / "audio" / "narration.wav").is_file()

    asyncio.run(go())


class _FakeComfyUI:
    """Minimal fake matching the image stage's provider surface."""

    @property
    def workflow_name(self) -> str:
        return "comfyui.json"

    async def render(self, variables, *, output_dir, workflow=None) -> list[ComfyUIRender]:  # noqa: ARG002
        dest = Path(output_dir)
        await asyncio.to_thread(dest.mkdir, parents=True, exist_ok=True)
        name = "shot_001.png"
        await asyncio.to_thread((dest / name).write_bytes, PNG_1X1)
        return [ComfyUIRender(file=str(dest / name), prompt_id="mock", width=1, height=1)]


def _shot(shot_id: int, subject: str) -> VisualShot:
    return VisualShot(
        id=shot_id,
        block="hook",
        start_second=0.0,
        end_second=6.0,
        duration_seconds=6.0,
        visual=f"{subject}, macro close-up",
        camera="push-in",
        transition="cut",
        reason="hook shot",
        purpose="Attention",
        learning_goal="learn the concept",
        visual_type="Macro Shot",
        scene=VisualScene(
            subject=subject,
            environment="bench",
            composition="centered",
            lighting="studio",
            camera_motion="push",
            focus="nozzle",
            style="technical",
        ),
    )


def _plan() -> VisualPlanOutput:
    return VisualPlanOutput(
        total_seconds=12,
        shots=[_shot(1, "first layer")],
        branding=VisualBranding(use_logo=True, use_broll=False, broll_source=None),
    )
