"""Tests for the Publishing Assets subsystem (Metadata + Thumbnail stages)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any

import pytest

from pr1me.core.base_stage import BaseStage
from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.contracts.publishing import (
    MetadataOutput,
    ThumbnailConcept,
    ThumbnailManifestOutput,
)
from pr1me.pipeline.runner import PipelineRunner
from pr1me.providers.base_provider import BaseProvider, Completion, CompletionRequest, Usage
from pr1me.providers.comfyui import ComfyUIProvider, ComfyUIRender
from pr1me.stages.metadata_stage import MetadataStage, MetadataValidationError
from pr1me.stages.thumbnail_stage import ThumbnailStage, ThumbnailValidationError, build_thumbnail_prompt

logger = logging.getLogger("test-publishing")

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

#: Canned metadata reply matching prompt 06's schema (passes the SEO gate).
_METADATA_REPLY = {
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
    "secondary_keywords": ["bed leveling 3d printer", "first layer adhesion 3d printing"],
    "search_intent": "How To",
    "target_audience": "Beginner",
}

#: Canned thumbnail concept matching prompt 05's schema.
_THUMBNAIL_CONCEPT = {
    "subject": "A clean fused first layer with perfect squish on a heated bed",
    "composition": "Close-up: the first layer fills 70% of the frame with dark negative space",
    "colors": {"background": "deep navy", "accent": "electric orange", "text": "white"},
    "curiosity_trigger": "Precision",
    "eye_path": "First layer to nozzle gap to text",
    "text_overlay": "PERFECT SQUISH",
    "focal_point": "The smooth fused first layer",
    "concept_reason": "Precision signals craft without risking the click.",
    "style": "high-contrast technical macro render",
}

_METADATA_JSON = json.dumps(_METADATA_REPLY)
_CONCEPT_JSON = json.dumps(_THUMBNAIL_CONCEPT)


def _input_payload() -> dict[str, Any]:
    return {
        "topic": "First-Layer Squish",
        "hook": "Why does the layer lift?",
        "explanation": "Warping cools uneven.",
        "practical_insight": "Add a brim.",
        "ending": "Try it.",
    }


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "work")


def _context(tmp_path: Path, settings: Settings, *, provider: BaseProvider | None = None) -> StageContext:
    return StageContext(
        settings=settings,
        logger=logger,
        prompt_loader=PromptLoader(tmp_path / "prompts"),
        provider=provider,
    )


def _write_prompts(tmp_path: Path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "05_thumbnail_generator.md").write_text(
        "# 05 Thumbnail Generator\n\nReturn one thumbnail concept.", encoding="utf-8"
    )
    (prompts / "06_metadata_generator.md").write_text(
        "# 06 Metadata Generator\n\nReturn one metadata set.", encoding="utf-8"
    )


def _completion(text: str) -> Completion:
    return Completion(
        request=CompletionRequest(),
        text=text,
        usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


# ----------------------------------------------------------------- provider -


class StubProvider(BaseProvider):
    """Returns canned JSON per prompt, selected by a system-prompt marker."""

    name = "stub"

    async def generate(self, request: CompletionRequest) -> Completion:
        if not request.messages:
            raise AssertionError("expected a system message carrying the prompt")
        system = str(request.messages[0].get("content", ""))
        if "06 Metadata Generator" in system:
            return _completion(_METADATA_JSON)
        return _completion(_CONCEPT_JSON)


class FakeComfyUIProvider(ComfyUIProvider):
    """Records render calls and returns a tiny PNG for every render."""

    name = "comfyui"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @property
    def workflow_name(self) -> str:
        return "comfyui.json"

    async def render(self, variables, *, output_dir, workflow=None) -> list[ComfyUIRender]:  # noqa: ARG002
        dest = Path(output_dir)
        await asyncio.to_thread(dest.mkdir, parents=True, exist_ok=True)
        name = f"thumb_{len(self.calls):02d}.png"
        await asyncio.to_thread((dest / name).write_bytes, PNG_1X1)
        self.calls.append(dict(variables))
        return [ComfyUIRender(file=str(dest / name), prompt_id="mock-thumb", width=1, height=1)]


class EmptyComfyUIProvider(FakeComfyUIProvider):
    async def render(self, variables, *, output_dir, workflow=None) -> list[ComfyUIRender]:  # noqa: ARG002
        return []


# --------------------------------------------------------------- contract ----


def test_metadata_output_validates_prompt_schema() -> None:
    output = MetadataOutput.model_validate(_METADATA_REPLY)
    assert output.title.startswith("Fix First-Layer")
    assert output.visibility.value == "public"
    assert len(output.tags) == 6
    assert output.search_intent == "How To"
    assert output.target_audience == "Beginner"


def test_metadata_output_rejects_unknown_visibility() -> None:
    with pytest.raises(ValueError):
        MetadataOutput.model_validate({**_METADATA_REPLY, "visibility": "secret"})


def test_metadata_output_rejects_bad_tag_count() -> None:
    with pytest.raises(ValueError):
        MetadataOutput.model_validate({**_METADATA_REPLY, "tags": ["only one"]})


def test_thumbnail_concept_rejects_unknown_trigger() -> None:
    with pytest.raises(ValueError):
        ThumbnailConcept.model_validate({**_THUMBNAIL_CONCEPT, "curiosity_trigger": "Spicy"})


def test_thumbnail_manifest_contract_rejects_width_zero() -> None:
    with pytest.raises(ValueError):
        ThumbnailManifestOutput(
            output_dir="out",
            file="thumbnail.png",
            bytes=1,
            width=0,
            height=1,
            checksum="abc",
            concept=_THUMBNAIL_CONCEPT,
            metadata={
                "backend": "comfyui",
                "workflow": "comfyui.json",
                "comfyui_prompt_id": "x",
                "prompt": "p",
                "seed": 1,
                "steps": 3,
                "cfg": 1.0,
                "sampler": "a",
                "scheduler": "b",
            },
        )


# ------------------------------------------------------------- metadata ------


def test_metadata_stage_generates_full_metadata(tmp_path: Path) -> None:
    _write_prompts(tmp_path)
    settings = _settings(tmp_path)
    stage = MetadataStage(context=_context(tmp_path, settings, provider=StubProvider()))

    async def go() -> None:
        result: MetadataOutput = await stage.run(_input_payload())
        assert result.title == _METADATA_REPLY["title"]
        assert result.language == "en"
        assert result.validation.status.value == "ok"
        assert "primary_keyword_in_title" in result.validation.checks
        assert result.visibility.value == "public"

    asyncio.run(go())


def test_metadata_stage_passes_topic_and_script_to_prompt(tmp_path: Path) -> None:
    _write_prompts(tmp_path)
    seen: list[str] = []

    class RecordingProvider(StubProvider):
        async def generate(self, request: CompletionRequest) -> Completion:
            seen.append(str(request.messages[1].get("content", "")))
            return await super().generate(request)

    stage = MetadataStage(context=_context(tmp_path, _settings(tmp_path), provider=RecordingProvider()))

    async def go() -> None:
        await stage.run(_input_payload())

    asyncio.run(go())
    message = seen[0]
    assert "topic: First-Layer Squish" in message
    assert '"hook": "Why does the layer lift?"' in message


def test_metadata_stage_rejects_keyword_missing_from_title(tmp_path: Path) -> None:
    _write_prompts(tmp_path)

    class OffKeywordProvider(StubProvider):
        async def generate(self, request: CompletionRequest) -> Completion:
            reply = {**_METADATA_REPLY, "title": "Unrelated Engineering Tips", "primary_keyword": "z offset"}
            return _completion(json.dumps(reply))

    stage = MetadataStage(context=_context(tmp_path, _settings(tmp_path), provider=OffKeywordProvider()))

    async def go() -> None:
        with pytest.raises(MetadataValidationError, match="primary keyword must appear in the title"):
            await stage.run(_input_payload())

    asyncio.run(go())


def test_metadata_stage_fails_fast_without_llm(tmp_path: Path) -> None:
    from pr1me.core.errors import ProviderNotConfiguredError

    _write_prompts(tmp_path)
    stage = MetadataStage(context=_context(tmp_path, _settings(tmp_path)))

    async def go() -> None:
        with pytest.raises(ProviderNotConfiguredError, match="no AI provider"):
            await stage.run(_input_payload())

    asyncio.run(go())


# ------------------------------------------------------------ thumbnail ------


def test_thumbnail_stage_renders_and_manifests(tmp_path: Path) -> None:
    _write_prompts(tmp_path)
    settings = _settings(tmp_path)
    stage = ThumbnailStage(
        context=_context(tmp_path, settings, provider=StubProvider()),
        comfyui_provider=FakeComfyUIProvider(),
    )

    async def go() -> None:
        result: ThumbnailManifestOutput = await stage.run(_input_payload())
        assert result.file == str(settings.work_dir / "thumbnail.png")
        assert result.width == 1
        assert result.height == 1
        assert result.bytes > 0
        assert result.checksum
        assert result.concept.subject == _THUMBNAIL_CONCEPT["subject"]
        assert result.metadata.backend == "comfyui"
        assert result.metadata.workflow == "comfyui.json"
        assert result.metadata.comfyui_prompt_id == "mock-thumb"
        assert result.metadata.prompt.startswith(_THUMBNAIL_CONCEPT["subject"])
        assert result.validation.status.value == "ok"

    asyncio.run(go())
    assert (settings.work_dir / "thumbnail.png").is_file()


def test_thumbnail_stage_composes_concept_into_render_variables(tmp_path: Path) -> None:
    _write_prompts(tmp_path)
    fake = FakeComfyUIProvider()
    stage = ThumbnailStage(
        context=_context(tmp_path, _settings(tmp_path), provider=StubProvider()),
        comfyui_provider=fake,
    )

    async def go() -> None:
        await stage.run(_input_payload())

    asyncio.run(go())
    assert len(fake.calls) == 1
    variables = fake.calls[0]
    assert _THUMBNAIL_CONCEPT["subject"] in variables["positive_prompt"]
    assert _THUMBNAIL_CONCEPT["composition"] in variables["positive_prompt"]
    assert "PERFECT SQUISH" in variables["positive_prompt"]
    assert "vertical 9:16 YouTube thumbnail" in variables["positive_prompt"]
    assert variables["width"] == 1080
    assert variables["height"] == 1920


def test_thumbnail_stage_fails_on_empty_render(tmp_path: Path) -> None:
    _write_prompts(tmp_path)
    stage = ThumbnailStage(
        context=_context(tmp_path, _settings(tmp_path), provider=StubProvider()),
        comfyui_provider=EmptyComfyUIProvider(),
    )

    async def go() -> None:
        with pytest.raises(ThumbnailValidationError, match="rendered no images"):
            await stage.run(_input_payload())

    asyncio.run(go())


def test_thumbnail_stage_rejects_long_text_overlay(tmp_path: Path) -> None:
    _write_prompts(tmp_path)

    class WordyProvider(StubProvider):
        async def generate(self, request: CompletionRequest) -> Completion:
            reply = {**_THUMBNAIL_CONCEPT, "text_overlay": "TOO MANY WORDS HERE BUDDY"}
            return _completion(json.dumps(reply))

    stage = ThumbnailStage(
        context=_context(tmp_path, _settings(tmp_path), provider=WordyProvider()),
        comfyui_provider=FakeComfyUIProvider(),
    )

    async def go() -> None:
        with pytest.raises(ThumbnailValidationError, match="text overlay exceeds"):
            await stage.run(_input_payload())

    asyncio.run(go())


# ------------------------------------------------------------ prompt builder -


def test_build_thumbnail_prompt_orders_fields() -> None:
    concept = ThumbnailConcept.model_validate(_THUMBNAIL_CONCEPT)
    prompt = build_thumbnail_prompt(concept)
    assert prompt.startswith(_THUMBNAIL_CONCEPT["subject"])
    assert "colors: background deep navy, accent electric orange" in prompt
    assert _THUMBNAIL_CONCEPT["focal_point"] in prompt
    assert "text overlay PERFECT SQUISH in white" in prompt
    assert prompt.endswith("vertical 9:16 YouTube thumbnail, high contrast")


# ------------------------------------------------------------- runner --------


class _TopicInput(StageInput):
    model_config = {"extra": "ignore"}

    topic: str | None = None


class _TopicOutput(StageOutput):
    topic: str = "First-Layer Squish"


class _ScriptInput(StageInput):
    model_config = {"extra": "ignore"}

    hook: str | None = None
    explanation: str | None = None
    practical_insight: str | None = None
    ending: str | None = None


class _ScriptOutput(StageOutput):
    hook: str | None = None
    explanation: str | None = None
    practical_insight: str | None = None
    ending: str | None = None


class _RenderInput(StageInput):
    model_config = {"extra": "ignore"}

    file: str | None = None


class _RenderOutput(StageOutput):
    file: str | None = None


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
        return _ScriptOutput(hook="H", explanation="E", practical_insight="P", ending="D")


class _RenderStub(BaseStage[_RenderInput, _RenderOutput]):
    stage_id = "video_render"
    name = "Render Stub"
    depends_on: tuple = ("script",)
    input_model = _RenderInput
    output_model = _RenderOutput

    async def execute(self, payload: _RenderInput) -> _RenderOutput:  # noqa: ARG002
        return _RenderOutput()


def _run_registry(context: StageContext, comfyui: FakeComfyUIProvider) -> StageRegistry:
    registry = StageRegistry(context=context)
    registry.register(_TopicStub(context=context))
    registry.register(_ScriptStub(context=context))
    registry.register(_RenderStub(context=context))
    registry.register(MetadataStage(context=context))
    registry.register(ThumbnailStage(context=context, comfyui_provider=comfyui))
    return registry


def test_runner_orders_render_then_metadata_then_thumbnail(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    _write_prompts(tmp_path)
    context = _context(tmp_path, settings, provider=StubProvider())
    runner = PipelineRunner(
        _run_registry(context, FakeComfyUIProvider()),
        context=context,
        artifact_dir=settings.work_dir,
    )

    async def go() -> None:
        report = await runner.run({"directive": "x"}, job_id="job-pub")
        assert report.run_status.value == "complete"
        assert [record.stage_id for record in report.stages] == [
            "topic",
            "script",
            "video_render",
            "metadata",
            "thumbnail",
        ]

    asyncio.run(go())


def test_runner_persists_metadata_and_thumbnail_manifests(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    _write_prompts(tmp_path)
    context = _context(tmp_path, settings, provider=StubProvider())
    runner = PipelineRunner(
        _run_registry(context, FakeComfyUIProvider()),
        context=context,
        artifact_dir=settings.work_dir,
    )

    async def go() -> None:
        report = await runner.run({"directive": "x"}, job_id="job-pub-2")
        assert report.run_status.value == "complete"
        metadata = json.loads(
            (settings.work_dir / "job-pub-2_metadata.json").read_text(encoding="utf-8")
        )
        assert metadata["title"] == _METADATA_REPLY["title"]
        thumbnail = json.loads(
            (settings.work_dir / "job-pub-2_thumbnail.json").read_text(encoding="utf-8")
        )
        assert thumbnail["file"].endswith("thumbnail.png")
        assert thumbnail["validation"]["status"] == "ok"

    asyncio.run(go())
    assert (settings.work_dir / "thumbnail.png").is_file()