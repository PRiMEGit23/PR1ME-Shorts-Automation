"""Production pipeline tests: the fourteen-stage mission pipeline end-to-end.

Covers the orchestrator's guarantees:

- a fresh run produces the full run layout and a complete manifest
- dry-run publishing by default; real publishing only when enabled
- resume: completed stages are skipped from matching checkpoints
- resume after a render-loop (ComfyUI) crash, a voice failure, and a video
  render failure - the failing stage re-runs, the rest is restored
- corrupted artifacts force a re-run instead of a silent restore
- fingerprints are deterministic: identical directives reproduce identical
  stage fingerprints across runs
- the publisher fails closed when the channel category is unmapped

All providers are injected fakes (deterministic SimulatedRenderer, fake
voice / video / YouTube providers), so the suite runs offline.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import struct
from pathlib import Path

import pytest
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.visual_architecture import EngineeringDomain, Modality
from runtime.pipeline import ProductionPipeline
from runtime.pipeline_stages import build_srt, compose_narration
from runtime.renderer import SimulatedRenderer

from pr1me.providers.video_renderer import VideoRender, VideoRenderRequest
from pr1me.providers.voice import VoiceRender, VoiceSynthesisError
from pr1me.providers.youtube import YouTubeBackend, YouTubeProvider

FDM = EngineeringDomain.FDM
PHOTOREAL = Modality.PHOTOREAL

# ------------------------------------------------------------------ fakes --


def _wav(sample_rate: int = 22050, seconds: float = 0.01) -> bytes:
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


def _mp4() -> bytes:
    def box(tag: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", 8 + len(payload)) + tag + payload

    mvhd = box(
        b"mvhd",
        b"\x00\x00\x00\x00"
        + struct.pack(">II", 0, 0)
        + struct.pack(">II", 1000, 6000)
        + struct.pack(">I", 0x00010000)
        + struct.pack(">H", 0x0100)
        + b"\x00" * 10
        + b"\x00" * 36
        + b"\x00" * 24
        + struct.pack(">I", 2),
    )
    return box(b"ftyp", b"isom" + struct.pack(">I", 0x00000200) + b"isomiso2mp41") + box(
        b"moov", mvhd
    )


class _FakeVoiceProvider:
    """Minimal VoiceProvider seam: writes a real WAV, fails on demand."""

    name = "voice"
    provider_name = "fake-voice"

    def __init__(self, fail_first: int = 0) -> None:
        self._failures = fail_first
        self.calls = 0

    async def synthesize(
        self,
        text: str,
        *,
        output_dir: str | Path,
        voice: str | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
    ) -> VoiceRender:
        self.calls += 1
        if self._failures > 0:
            self._failures -= 1
            raise VoiceSynthesisError("TTS backend down", retryable=False)
        data = _wav(sample_rate or 22050)
        directory = Path(output_dir)
        await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
        target = directory / f"narration.{(format_ or 'wav').lstrip('.')}"
        await asyncio.to_thread(target.write_bytes, data)
        return VoiceRender(
            file=str(target),
            text=text,
            voice=voice or "default",
            sample_rate=sample_rate or 22050,
            format=(format_ or "wav").lstrip("."),
            duration_seconds=0.01,
            checksum=hashlib.sha256(data).hexdigest(),
        )


class _FakeVideoRendererProvider:
    """Minimal VideoRendererProvider seam: writes a valid MP4, fails on demand."""

    name = "video_renderer"
    provider_name = "fake-video"

    codec = "libx264"
    container = "mp4"
    crf = 20
    audio_codec = "aac"
    audio_bitrate_kbps = 192

    def __init__(self, fail_first: int = 0) -> None:
        self._failures = fail_first
        self.calls = 0

    async def render(
        self,
        request: VideoRenderRequest,
        *,
        output_dir: str | Path,
        filename: str = "short.mp4",
    ) -> VideoRender:
        self.calls += 1
        if self._failures > 0:
            self._failures -= 1
            raise RuntimeError("encoder crashed")
        data = _mp4()
        directory = Path(output_dir)
        await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
        target = directory / filename
        await asyncio.to_thread(target.write_bytes, data)
        return VideoRender(
            file=str(target),
            fps=request.fps,
            width=request.width,
            height=request.height,
            duration_seconds=6.0,
            size_bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
        )


class _FakeYouTubeBackend(YouTubeBackend):
    """Canned YouTube API backend; records whether any upload started."""

    name = "fake-youtube"

    def __init__(self) -> None:
        self.upload_media_calls = 0

    async def initialize_upload(
        self, *, access_token: str, metadata: dict, media_size: int, media_type: str
    ) -> str:
        return "https://example.com/upload/session-1"

    async def upload_media(self, *, upload_uri: str, data: bytes, media_type: str) -> dict:
        self.upload_media_calls += 1
        return {"id": "vid-123", "status": {"privacyStatus": "private", "uploadStatus": "uploaded"}}

    async def set_thumbnail(self, *, access_token: str, video_id: str, data: bytes, image_type: str) -> dict:
        return {}

    async def fetch_video(self, *, access_token: str, video_id: str) -> dict:
        return {
            "snippet": {"publishedAt": "2026-08-15T00:00:00Z"},
            "status": {"privacyStatus": "private"},
        }

    async def refresh_token(self, *, client_id: str, client_secret: str, refresh_token: str) -> dict:
        return {"access_token": "fresh"}


class _CrashingRenderer:
    """SimulatedRenderer that crashes the first N renders (ComfyUI down)."""

    def __init__(self, fail_first: int = 1) -> None:
        self._remaining = fail_first
        self._inner = SimulatedRenderer()

    def render(self, request):
        if self._remaining > 0:
            self._remaining -= 1
            raise RuntimeError("ComfyUI connection refused")
        return self._inner.render(request)


# ------------------------------------------------------------------ rows --


def _education_row() -> dict[str, str]:
    return {
        "topic": "How 3D Printing Works",
        "difficulty": "B",
        "category": "Education",
        "subcategory": "Basics",
        "keywords": '["3d printing","additive manufacturing"]',
        "search_intent": "explain how it works",
        "viewer_level": "Beginner",
        "engineering_summary": "FDM printers melt filament and lay it down in layers.",
        "scene_count": "5",
    }


def _pipeline(row: dict[str, str], run_dir: Path, **overrides):
    defaults: dict = {
        "row": row,
        "run_dir": run_dir,
        "seed": 42,
        "max_attempts": 3,
        "engineering_domain": FDM,
        "modality": PHOTOREAL,
        "renderer": SimulatedRenderer(),
        "voice_provider": _FakeVoiceProvider(),
        "video_renderer_provider": _FakeVideoRendererProvider(),
    }
    defaults.update(overrides)
    return ProductionPipeline(**defaults)


# ------------------------------------------------------------ narration --


def test_compose_narration_is_deterministic_and_complete() -> None:
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    narration = compose_narration(plan)
    assert narration == compose_narration(plan)
    assert plan.attention_hook in narration
    assert plan.final_takeaway in narration
    for step in plan.knowledge_flow:
        assert step.concept in narration


def test_build_srt_is_deterministic() -> None:
    text = "First sentence. Second one! Third?"
    first = build_srt(text, 30.0)
    assert first == build_srt(text, 30.0)
    blocks = [part for part in first.split("\n\n") if part.strip()]
    assert len(blocks) == 3
    assert "00:00:00,000" in first


# ------------------------------------------------------------ fresh run --


@pytest.mark.asyncio
async def test_fresh_run_completes_end_to_end(tmp_path) -> None:
    run_dir = tmp_path / "run"
    result = await _pipeline(GYROID_ROW, run_dir).run()

    assert result.status == "complete"
    assert result.error is None
    assert (run_dir / "manifest.json").is_file()
    assert (run_dir / "reports" / "execution_report.json").is_file()
    assert (run_dir / "events.json").is_file()
    assert (run_dir / "pipeline_context.json").is_file()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["run_id"] == result.run_id

    for scene_id in ("S1", "S2", "S3", "S4", "S5"):
        assert (run_dir / "images" / f"{scene_id}.png").is_file()
        assert (run_dir / "workflow" / f"{scene_id}.json").is_file()
    assert (run_dir / "audio" / "narration.wav").is_file()
    assert (run_dir / "subtitles" / "narration.srt").is_file()
    assert (run_dir / "video" / "short.mp4").is_file()
    assert (run_dir / "thumbnail" / "thumbnail.png").is_file()
    assert (run_dir / "metadata" / "metadata.json").is_file()

    metadata = json.loads((run_dir / "metadata" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["visibility"] == "private"
    assert metadata["made_for_kids"] is False
    # "Slicer & Print Settings" is not in the canonical YouTube taxonomy.
    assert metadata["category_id"] is None

    report = json.loads((run_dir / "reports" / "execution_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "complete"
    assert report["stages"][-1]["stage_id"] == "publisher"
    assert all(stage["cache_hit"] is False for stage in report["stages"])


# ------------------------------------------------------------ publisher --


@pytest.mark.asyncio
async def test_dry_run_publisher_manifest(tmp_path) -> None:
    run_dir = tmp_path / "run"
    result = await _pipeline(GYROID_ROW, run_dir).run()

    manifest = json.loads((run_dir / "publish_manifest.json").read_text(encoding="utf-8"))
    assert manifest["dry_run"] is True
    assert manifest["video_id"].startswith("dry-run-")
    assert manifest["url"] == f"https://youtu.be/{manifest['video_id']}"
    assert manifest["upload_status"] == "dry-run"
    assert manifest["visibility"] == "private"
    assert "dry_run" in result.manifest["final_artifacts"]["publish_manifest"]


@pytest.mark.asyncio
async def test_real_publish_succeeds_with_mapped_category(tmp_path) -> None:
    run_dir = tmp_path / "run"
    backend = _FakeYouTubeBackend()
    provider = YouTubeProvider(backend=backend, access_token="test-token")
    result = await _pipeline(
        _education_row(), run_dir, publish=True, youtube_provider=provider
    ).run()

    assert result.status == "complete"
    manifest = json.loads((run_dir / "publish_manifest.json").read_text(encoding="utf-8"))
    assert manifest["dry_run"] is False
    assert manifest["video_id"] == "vid-123"
    assert manifest["url"] == "https://youtu.be/vid-123"
    assert manifest["upload_status"] == "uploaded"
    assert backend.upload_media_calls == 1


@pytest.mark.asyncio
async def test_real_publish_fails_closed_on_unknown_category(tmp_path) -> None:
    run_dir = tmp_path / "run"
    backend = _FakeYouTubeBackend()
    provider = YouTubeProvider(backend=backend, access_token="test-token")
    result = await _pipeline(
        GYROID_ROW, run_dir, publish=True, youtube_provider=provider
    ).run()

    assert result.status == "failed"
    assert "unknown channel category" in (result.error or "")
    # No upload ever started.
    assert backend.upload_media_calls == 0


# ------------------------------------------------------------ determinism --


@pytest.mark.asyncio
async def test_fingerprints_are_deterministic_across_runs(tmp_path) -> None:
    # Determinism holds per run directory: stage inputs include absolute
    # artifact paths, so two different run dirs legitimately fingerprint
    # differently. Re-running the same run dir must reproduce every stage.
    run_dir = tmp_path / "run"
    first = await _pipeline(GYROID_ROW, run_dir).run()
    second = await _pipeline(GYROID_ROW, run_dir).run()

    assert first.status == second.status == "complete"
    fingerprints_a = {s["stage_id"]: s["fingerprint"] for s in first.report["stages"]}
    fingerprints_b = {s["stage_id"]: s["fingerprint"] for s in second.report["stages"]}
    assert set(fingerprints_a) == set(fingerprints_b)
    for stage_id, fingerprint in fingerprints_a.items():
        assert fingerprint == fingerprints_b[stage_id]


# ------------------------------------------------------------ resume --


@pytest.mark.asyncio
async def test_resume_skips_completed_stages(tmp_path) -> None:
    run_dir = tmp_path / "run"
    pipeline = _pipeline(GYROID_ROW, run_dir)
    first = await pipeline.run()
    assert first.status == "complete"

    second = await pipeline.run(resume=True)
    assert second.status == "complete"
    report = json.loads((run_dir / "reports" / "execution_report.json").read_text(encoding="utf-8"))
    assert len(report["stages"]) == 15
    assert all(stage["cache_hit"] is True for stage in report["stages"])
    assert all(stage["status"] == "skipped" for stage in report["stages"])
    # Restored outputs are usable: the dry-run manifest still exists.
    assert (run_dir / "publish_manifest.json").is_file()


@pytest.mark.asyncio
async def test_resume_after_render_loop_crash(tmp_path) -> None:
    run_dir = tmp_path / "run"
    broken = _pipeline(
        GYROID_ROW, run_dir, renderer=_CrashingRenderer(fail_first=1)
    )
    failed = await broken.run()
    assert failed.status == "failed"
    assert "ComfyUI connection refused" in (failed.error or "")

    healed = _pipeline(
        GYROID_ROW, run_dir, renderer=_CrashingRenderer(fail_first=0)
    )
    resumed = await healed.run(resume=True)
    assert resumed.status == "complete"
    report = json.loads((run_dir / "reports" / "execution_report.json").read_text(encoding="utf-8"))
    by_id = {stage["stage_id"]: stage for stage in report["stages"]}
    # Everything before the crash was restored; the crashed stage re-ran.
    for stage_id in ("knowledge_load", "educational_director", "visual_intelligence",
                     "prompt_compiler", "workflow_builder"):
        assert by_id[stage_id]["cache_hit"] is True
    assert by_id["render_loop"]["cache_hit"] is False
    assert by_id["render_loop"]["status"] == "completed"
    # The whole tail ran for real.
    for stage_id in ("voice", "subtitles", "video_assembly", "video_render",
                     "thumbnail", "metadata", "publisher"):
        assert by_id[stage_id]["cache_hit"] is False
    assert (run_dir / "images" / "S1.png").is_file()


@pytest.mark.asyncio
async def test_resume_after_voice_failure(tmp_path) -> None:
    run_dir = tmp_path / "run"
    voice = _FakeVoiceProvider(fail_first=1)
    failed = await _pipeline(GYROID_ROW, run_dir, voice_provider=voice).run()
    assert failed.status == "failed"
    assert "TTS backend down" in (failed.error or "")

    healed = _pipeline(GYROID_ROW, run_dir, voice_provider=_FakeVoiceProvider())
    resumed = await healed.run(resume=True)
    assert resumed.status == "complete"
    report = json.loads((run_dir / "reports" / "execution_report.json").read_text(encoding="utf-8"))
    by_id = {stage["stage_id"]: stage for stage in report["stages"]}
    assert by_id["render_loop"]["cache_hit"] is True
    assert by_id["voice"]["cache_hit"] is False
    assert by_id["video_render"]["cache_hit"] is False
    assert (run_dir / "audio" / "narration.wav").is_file()
    assert (run_dir / "video" / "short.mp4").is_file()


@pytest.mark.asyncio
async def test_resume_after_video_render_failure(tmp_path) -> None:
    run_dir = tmp_path / "run"
    video = _FakeVideoRendererProvider(fail_first=1)
    failed = await _pipeline(GYROID_ROW, run_dir, video_renderer_provider=video).run()
    assert failed.status == "failed"
    assert "encoder crashed" in (failed.error or "")

    healed = _pipeline(GYROID_ROW, run_dir, video_renderer_provider=_FakeVideoRendererProvider())
    resumed = await healed.run(resume=True)
    assert resumed.status == "complete"
    report = json.loads((run_dir / "reports" / "execution_report.json").read_text(encoding="utf-8"))
    by_id = {stage["stage_id"]: stage for stage in report["stages"]}
    assert by_id["video_assembly"]["cache_hit"] is True
    assert by_id["video_render"]["cache_hit"] is False
    assert by_id["publisher"]["cache_hit"] is False
    assert (run_dir / "video" / "short.mp4").is_file()


@pytest.mark.asyncio
async def test_corrupted_artifact_forces_rerun(tmp_path) -> None:
    run_dir = tmp_path / "run"
    pipeline = _pipeline(GYROID_ROW, run_dir)
    first = await pipeline.run()
    assert first.status == "complete"

    voice_artifacts = list((run_dir / "artifacts" / "voice").glob("output.*.json"))
    assert voice_artifacts, "expected a persisted voice output artifact"
    voice_artifacts[0].unlink()

    second = await pipeline.run(resume=True)
    assert second.status == "complete"
    report = json.loads((run_dir / "reports" / "execution_report.json").read_text(encoding="utf-8"))
    by_id = {stage["stage_id"]: stage for stage in report["stages"]}
    assert by_id["knowledge_load"]["cache_hit"] is True
    assert by_id["voice"]["cache_hit"] is False
    assert (run_dir / "audio" / "narration.wav").is_file()


@pytest.mark.asyncio
async def test_resume_without_flag_reruns_everything(tmp_path) -> None:
    run_dir = tmp_path / "run"
    pipeline = _pipeline(GYROID_ROW, run_dir)
    first = await pipeline.run()
    assert first.status == "complete"

    second = await pipeline.run(resume=False)
    assert second.status == "complete"
    report = json.loads((run_dir / "reports" / "execution_report.json").read_text(encoding="utf-8"))
    assert all(stage["cache_hit"] is False for stage in report["stages"])
