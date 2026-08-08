"""Tests for the Publish subsystem (YouTubeProvider + PublisherStage)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest

from pr1me.core.base_stage import BaseStage
from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.errors import ProviderNotConfiguredError
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.contracts.publish import PublishInput, PublishManifestOutput
from pr1me.pipeline.runner import PipelineRunner
from pr1me.providers.youtube import (
    HTTPYouTubeBackend,
    YouTubeAuthError,
    YouTubeProvider,
    YouTubePublishResult,
    YouTubeUploadError,
    YouTubeUploadRequest,
    youtube_category_id,
)
from pr1me.stages.publisher_stage import PublisherStage, PublishValidationError

logger = logging.getLogger("test-publish")

#: The publish input always carries the approved metadata fields verbatim
#: (the runner flattens MetadataOutput's rows into the publisher's input).
_PUBLISH_FIELDS: dict[str, Any] = {
    "title": "Fix First-Layer Squish (Print Settings That Work)",
    "description": (
        "Fix first-layer squish with the right print settings. "
        "Level the bed and tune the Z height, then check your first layer."
    ),
    "tags": [
        "first layer squish",
        "3d printing first layer",
        "bed leveling 3d printer",
        "z offset calibration",
        "first layer adhesion",
        "print quality tips",
    ],
    "hashtags": ["#FirstLayer", "#3Dprinting"],
    "category": "Science & Technology",
    "visibility": "public",
    "publish_at": None,
    "made_for_kids": False,
    "primary_keyword": "first layer squish",
    "secondary_keywords": ["bed leveling 3d printer"],
    "search_intent": "How To",
    "target_audience": "Beginner",
}


def _context(tmp_path: Path, settings: Settings) -> StageContext:
    return StageContext(
        settings=settings,
        logger=logger,
        prompt_loader=PromptLoader(tmp_path / "prompts"),
    )


def _settings(tmp_path: Path) -> Settings:
    settings = Settings(work_dir=tmp_path / "work")
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    return settings


def _write_assets(work_dir: Path) -> tuple[Path, Path]:
    video = work_dir / "short.mp4"
    thumbnail = work_dir / "thumbnail.png"
    video.write_bytes(b"fake-mp4")
    thumbnail.write_bytes(b"fake-png")
    return video, thumbnail


# ---------------------------------------------------------------- provider --


class FakeYouTubeAPI:
    """Serves a canned resumable-upload flow, recording every call."""

    def __init__(
        self,
        *,
        visibility: str = "public",
        fail_status: int | None = None,
        fail_times: int = 0,
    ) -> None:
        self.initialize_calls = 0
        self.media_calls = 0
        self.thumbnail_calls = 0
        self.verify_calls = 0
        self.fail_status = fail_status
        self.fail_times = fail_times
        self.visibility = visibility

    @property
    def handler(self) -> Any:
        return self._handle

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST" and "/upload/youtube/v3/videos" in url:
            self.initialize_calls += 1
            if self._should_fail(self.initialize_calls):
                return httpx.Response(self.fail_status or 500, json={})
            return httpx.Response(
                200,
                headers={"Location": "https://res.example/resumable/session/upload"},
                json={},
            )
        if request.method == "PUT" and "/resumable/session/upload" in url:
            self.media_calls += 1
            if self._should_fail(self.media_calls):
                return httpx.Response(self.fail_status or 500, json={})
            return httpx.Response(
                200,
                json={
                    "id": "mock-video-1",
                    "status": {"privacyStatus": self.visibility, "uploadStatus": "uploaded"},
                },
            )
        if request.method == "POST" and "/upload/youtube/v3/thumbnails/set" in url:
            self.thumbnail_calls += 1
            if self._should_fail(self.thumbnail_calls):
                return httpx.Response(self.fail_status or 500, json={})
            return httpx.Response(200, json={"items": []})
        if request.method == "GET" and "/youtube/v3/videos" in url:
            self.verify_calls += 1
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "mock-video-1",
                            "snippet": {"publishedAt": "2026-08-07T12:00:00Z"},
                            "status": {"privacyStatus": self.visibility, "uploadStatus": "processed"},
                        }
                    ]
                },
            )
        return httpx.Response(404, json={"error": "unexpected path"})

    def _should_fail(self, call: int) -> bool:
        return self.fail_status is not None and call <= self.fail_times


def _provider(api: FakeYouTubeAPI, **kwargs: Any) -> YouTubeProvider:
    return YouTubeProvider(
        access_token="ya29.test-token",
        retry_base_delay=0.01,
        backend=HTTPYouTubeBackend(
            base_url="https://api.mock",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(api.handler)),
        ),
        **kwargs,
    )


def _request(video_file: Path, thumbnail_file: Path | None = None) -> YouTubeUploadRequest:
    return YouTubeUploadRequest(
        video_file=str(video_file),
        thumbnail_file=str(thumbnail_file) if thumbnail_file else None,
        title="Fix First-Layer Squish (Print Settings That Work)",
        description="Level the bed and tune the Z height.",
        tags=["first layer squish", "bed leveling"],
        category_id="28",
        visibility="public",
        made_for_kids=False,
    )


def test_youtube_requires_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PR1ME_YOUTUBE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("PR1ME_YOUTUBE_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("PR1ME_YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("PR1ME_YOUTUBE_CLIENT_SECRET", raising=False)
    with pytest.raises(ProviderNotConfiguredError, match="access token"):
        YouTubeProvider()


def test_youtube_category_id_maps_channel_names() -> None:
    assert youtube_category_id("Science & Technology") == "28"
    assert youtube_category_id("Education") == "27"
    assert youtube_category_id("17") == "17"
    assert youtube_category_id("Spicy") is None


def test_youtube_publish_uploads_thumbnail_and_verifies(tmp_path: Path) -> None:
    video = tmp_path / "short.mp4"
    thumbnail = tmp_path / "thumbnail.png"
    video.write_bytes(b"v")
    thumbnail.write_bytes(b"t")
    api = FakeYouTubeAPI()
    provider = _provider(api)

    async def go() -> None:
        result = await provider.publish(_request(video, thumbnail))
        assert result.video_id == "mock-video-1"
        assert result.url == "https://youtu.be/mock-video-1"
        assert result.visibility == "public"
        assert result.published_at == "2026-08-07T12:00:00Z"
        assert result.upload_status == "uploaded"
        assert api.initialize_calls == 1
        assert api.media_calls == 1
        assert api.thumbnail_calls == 1
        assert api.verify_calls == 1
        await provider.close()

    asyncio.run(go())


def test_youtube_publish_retries_transient_failures(tmp_path: Path) -> None:
    video = tmp_path / "short.mp4"
    video.write_bytes(b"v")
    api = FakeYouTubeAPI(fail_status=503, fail_times=1)
    provider = _provider(api)

    async def go() -> None:
        result = await provider.publish(_request(video))
        assert result.video_id == "mock-video-1"
        assert api.initialize_calls == 2
        await provider.close()

    asyncio.run(go())


def test_youtube_publish_fails_fast_on_auth_error(tmp_path: Path) -> None:
    video = tmp_path / "short.mp4"
    video.write_bytes(b"v")
    api = FakeYouTubeAPI(fail_status=401, fail_times=99)
    provider = _provider(api)

    async def go() -> None:
        with pytest.raises(YouTubeAuthError):
            await provider.publish(_request(video))
        await provider.close()

    asyncio.run(go())
    assert api.initialize_calls == 1


def test_youtube_publish_fails_on_missing_video(tmp_path: Path) -> None:
    api = FakeYouTubeAPI()
    provider = _provider(api)

    async def go() -> None:
        with pytest.raises(YouTubeUploadError, match="video file missing"):
            await provider.publish(_request(tmp_path / "nope.mp4"))
        await provider.close()

    asyncio.run(go())
    assert api.initialize_calls == 0


# ------------------------------------------------------------- stage ---------


class FakeYouTubeProvider(YouTubeProvider):
    """Records uploads and returns a canned publish result without a network."""

    def __init__(self, *, visibility: str = "public") -> None:
        super().__init__(access_token="test-token")
        self.calls: list[YouTubeUploadRequest] = []
        self.visibility = visibility

    async def publish(self, request: YouTubeUploadRequest) -> YouTubePublishResult:
        self.calls.append(request)
        return YouTubePublishResult(
            video_id="mock-video-1",
            url="https://youtu.be/mock-video-1",
            visibility=self.visibility,
            published_at="2026-08-07T12:00:00Z",
        )


def _stage(tmp_path: Path, *, provider: FakeYouTubeProvider | None = None) -> tuple[PublisherStage, Settings]:
    settings = _settings(tmp_path)
    return PublisherStage(context=_context(tmp_path, settings), youtube_provider=provider), settings


def test_publisher_stage_dry_run_returns_upload_payload(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    (settings.work_dir / "short.mp4").write_bytes(b"v")
    (settings.work_dir / "thumbnail.png").write_bytes(b"t")
    stage = PublisherStage(context=_context(tmp_path, settings))

    async def go() -> None:
        result: PublishManifestOutput = await stage.run({**_PUBLISH_FIELDS, "dry_run": True})
        assert result.dry_run is True
        assert result.video_id is None
        assert result.url is None
        assert result.upload_payload is not None
        assert result.upload_payload.title == _PUBLISH_FIELDS["title"]
        assert result.upload_payload.tags == [*_PUBLISH_FIELDS["tags"], *_PUBLISH_FIELDS["hashtags"]]
        assert result.upload_payload.visibility.value == "public"
        assert result.validation.status.value == "ok"
        assert "dry_run_payload" in result.validation.checks

    asyncio.run(go())


def test_publisher_stage_uploads_and_returns_manifest(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    (settings.work_dir / "short.mp4").write_bytes(b"v")
    (settings.work_dir / "thumbnail.png").write_bytes(b"t")
    fake = FakeYouTubeProvider()
    stage = PublisherStage(context=_context(tmp_path, settings), youtube_provider=fake)

    async def go() -> None:
        result: PublishManifestOutput = await stage.run(_PUBLISH_FIELDS)
        assert result.video_id == "mock-video-1"
        assert result.url == "https://youtu.be/mock-video-1"
        assert result.visibility is not None and result.visibility.value == "public"
        assert result.published_at == "2026-08-07T12:00:00Z"
        assert result.dry_run is False
        assert result.validation.status.value == "ok"
        assert "upload_ok" in result.validation.checks
        assert "visibility_match" in result.validation.checks

    asyncio.run(go())
    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert request.video_file == str(settings.work_dir / "short.mp4")
    assert request.thumbnail_file == str(settings.work_dir / "thumbnail.png")
    assert request.title == _PUBLISH_FIELDS["title"]
    assert request.tags == [*_PUBLISH_FIELDS["tags"], *_PUBLISH_FIELDS["hashtags"]]
    assert request.category_id == "28"
    assert request.visibility == "public"


def test_publisher_stage_honors_path_overrides(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    video = settings.work_dir / "custom.mp4"
    thumbnail = settings.work_dir / "custom.png"
    video.write_bytes(b"v")
    thumbnail.write_bytes(b"t")
    fake = FakeYouTubeProvider()
    stage = PublisherStage(context=_context(tmp_path, settings), youtube_provider=fake)

    async def go() -> None:
        payload = {**_PUBLISH_FIELDS, "video_file": str(video), "thumbnail_file": str(thumbnail)}
        await stage.run(payload)

    asyncio.run(go())
    assert fake.calls[0].video_file == str(video)
    assert fake.calls[0].thumbnail_file == str(thumbnail)


def test_publisher_stage_fails_when_video_missing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    fake = FakeYouTubeProvider()
    stage = PublisherStage(context=_context(tmp_path, settings), youtube_provider=fake)

    async def go() -> None:
        with pytest.raises(PublishValidationError, match="video file missing"):
            await stage.run(_PUBLISH_FIELDS)

    asyncio.run(go())
    assert fake.calls == []


def test_publisher_stage_fails_on_visibility_mismatch(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    (settings.work_dir / "short.mp4").write_bytes(b"v")
    (settings.work_dir / "thumbnail.png").write_bytes(b"t")
    stage = PublisherStage(
        context=_context(tmp_path, settings),
        youtube_provider=FakeYouTubeProvider(visibility="private"),
    )

    async def go() -> None:
        with pytest.raises(PublishValidationError, match="does not match the intended visibility"):
            await stage.run(_PUBLISH_FIELDS)

    asyncio.run(go())


def test_publisher_stage_fails_on_unknown_category(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    (settings.work_dir / "short.mp4").write_bytes(b"v")
    (settings.work_dir / "thumbnail.png").write_bytes(b"t")
    stage = PublisherStage(context=_context(tmp_path, settings), youtube_provider=FakeYouTubeProvider())

    async def go() -> None:
        with pytest.raises(PublishValidationError, match="not a known YouTube category"):
            await stage.run({**_PUBLISH_FIELDS, "category": "Spicy"})

    asyncio.run(go())


def test_publish_input_requires_publish_at_when_scheduled() -> None:
    with pytest.raises(ValueError, match="publish_at is required"):
        PublishInput.model_validate({**_PUBLISH_FIELDS, "visibility": "scheduled", "publish_at": None})
    payload = PublishInput.model_validate(
        {**_PUBLISH_FIELDS, "visibility": "scheduled", "publish_at": "2026-08-08T12:00:00Z"}
    )
    assert payload.metadata_block().publish_at == "2026-08-08T12:00:00Z"


# ------------------------------------------------------------- runner --------


class _TopicInput(StageInput):
    model_config = {"extra": "ignore"}

    topic: str | None = None


class _TopicOutput(StageOutput):
    topic: str = "First-Layer Squish"


class _ScriptInput(StageInput):
    model_config = {"extra": "ignore"}

    hook: str | None = None


class _ScriptOutput(StageOutput):
    hook: str | None = None


class _FileOutput(StageOutput):
    file: str | None = None


class _MetadataOutput(StageOutput):
    title: str = _PUBLISH_FIELDS["title"]
    description: str = _PUBLISH_FIELDS["description"]
    tags: list[str] = list(_PUBLISH_FIELDS["tags"])
    hashtags: list[str] = list(_PUBLISH_FIELDS["hashtags"])
    category: str = _PUBLISH_FIELDS["category"]
    visibility: str = "public"
    publish_at: str | None = None
    made_for_kids: bool = False
    primary_keyword: str = _PUBLISH_FIELDS["primary_keyword"]
    secondary_keywords: list[str] = list(_PUBLISH_FIELDS["secondary_keywords"])
    search_intent: str = "How To"
    target_audience: str = "Beginner"


class _TopicStub(BaseStage[_TopicInput, _TopicOutput]):
    stage_id = "topic"
    name = "Topic Stub"
    depends_on: tuple = ()
    input_model = _TopicInput
    output_model = _TopicOutput

    async def execute(self, payload: _TopicInput) -> _TopicOutput:  # noqa: ARG002
        return _TopicOutput()


class _ScriptStub(BaseStage[_ScriptInput, _ScriptOutput]):
    stage_id = "script"
    name = "Script Stub"
    depends_on: tuple = ("topic",)
    input_model = _ScriptInput
    output_model = _ScriptOutput

    async def execute(self, payload: _ScriptInput) -> _ScriptOutput:  # noqa: ARG002
        return _ScriptOutput(hook="H")


class _RenderStub(BaseStage[_ScriptInput, _FileOutput]):
    stage_id = "video_render"
    name = "Render Stub"
    depends_on: tuple = ("script",)
    input_model = _ScriptInput
    output_model = _FileOutput

    async def execute(self, payload: _ScriptInput) -> _FileOutput:  # noqa: ARG002
        target = self.context.settings.work_dir / "short.mp4"
        await asyncio.to_thread(target.write_bytes, b"v")
        return _FileOutput(file=str(target))


class _MetadataStub(BaseStage[_ScriptInput, _MetadataOutput]):
    stage_id = "metadata"
    name = "Metadata Stub"
    depends_on: tuple = ("topic", "script", "video_render")
    input_model = _ScriptInput
    output_model = _MetadataOutput

    async def execute(self, payload: _ScriptInput) -> _MetadataOutput:  # noqa: ARG002
        return _MetadataOutput()


class _ThumbnailStub(BaseStage[_ScriptInput, _FileOutput]):
    stage_id = "thumbnail"
    name = "Thumbnail Stub"
    depends_on: tuple = ("topic", "script", "video_render")
    input_model = _ScriptInput
    output_model = _FileOutput

    async def execute(self, payload: _ScriptInput) -> _FileOutput:  # noqa: ARG002
        target = self.context.settings.work_dir / "thumbnail.png"
        await asyncio.to_thread(target.write_bytes, b"t")
        return _FileOutput(file=str(target))


def _run_registry(context: StageContext, provider: FakeYouTubeProvider) -> StageRegistry:
    registry = StageRegistry(context=context)
    registry.register(_TopicStub(context=context))
    registry.register(_ScriptStub(context=context))
    registry.register(_RenderStub(context=context))
    registry.register(_MetadataStub(context=context))
    registry.register(_ThumbnailStub(context=context))
    registry.register(PublisherStage(context=context, youtube_provider=provider))
    return registry


def test_runner_orders_publisher_after_render_metadata_thumbnail(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    context = _context(tmp_path, settings)
    runner = PipelineRunner(
        _run_registry(context, FakeYouTubeProvider()),
        context=context,
        artifact_dir=settings.work_dir,
    )

    async def go() -> None:
        report = await runner.run({}, job_id="job-pub3")
        assert report.run_status.value == "complete"
        assert [record.stage_id for record in report.stages] == [
            "topic",
            "script",
            "video_render",
            "metadata",
            "thumbnail",
            "publisher",
        ]

    asyncio.run(go())


def test_runner_persists_publish_manifest(tmp_path: Path) -> None:
    import json

    settings = _settings(tmp_path)
    context = _context(tmp_path, settings)
    runner = PipelineRunner(
        _run_registry(context, FakeYouTubeProvider()),
        context=context,
        artifact_dir=settings.work_dir,
    )

    async def go() -> None:
        report = await runner.run({}, job_id="job-pub4")
        assert report.run_status.value == "complete"

    asyncio.run(go())
    manifest = json.loads((settings.work_dir / "job-pub4_publisher.json").read_text(encoding="utf-8"))
    assert manifest["video_id"] == "mock-video-1"
    assert manifest["url"] == "https://youtu.be/mock-video-1"
    assert manifest["visibility"] == "public"
    assert manifest["validation"]["status"] == "ok"