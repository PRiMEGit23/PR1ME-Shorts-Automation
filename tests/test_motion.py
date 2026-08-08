"""Tests for the Motion Graphics subsystem (overlay design stage)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.contracts.motion import MotionGraphicsOutput, MotionOverlay
from pr1me.models.contracts.visual import (
    VisualBranding,
    VisualPlanOutput,
    VisualScene,
    VisualShot,
)
from pr1me.pipeline.runner import PipelineRunner
from pr1me.stages.motion_stage import MotionGraphicsStage, MotionValidationError

logger = logging.getLogger("test-motion")


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


def _input_payload() -> dict:
    plan = _plan()
    return {
        "hook": "Why does the layer lift?",
        "explanation": "Warping cools uneven.",
        "practical_insight": "Add a brim.",
        "ending": "Try it.",
        "shots": [shot.model_dump(mode="json") for shot in plan.shots],
    }


def _settings(tmp_path: Path) -> Settings:
    return Settings(work_dir=tmp_path / "work")


def _context(tmp_path: Path, settings: Settings) -> StageContext:
    return StageContext(
        settings=settings,
        logger=logger,
        prompt_loader=PromptLoader(tmp_path / "prompts"),
    )


# ---------------------------------------------------------------- stage ------


def test_stage_builds_overlays_from_visual_plan(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    stage = MotionGraphicsStage(context=_context(tmp_path, settings))

    async def go() -> None:
        result: MotionGraphicsOutput = await stage.run(_input_payload())
        assert result.total_overlays == 2
        assert result.validation.status.value == "ok"
        assert len(result.overlays) == 2
        assert result.overlays[0].text == "WHY DOES THE"
        assert result.style_used.font == "Inter_Bold"

    asyncio.run(go())


def test_stage_clamps_duration_and_positions_in_safe_zone(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    stage = MotionGraphicsStage(context=_context(tmp_path, settings))

    async def go() -> None:
        result: MotionGraphicsOutput = await stage.run(_input_payload())
        for overlay in result.overlays:
            assert 1.5 <= overlay.duration_seconds <= 4.0
            assert overlay.end_second == pytest.approx(overlay.start_second + overlay.duration_seconds)
            assert overlay.pos_y < 1920 * 0.8, "overlay must stay out of the bottom 20%"

    asyncio.run(go())


def test_stage_caps_overlays_at_five(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    stage = MotionGraphicsStage(context=_context(tmp_path, settings))
    many = _input_payload()
    many["shots"] = [_shot(i, f"subject {i}") for i in range(1, 10)]

    async def go() -> None:
        result: MotionGraphicsOutput = await stage.run(many)
        assert result.total_overlays == 5
        assert result.validation.status.value == "ok"

    asyncio.run(go())


def test_stage_fails_when_no_shots(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    stage = MotionGraphicsStage(context=_context(tmp_path, settings))
    payload = _input_payload()
    payload["shots"] = []

    async def go() -> None:
        with pytest.raises(MotionValidationError, match="no usable visual shots"):
            await stage.run(payload)

    asyncio.run(go())


def test_stage_fails_when_block_has_no_narration(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    stage = MotionGraphicsStage(context=_context(tmp_path, settings))
    payload = _input_payload()
    payload["hook"] = ""

    async def go() -> None:
        with pytest.raises(MotionValidationError, match="no narration"):
            await stage.run(payload)

    asyncio.run(go())


# ------------------------------------------------------------- runner --------


def test_runner_includes_motion_graphics_after_visual(tmp_path: Path) -> None:
    from pr1me.core.base_stage import BaseStage
    from pr1me.models.contracts.base import StageInput, StageOutput

    settings = _settings(tmp_path)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    context = _context(tmp_path, settings)
    plan = _plan()

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
            return ScriptStubOutput(
                hook="Why does the layer lift?",
                explanation="Warping cools uneven.",
                practical_insight="Add a brim.",
                ending="Try it.",
            )

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
            return plan

    registry = StageRegistry(context=context)
    registry.register(ScriptStub(context=context))
    registry.register(VisualStub(context=context))
    registry.register(MotionGraphicsStage(context=context))
    runner = PipelineRunner(registry, context=context, artifact_dir=settings.work_dir)

    async def go() -> None:
        report = await runner.run(plan.model_dump(mode="json"), job_id="job-motion")
        assert report.run_status.value == "complete"
        assert [record.stage_id for record in report.stages] == [
            "script",
            "visual",
            "motion_graphics",
        ]
        artifact = json_load(settings.work_dir / "job-motion_motion_graphics.json")
        assert artifact["total_overlays"] == 2
        assert isinstance(artifact["overlays"][0]["style"], dict)

    asyncio.run(go())


def json_load(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------ contract --------


def test_motion_overlay_contract_rejects_long_duration() -> None:
    with pytest.raises(ValueError):
        MotionOverlay(
            id=1,
            text="TOO LONG",
            start_second=0.0,
            end_second=6.0,
            duration_seconds=6.0,
            pos_x=120.0,
            pos_y=120.0,
            style={"font": "Inter_Bold", "size_px": 96, "color": "#FFF", "accent": "#00E5FF"},
        )
