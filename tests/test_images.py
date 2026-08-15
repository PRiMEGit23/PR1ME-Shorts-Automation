"""Tests for the Image Generation subsystem (ComfyUI provider + stage)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest

from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.errors import ProviderNotConfiguredError
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.image import ImageManifestOutput
from pr1me.models.contracts.visual import (
    VisualBranding,
    VisualPlanOutput,
    VisualScene,
    VisualShot,
)
from pr1me.models.contracts.workflow import WorkflowFrame
from pr1me.pipeline.runner import PipelineRunner
from pr1me.providers.comfyui import (
    ComfyUIExecutionError,
    ComfyUIProvider,
    ComfyUIQueueError,
    ComfyUIRender,
    ComfyUITimeoutError,
    inject_variables,
    parse_queue_response,
    png_dimensions,
)
from pr1me.stages.image_generation_stage import ImageGenerationStage

logger = logging.LoggerAdapter(logging.getLogger("test-images"), {})

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


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
        shots=[_shot(1, "first layer"), _shot(2, "layer adhesion")],
        branding=VisualBranding(use_logo=True, use_broll=False, broll_source=None),
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "work")


def _context(tmp_path: Path, settings: Settings) -> StageContext:
    return StageContext(
        settings=settings,
        logger=logger,
        prompt_loader=PromptLoader(tmp_path / "prompts"),
    )


# ------------------------------------------------------------- injection ----


def test_inject_variables_typed_and_preserves_source() -> None:
    workflow: dict[str, Any] = {
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": "{seed}", "steps": "{steps}", "cfg": "{cfg}"},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a {positive_prompt} render"},
        },
    }
    result = inject_variables(workflow, {"seed": 424242, "positive_prompt": "cross-section PLA"})
    assert result["3"]["inputs"]["seed"] == 424242
    assert result["3"]["inputs"]["steps"] == "{steps}", "unknown placeholder preserved"
    assert result["6"]["inputs"]["text"] == "a cross-section PLA render"
    assert workflow["3"]["inputs"]["seed"] == "{seed}", "source workflow must not mutate"


def test_inject_variables_unknown_placeholder_stays() -> None:
    workflow = {"5": {"class_type": "EmptyLatentImage", "inputs": {"width": "{width}"}}}
    result = inject_variables(workflow, {"seed": 1})
    assert result["5"]["inputs"]["width"] == "{width}"


def test_parse_queue_response_ok() -> None:
    parsed = parse_queue_response({"prompt_id": "abc", "number": 2, "node_errors": {}})
    assert parsed.prompt_id == "abc"
    assert parsed.number == 2


def test_parse_queue_response_rejects_node_errors() -> None:
    with pytest.raises(ComfyUIQueueError, match="node errors"):
        parse_queue_response({"prompt_id": "abc", "node_errors": {"6": {"x": "y"}}})


def test_parse_queue_response_missing_id() -> None:
    with pytest.raises(ComfyUIQueueError, match="prompt_id"):
        parse_queue_response({"number": 1})


# ----------------------------------------------------------------- png -------


def test_png_dimensions() -> None:
    assert png_dimensions(PNG_1X1) == (1, 1)
    assert png_dimensions(b"not a png") == (0, 0)


# ----------------------------------------------------------------- provider ---


def _history_body(prompt_id: str, *, error: str | None = None) -> dict[str, Any]:
    status: dict[str, Any] = {"completed": True, "status_str": "success"}
    if error is not None:
        status["messages"] = [["execution_error", {"exception_message": error}]]
    return {
        prompt_id: {
            "status": status,
            "outputs": {
                "9": {"images": [{"filename": "pr1me_00001_.png", "subfolder": "", "type": "output"}]}
            },
        }
    }


def _comfy_transport(
    *,
    queue_tries: int = 1,
    history_error: str | None = None,
) -> httpx.MockTransport:
    calls = {"queue": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            calls["queue"] += 1
            if calls["queue"] < queue_tries:
                return httpx.Response(503, content=b"")
            return httpx.Response(200, json={"prompt_id": "mock-1234", "number": 1})
        if request.url.path.startswith("/history/"):
            return httpx.Response(200, json=_history_body("mock-1234", error=history_error))
        if request.url.path == "/view":
            return httpx.Response(200, content=PNG_1X1)
        return httpx.Response(404, content=b"")

    return httpx.MockTransport(handler)


def _provider(
    transport: httpx.MockTransport,
    *,
    timeout_seconds: float | None = None,
    poll_interval: float | None = None,
    max_retries: int | None = None,
    retry_base_delay: float | None = None,
) -> ComfyUIProvider:
    return ComfyUIProvider(
        base_url="http://comfyui.local",
        workflow_file=Path("workflows/comfyui.json"),
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        max_retries=max_retries,
        retry_base_delay=retry_base_delay,
        http_client=httpx.AsyncClient(transport=transport),
    )


def test_render_saves_image_to_output_dir(tmp_path: Path) -> None:
    rendered_holder: list[ComfyUIRender] = []

    async def go() -> None:
        provider = _provider(_comfy_transport())
        rendered = await provider.render(
            {"positive_prompt": "cross-section PLA", "seed": 7},
            output_dir=str(tmp_path / "out"),
        )
        assert len(rendered) == 1
        assert rendered[0].width == 1
        assert rendered[0].prompt_id == "mock-1234"
        rendered_holder.append(rendered[0])
        await provider.close()

    asyncio.run(go())
    path = Path(rendered_holder[0].file)
    assert path.parent == tmp_path / "out"
    assert path.is_file()
    assert path.read_bytes() == PNG_1X1


def test_workflow_load_from_file(tmp_path: Path) -> None:
    workflow_file = tmp_path / "comfyui.json"
    workflow_file.write_text(json.dumps({"4": {"class_type": "KSampler", "inputs": {"x": 1}}}))

    async def go() -> None:
        provider = ComfyUIProvider(workflow_file=workflow_file)
        graph = await provider.load_workflow()
        assert graph["4"]["class_type"] == "KSampler"
        await provider.close()

    asyncio.run(go())


def test_queue_retries_transient_failure(tmp_path: Path) -> None:
    async def go() -> None:
        provider = _provider(
            _comfy_transport(queue_tries=2),
            max_retries=3,
            retry_base_delay=0.01,
        )
        rendered = await provider.render({"positive_prompt": "x"}, output_dir=tmp_path)
        assert rendered
        await provider.close()

    asyncio.run(go())


def test_execution_error_raises(tmp_path: Path) -> None:
    async def go() -> None:
        provider = _provider(_comfy_transport(history_error="KSampler exploded"))
        with pytest.raises(ComfyUIExecutionError, match="KSampler exploded"):
            await provider.render({"positive_prompt": "x"}, output_dir=tmp_path)
        await provider.close()

    asyncio.run(go())


def test_execution_timeout_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async def go() -> None:
        provider = ComfyUIProvider(
            base_url="http://comfyui.local",
            workflow_file=Path("workflows/comfyui.json"),
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            timeout_seconds=0.05,
            poll_interval=0.01,
        )
        with pytest.raises(ComfyUITimeoutError):
            await provider.wait("never-done")
        await provider.close()

    asyncio.run(go())


def test_missing_workflow_file_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(ProviderNotConfiguredError, match="workflow file not found"):
        ComfyUIProvider(workflow_file=tmp_path / "missing.json")


# ------------------------------------------------------------- stage ---------


class FakeComfyUIProvider(ComfyUIProvider):
    """Records render calls and returns a tiny PNG for every render."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @property
    def workflow_name(self) -> str:
        return "comfyui.json"

    async def render(
        self,
        variables: dict[str, Any],
        *,
        output_dir: str | Path,
        workflow: Any = None,  # noqa: ARG002
    ) -> list[ComfyUIRender]:
        dest = Path(output_dir)
        await asyncio.to_thread(dest.mkdir, parents=True, exist_ok=True)
        name = f"render_{len(self.calls):02d}.png"
        await asyncio.to_thread((dest / name).write_bytes, PNG_1X1)
        self.calls.append(dict(variables))
        return [ComfyUIRender(file=str(dest / name), prompt_id="mock", width=1, height=1)]


class EmptyComfyUIProvider(FakeComfyUIProvider):
    async def render(
        self,
        variables: dict[str, Any],
        *,
        output_dir: str | Path,
        workflow: Any = None,  # noqa: ARG002
    ) -> list[ComfyUIRender]:
        return []


def _frame(shot_id: int, block: str) -> WorkflowFrame:
    return WorkflowFrame(
        shot_id=shot_id,
        block=block,
        start_second=(shot_id - 1) * 6.0,
        end_second=shot_id * 6.0,
        duration_seconds=6.0,
        positive_prompt=f"validated prompt for shot {shot_id}",
        negative_prompt="hygiene negatives",
        camera="low angle, macro 100mm, push-in",
        composition="centered",
        lighting="studio",
        style="technical render",
        motion="slow push-in",
        transition="cut",
        validation_score=100,
        width=1080,
        height=1920,
        seed=424242 + shot_id * 7919,
        steps=28,
        cfg=7.0,
        sampler="euler_a",
        scheduler="karras",
    )


def test_stage_renders_every_shot_in_order(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    context = _context(tmp_path, settings)
    fake = FakeComfyUIProvider()
    stage = ImageGenerationStage(context=context, comfyui_provider=fake)

    async def go() -> None:
        result: ImageManifestOutput = await stage.run(_plan().model_dump(mode="json"))
        assert result.total == 2
        assert [asset.shot_id for asset in result.images] == [1, 2]
        assert result.validation.status.value == "ok"
        assert len(fake.calls) == 2
        first = fake.calls[0]
        assert "first layer" in first["positive_prompt"]
        assert first["width"] == settings.target_width

    asyncio.run(go())


def test_stage_renders_validated_frames_in_order(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    context = _context(tmp_path, settings)
    fake = FakeComfyUIProvider()
    stage = ImageGenerationStage(context=context, comfyui_provider=fake)

    async def go() -> None:
        result: ImageManifestOutput = await stage.run(
            {
                "total_seconds": 12.0,
                "shots": [],
                "branding": {"use_logo": True, "use_broll": True, "broll_source": None},
                "frames": [_frame(1, "hook"), _frame(2, "explanation")],
            }
        )
        assert result.total == 2
        assert [asset.shot_id for asset in result.images] == [1, 2]
        assert result.validation.status.value == "ok"
        assert len(fake.calls) == 2
        first = fake.calls[0]
        assert first["positive_prompt"] == "validated prompt for shot 1"
        assert first["seed"] == 424242 + 7919
        assert first["steps"] == 28
        assert first["width"] == 1080
        metadata = result.images[0].metadata
        assert metadata.block == "hook"
        assert metadata.start_second == 0.0
        assert metadata.end_second == 6.0
        assert metadata.positive_prompt == "validated prompt for shot 1"

    asyncio.run(go())


def test_stage_prefers_frames_over_legacy_plan_when_flag_off(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    context = _context(tmp_path, settings)
    fake = FakeComfyUIProvider()
    stage = ImageGenerationStage(context=context, comfyui_provider=fake)

    async def go() -> None:
        result: ImageManifestOutput = await stage.run(
            {
                "total_seconds": 12.0,
                "shots": [_shot(1, "legacy subject")],
                "branding": {"use_logo": True, "use_broll": True, "broll_source": None},
                "frames": [_frame(1, "hook")],
            }
        )
        assert result.total == 1
        assert fake.calls[0]["positive_prompt"] == "validated prompt for shot 1"
        assert "legacy subject" not in fake.calls[0]["positive_prompt"]

    asyncio.run(go())


def test_stage_legacy_flag_forces_visual_plan_prompts(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.use_legacy_image_prompts = True
    context = _context(tmp_path, settings)
    fake = FakeComfyUIProvider()
    stage = ImageGenerationStage(context=context, comfyui_provider=fake)

    async def go() -> None:
        result: ImageManifestOutput = await stage.run(
            {
                "total_seconds": 12.0,
                "shots": [_shot(1, "legacy subject")],
                "branding": {"use_logo": True, "use_broll": True, "broll_source": None},
                "frames": [_frame(1, "hook")],
            }
        )
        assert result.total == 1
        assert "legacy subject" in fake.calls[0]["positive_prompt"]

    asyncio.run(go())


def test_stage_preserves_shot_ordering_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    stage = ImageGenerationStage(
        context=_context(tmp_path, settings),
        comfyui_provider=FakeComfyUIProvider(),
    )

    async def go() -> None:
        result: ImageManifestOutput = await stage.run(_plan().model_dump(mode="json"))
        files = [Path(asset.file).name for asset in result.images]
        assert files == ["shot_001.png", "shot_002.png"]

    asyncio.run(go())


def test_stage_fails_when_render_returns_nothing(tmp_path: Path) -> None:
    from pr1me.stages.image_generation_stage import ImageValidationError

    settings = _settings(tmp_path)
    stage = ImageGenerationStage(
        context=_context(tmp_path, settings),
        comfyui_provider=EmptyComfyUIProvider(),
    )

    async def go() -> None:
        with pytest.raises(ImageValidationError, match="rendered no images"):
            await stage.run(_plan().model_dump(mode="json"))

    asyncio.run(go())


def test_runner_includes_image_generation_after_workflow_builder(tmp_path: Path) -> None:
    from pr1me.core.base_stage import BaseStage
    from pr1me.models.contracts.base import StageInput, StageOutput

    settings = _settings(tmp_path)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    context = _context(tmp_path, settings)

    class BuilderInput(StageInput):
        model_config = {"extra": "ignore"}

    class BuilderOutput(StageOutput):
        frames: list[WorkflowFrame] = []
        total: int = 0
        validation: ValidationDescriptor = ValidationDescriptor()

    class WorkflowBuilderStub(BaseStage[BuilderInput, BuilderOutput]):
        stage_id = "workflow_builder"
        name = "Workflow Builder Stub"
        depends_on: tuple = ()
        input_model = BuilderInput
        output_model = BuilderOutput

        async def execute(self, payload: BuilderInput) -> BuilderOutput:  # noqa: ARG002
            return BuilderOutput(
                frames=[_frame(1, "hook"), _frame(2, "hook")],
                total=2,
            )

    registry = StageRegistry(context=context)
    registry.register(WorkflowBuilderStub(context=context))
    registry.register(ImageGenerationStage(context=context, comfyui_provider=FakeComfyUIProvider()))
    runner = PipelineRunner(registry, context=context, artifact_dir=settings.work_dir)

    async def go() -> None:
        report = await runner.run(_plan().model_dump(mode="json"), job_id="job-img")
        assert report.run_status.value == "complete"
        assert [record.stage_id for record in report.stages] == [
            "workflow_builder",
            "image_generation",
        ]
        assert (settings.work_dir / "images" / "shot_001.png").is_file()

    asyncio.run(go())
