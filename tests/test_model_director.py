"""Model Director tests (Phase 10): registry, selectors, adapters, switching.

Covers the Universal Multi-Model Generation Engine:

- the registry: eight image + five video models, defaults, future models
- determinism: the same brief always compiles to the same model output
- the whole knowledge base: every row directs to a compatible model plan,
  and the full 400-row run stays within the performance budget
- compatibility: deliberate violations are caught, the matrix is complete
- quality prediction: hero scenes prefer the photoreal leader, macro shots
  prefer macro detail
- selection: quality targets, VRAM budgets, preference ties, replans
- fallback strategy: the chain order and the switch bar (2 failures, +3 QA)
- adapters: every named adapter emits the canonical BackendWorkflow shape,
  and the legacy SDXL workflow shape is a strict subset of it
- the render loop: the directed path switches models after repeated QA
  failure when the fallback predicts a meaningful gain; the legacy path
  never switches
- the pipeline: fifteen stages end-to-end, Model Director artifacts, and
  compiled backend workflows on disk

All providers are injected fakes, so the suite runs offline.
"""

from __future__ import annotations

import csv
import hashlib
import json
import struct
import time
from pathlib import Path

import pytest
from knowledge.ai_director import AIDirector
from knowledge.ai_director.director_models import DirectorOutput
from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.model_director import (
    DEFAULT_MODEL_KEY,
    DEFAULT_VIDEO_MODEL_KEY,
    REGISTRY,
    SWITCH_AFTER_ATTEMPTS,
    ModelDirector,
    ModelKind,
    ModelOutput,
    ModelRegistry,
    ModelSpec,
    chain_exhausted,
    check_model,
    compatibility_matrix,
    expected_qa_score,
    fallback_chain,
    model_count,
    next_fallback,
    replan_for_model,
    should_switch_model,
)
from knowledge.model_director.examples.run_worked_examples import direct_all
from knowledge.visual_architecture import EngineeringDomain, Modality
from knowledge.visual_intelligence.storyboard import ShotType, VisualStoryboard
from runtime.backends import ADAPTER_BY_FAMILY, NAMED_ADAPTERS, adapter_for
from runtime.models import AttemptStatus, RenderResult, SessionConfig
from runtime.pipeline import ProductionPipeline
from runtime.render_loop import RenderLoop
from runtime.renderer import SimulatedRenderer
from runtime.storyboard_builder import StoryboardBuilder
from runtime.workflow_builder import WorkflowBuilder

from pr1me.providers.video_renderer import VideoRender, VideoRenderRequest
from pr1me.providers.voice import VoiceRender

FDM = EngineeringDomain.FDM
PHOTOREAL = Modality.PHOTOREAL

_ED = EducationalDirector()
_AD = AIDirector()
_MD = ModelDirector()
_ROWS = list(csv.DictReader(open("assets/knowledge_base.csv", encoding="utf-8")))

CANONICAL_KEYS = {
    "workflow_version",
    "backend",
    "profile",
    "sampler",
    "scheduler",
    "steps",
    "cfg",
    "resolution",
    "aspect_ratio",
    "vae",
    "loras",
    "negative_tokens",
    "positive_prompt",
    "negative_prompt",
    "controlnet",
    "ip_adapter",
    "depth_strategy",
    "segmentation_strategy",
    "upscaler",
    "refiner",
    "animation_backend",
    "quality_target",
    "nodes",
}


def _brief() -> tuple[EducationalPlan, DirectorOutput, VisualStoryboard]:
    plan = _ED.direct_from_csv(GYROID_ROW)
    brief = _AD.direct(plan)
    board = StoryboardBuilder().build(
        plan, engineering_domain=FDM, modality=PHOTOREAL, director=brief
    )
    return plan, brief, board


def _model_output() -> ModelOutput:
    return _MD.direct(_brief()[1])


# ------------------------------------------------------------------- fakes --


class _FailingRenderer:
    """SimulatedRenderer that fails QA for the first ``fail_first`` renders."""

    def __init__(self, fail_first: int = 2) -> None:
        self._remaining = fail_first
        self._inner = SimulatedRenderer()
        self.calls = 0

    def render(self, request) -> RenderResult:
        self.calls += 1
        result = self._inner.render(request)
        if self._remaining > 0:
            self._remaining -= 1
            metadata = result.metadata.model_copy(
                update={
                    "subject_present": False,
                    "subject_prominence": 0.2,
                    "subject_occluded": True,
                    "engineering_accuracy": 0.3,
                    "geometry_correct": False,
                    "material_correct": False,
                }
            )
            return RenderResult(metadata=metadata, image_bytes=result.image_bytes)
        return result


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


class _FakeVoice:
    """Deterministic voice seam for the pipeline integration test."""

    name = "voice"
    provider_name = "fake-voice"

    async def synthesize(
        self,
        text: str,
        *,
        output_dir: str | Path,
        voice: str | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
    ) -> VoiceRender:
        data = _wav(sample_rate or 22050)
        target = Path(output_dir) / f"narration.{(format_ or 'wav').lstrip('.')}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return VoiceRender(
            file=str(target),
            text=text,
            voice=voice or "default",
            sample_rate=sample_rate or 22050,
            format=(format_ or "wav").lstrip("."),
            duration_seconds=0.01,
            checksum=hashlib.sha256(data).hexdigest(),
        )


class _FakeVideo:
    """Deterministic video renderer seam for the pipeline integration test."""

    name = "video_renderer"
    provider_name = "fake-video"
    codec = "libx264"
    container = "mp4"
    crf = 20
    audio_codec = "aac"
    audio_bitrate_kbps = 192

    async def render(
        self,
        request: VideoRenderRequest,
        *,
        output_dir: str | Path,
        filename: str = "short.mp4",
    ) -> VideoRender:
        data = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 24
        target = Path(output_dir) / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return VideoRender(
            file=str(target),
            fps=request.fps,
            width=request.width,
            height=request.height,
            duration_seconds=6.0,
            size_bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
        )


def _pipeline(run_dir: Path, **overrides):
    defaults: dict = {
        "row": GYROID_ROW,
        "run_dir": run_dir,
        "seed": 42,
        "max_attempts": 3,
        "engineering_domain": FDM,
        "modality": PHOTOREAL,
        "renderer": SimulatedRenderer(),
        "voice_provider": _FakeVoice(),
        "video_renderer_provider": _FakeVideo(),
    }
    defaults.update(overrides)
    return ProductionPipeline(**defaults)


# ----------------------------------------------------------------- registry --


def test_registry_holds_eight_image_and_five_video_models() -> None:
    images, videos = model_count()
    assert images == 8
    assert videos == 5
    image_keys = {spec.key for spec in REGISTRY.of_kind(ModelKind.IMAGE)}
    video_keys = {spec.key for spec in REGISTRY.of_kind(ModelKind.VIDEO)}
    assert image_keys == {
        "flux-dev",
        "flux-schnell",
        "sdxl",
        "juggernaut-xl",
        "realvis-xl",
        "qwen-image",
        "gpt-image",
        "hiredream",
    }
    assert video_keys == {
        "wan-2-2",
        "ltx-video",
        "hunyuan-video",
        "cogvideox",
        "animatediff",
    }


def test_registry_defaults_and_lookup() -> None:
    assert DEFAULT_MODEL_KEY == "sdxl"
    assert DEFAULT_VIDEO_MODEL_KEY == "wan-2-2"
    spec = REGISTRY.get("sdxl")
    assert spec.kind is ModelKind.IMAGE
    assert spec.is_video is False
    assert REGISTRY.get("wan-2-2").kind is ModelKind.VIDEO
    with pytest.raises(KeyError):
        REGISTRY.get("no-such-model")


def test_register_accepts_future_models_and_rejects_duplicates() -> None:
    future = ModelSpec(
        key="future-model",
        name="Future Model",
        family="future",
        kind=ModelKind.IMAGE,
        photoreal=99.0,
        diagram=99.0,
        macro_detail=99.0,
        engineering=99.0,
        adherence=99.0,
        vram_mb=4096,
        speed_factor=2.0,
        reliability=0.99,
        supported_samplers=("euler",),
        supported_schedulers=("normal",),
        supported_vaes=("future-vae",),
        supported_resolutions=("1024x1792",),
    )
    registry = ModelRegistry()
    registry.register(future)
    assert registry.get("future-model").family == "future"
    with pytest.raises(ValueError):
        registry.register(future)


# -------------------------------------------------------------- determinism --


def test_directing_the_same_brief_is_bit_for_bit_deterministic() -> None:
    first = _MD.direct(_brief()[1]).model_dump(mode="json")
    second = _MD.direct(_brief()[1]).model_dump(mode="json")
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# ------------------------------------------------------- whole knowledge base --


def test_every_knowledge_row_directs_to_a_compatible_model_plan() -> None:
    for row in _ROWS:
        plan = _ED.direct_from_csv(row)
        brief = _AD.direct(plan)
        output = _MD.direct(brief)
        assert output.scene_count == len(output.scene_plans)
        for scene_plan in output.scene_plans:
            profile = scene_plan.model_profile
            assert REGISTRY.get(profile.image_model).kind is ModelKind.IMAGE
            assert REGISTRY.get(profile.video_model).kind is ModelKind.VIDEO
            assert 0.0 < scene_plan.expected_qa_score <= 100.0
            assert 0.0 <= scene_plan.expected_success_probability <= 1.0
            assert scene_plan.expected_retry_count >= 1
            assert scene_plan.expected_vram_mb >= 512
            assert scene_plan.estimated_time_seconds > 0.0
            assert scene_plan.workflow_profile is not None
            ModelOutput.model_validate(output.model_dump(mode="json"))


def test_directing_the_whole_knowledge_base_is_fast() -> None:
    started = time.perf_counter()
    for row in _ROWS:
        plan = _ED.direct_from_csv(row)
        brief = _AD.direct(plan)
        _MD.direct(brief)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"directing 400 rows took {elapsed:.2f}s"


# ------------------------------------------------------------ compatibility --


def test_compatibility_checker_flags_deliberate_violations() -> None:
    report = check_model(
        "flux-dev",
        sampler="euler_a",
        scheduler="karras",
        vae="flux-vae",
        resolution="832x1216",
        aspect_ratio="9:16",
        controlnet="canny",
        ip_adapter="style_transfer",
        depth="monocular",
        segmentation="none",
        upscaler="4x_ultrasharp",
        refiner="none",
    )
    assert report.compatible is False
    assert any("sampler 'euler_a'" in message for message in report.violations)
    assert any("scheduler 'karras'" in message for message in report.violations)

    # gpt-image has no ControlNet support at all.
    report = check_model(
        "gpt-image",
        sampler="dpmpp_2m",
        scheduler="normal",
        vae="gpt-image-vae",
        resolution="1024x1792",
        aspect_ratio="9:16",
        controlnet="canny",
    )
    assert report.compatible is False
    assert any("controlnet 'canny'" in message for message in report.violations)

    clean = check_model(
        "sdxl",
        sampler="dpmpp_2m",
        scheduler="karras",
        vae="sdxl-vae-fp16-fix",
        resolution="832x1216",
        aspect_ratio="9:16",
        controlnet="canny",
        ip_adapter="style_transfer",
        depth="monocular",
        segmentation="sam",
        upscaler="esrgan",
        refiner="sdxl-refiner",
    )
    assert clean.compatible is True
    assert clean.violations == ()


def test_compatibility_matrix_covers_every_model_and_axis() -> None:
    matrix = compatibility_matrix()
    assert len(matrix) == 13
    axis = {
        "samplers",
        "schedulers",
        "vaes",
        "resolutions",
        "aspect_ratios",
        "controlnet",
        "ip_adapter",
        "depth",
        "segmentation",
        "upscalers",
        "refiners",
        "animation_backends",
    }
    for row in matrix.values():
        assert set(row) == axis
        assert all(isinstance(cell, bool) for cell in row.values())
    # Image models carry no animation backend; video models carry no upscaler.
    assert matrix["flux-dev"]["animation_backends"] is False
    assert matrix["wan-2-2"]["upscalers"] is True


# ---------------------------------------------------------- quality prediction --


def test_expected_qa_reflects_capability_axes() -> None:
    # Macro shots favor macro detail: flux-dev (90) beats gpt-image (86).
    assert expected_qa_score("flux-dev", ShotType.MACRO) > expected_qa_score(
        "gpt-image", ShotType.MACRO
    )
    # Photoreal hero shots favor the photoreal leader: gpt-image (93) wins.
    assert expected_qa_score("gpt-image", ShotType.HERO) > expected_qa_score(
        "sdxl", ShotType.HERO
    )
    # Blueprint shots reward diagram quality: flux-dev (78) beats gpt (75)
    # despite gpt's higher adherence - the diagram axis decides.
    assert expected_qa_score("flux-dev", ShotType.BLUEPRINT) > expected_qa_score(
        "gpt-image", ShotType.BLUEPRINT
    )


def test_hero_scenes_prefer_the_photoreal_leader() -> None:
    output = _model_output()
    by_id = {plan.scene_id: plan for plan in output.scene_plans}
    assert by_id["S1"].model_profile.image_model == "gpt-image"
    assert by_id["S1"].model_profile.quality_target == "premium"
    assert by_id["S1"].model_profile.video_model == "wan-2-2"
    assert by_id["S1"].expected_qa_score == pytest.approx(92.5, abs=0.5)


# ----------------------------------------------------------------- selectors --


def test_samplers_and_schedulers_clamp_into_supported_sets() -> None:
    output = _model_output()
    for plan in output.scene_plans:
        profile = plan.model_profile
        spec = REGISTRY.get(profile.image_model)
        assert profile.sampler in spec.supported_samplers
        assert profile.scheduler in spec.supported_schedulers
        assert profile.vae in spec.supported_vaes
        assert profile.resolution in spec.supported_resolutions
        assert profile.aspect_ratio in spec.supported_aspect_ratios
        assert profile.controlnet == "none" or profile.controlnet in (
            spec.supported_controlnet
        )
        assert profile.ip_adapter == "none" or profile.ip_adapter in (
            spec.supported_ip_adapters
        )
        assert profile.upscaler in spec.supported_upscalers
        assert profile.refiner in spec.supported_refiners


def test_controlnet_matches_shot_strategy() -> None:
    output = _model_output()
    by_id = {plan.scene_id: plan for plan in output.scene_plans}
    # S2 is the comparison split: canny edge conditioning.
    assert by_id["S2"].model_profile.controlnet == "canny"
    # S3 is the cross section: depth conditioning.
    assert by_id["S3"].model_profile.controlnet == "depth"
    # S4 is the blueprint diagram: lineart conditioning.
    assert by_id["S4"].model_profile.controlnet == "lineart"
    # The hero open is a clean render: no conditioning.
    assert by_id["S1"].model_profile.controlnet == "none"


def test_ip_adapter_kicks_in_for_hero_scenes() -> None:
    output = _model_output()
    by_id = {plan.scene_id: plan for plan in output.scene_plans}
    # gpt-image carries no IPAdapter support, so the hero gets none.
    assert by_id["S1"].model_profile.ip_adapter == "none"
    assert by_id["S2"].model_profile.ip_adapter == "none"
    # Recompiled onto SDXL-family, the hero earns the style transfer.
    hero = replan_for_model(by_id["S1"], "sdxl")
    assert hero.model_profile.ip_adapter == "style_transfer"


def test_replan_for_model_recompiles_for_another_family() -> None:
    plan = _model_output().scene_plans[0]
    assert plan.model_profile.image_model == "gpt-image"
    replanned = replan_for_model(plan, "sdxl")
    assert replanned.scene_id == plan.scene_id
    assert replanned.scene_index == plan.scene_index
    assert replanned.shot_type is plan.shot_type
    assert replanned.is_hero is plan.is_hero
    assert replanned.workflow_profile is plan.workflow_profile
    assert replanned.model_profile.image_model == "sdxl"
    assert replanned.model_profile.quality_target == plan.model_profile.quality_target
    assert replanned.model_profile.sampler == "dpmpp_2m"
    assert replanned.model_profile.vae == "sdxl-vae-fp16-fix"
    assert "fallback recompile for sdxl" in replanned.model_profile.rationale


# ----------------------------------------------------------- model selection --


def test_vram_budget_restricts_candidates() -> None:
    _, brief, _ = _brief()
    output = _MD.direct(brief, vram_budget_mb=11000)
    for plan in output.scene_plans:
        assert plan.expected_vram_mb <= 11000
        assert plan.model_profile.image_model in {"sdxl", "juggernaut-xl", "realvis-xl"}


def test_preferred_model_only_breaks_exact_ties(monkeypatch) -> None:
    # Both "models" carry identical capability records (an exact tie on
    # every shot axis); the preference must decide, registry order alone
    # decides without it.
    twin_a = REGISTRY.get("flux-dev")
    twin_b = twin_a.model_copy(update={"key": "flux-schnell", "name": "FLUX Schnell"})
    specs: dict[str, ModelSpec] = {
        "flux-dev": twin_a,
        "flux-schnell": twin_b,
    }
    specs.update({spec.key: spec for spec in REGISTRY.of_kind(ModelKind.VIDEO)})
    monkeypatch.setattr(REGISTRY, "_specs", specs)

    _, brief, _ = _brief()
    # No preference: registry order wins (flux-dev).
    plain = ModelDirector().direct(brief)
    assert {plan.model_profile.image_model for plan in plain.scene_plans} == {
        "flux-dev"
    }
    # Exact tie, preference on flux-schnell: the preference wins.
    preferred = ModelDirector().direct(brief, preferred_model="flux-schnell")
    assert {plan.model_profile.image_model for plan in preferred.scene_plans} == {
        "flux-schnell"
    }


def test_quality_target_flow() -> None:
    output = _model_output()
    by_id = {plan.scene_id: plan for plan in output.scene_plans}
    assert by_id["S1"].model_profile.quality_target == "premium"  # hero
    assert by_id["S5"].model_profile.quality_target == "premium"  # thumbnail
    assert by_id["S2"].model_profile.quality_target == "balanced"


# ------------------------------------------------------------ fallback chain --


def test_fallback_chain_orders_preferred_first() -> None:
    chain = fallback_chain()
    assert chain[0] == "flux-dev"
    assert len(chain) == 8
    assert next_fallback("sdxl") == "juggernaut-xl"
    assert chain_exhausted("hiredream") is True
    assert next_fallback("hiredream") is None
    preferred = fallback_chain(preferred="sdxl")
    assert preferred[0] == "sdxl"
    assert "sdxl" not in preferred[1:]


def test_switch_requires_enough_failures_and_meaningful_gain() -> None:
    verdict, reason = should_switch_model(
        "sdxl",
        "juggernaut-xl",
        ShotType.HERO,
        consecutive_failures=1,
    )
    assert verdict is False
    assert "consecutive failures" in reason

    verdict, reason = should_switch_model(
        "sdxl",
        "juggernaut-xl",
        ShotType.HERO,
        consecutive_failures=SWITCH_AFTER_ATTEMPTS,
    )
    assert verdict is True
    assert "switching" in reason

    # The best model already: the fallback predicts less, so no switch.
    verdict, reason = should_switch_model(
        "flux-dev",
        "flux-schnell",
        ShotType.CROSS_SECTION,
        consecutive_failures=SWITCH_AFTER_ATTEMPTS,
    )
    assert verdict is False
    assert "improvement bar" in reason


# ------------------------------------------------------------------ adapters --


def test_every_named_adapter_produces_the_canonical_workflow_shape() -> None:
    output = _model_output()
    base = output.scene_plans[0]
    prompt = CompiledPrompt(
        prompt="A hero render of the gyroid infill.",
        negative_prompt="clutter, background objects",
    )
    for model_key in (
        "flux-dev",
        "flux-schnell",
        "sdxl",
        "juggernaut-xl",
        "realvis-xl",
        "qwen-image",
        "gpt-image",
        "hiredream",
    ):
        scene_plan = replan_for_model(base, model_key)
        workflow = WorkflowBuilder().build_from_directive(
            prompt=prompt, plan=scene_plan
        )
        assert CANONICAL_KEYS.issubset(workflow.keys())
        assert workflow["backend"] == adapter_for(model_key).backend
        assert workflow["quality_target"] == "premium"
        assert workflow["positive_prompt"] == prompt.prompt


def test_every_named_adapter_is_registered_and_dispatched() -> None:
    assert set(NAMED_ADAPTERS) == {
        "flux",
        "sdxl",
        "qwen",
        "gpt_image",
        "wan",
        "ltx",
        "cogvideo",
        "animatediff",
    }
    assert adapter_for("flux-dev") is ADAPTER_BY_FAMILY["flux"]
    assert adapter_for("gpt-image") is ADAPTER_BY_FAMILY["gpt_image"]
    assert adapter_for("hiredream") is not None  # generic fallback
    assert adapter_for("no-such-model") is not None  # generic fallback


# --------------------------------------------------------------- render loop --


def _directed_scene_run(
    renderer, scene_plan, *, max_attempts: int = 5, seed: int = 42
):
    plan, brief, board = _brief()
    loop = RenderLoop(renderer=renderer)
    cfg = SessionConfig(model_key="sdxl", max_attempts=max_attempts)
    return loop.run(
        plan=plan,
        storyboard=board,
        scene=board.scenes[0],
        topic=brief.topic,
        seed=seed,
        config=cfg,
        directive=scene_plan,
    )


def test_directed_loop_switches_model_after_two_failures() -> None:
    _, _, board = _brief()
    output = _MD.direct(_brief()[1])
    hero_plan = replan_for_model(output.scene_plans[0], "sdxl")
    assert hero_plan.model_profile.image_model == "sdxl"

    renderer = _FailingRenderer(fail_first=2)
    result = _directed_scene_run(renderer, hero_plan, max_attempts=5)

    statuses = [attempt.status for attempt in result.attempts]
    assert statuses == [
        AttemptStatus.FAILED,
        AttemptStatus.FAILED,
        AttemptStatus.MODEL_SWITCHED,
        AttemptStatus.PASSED,
    ]
    switch = result.attempts[2]
    assert switch.image_model == "juggernaut-xl"
    assert "switching" in switch.rationale
    # The post-switch render runs the recompiled backend workflow.
    passed = result.attempts[3]
    assert passed.image_model == "juggernaut-xl"
    assert passed.workflow["backend"] == "sdxl"
    assert passed.status is AttemptStatus.PASSED


def test_directed_loop_keeps_model_when_fallback_is_not_better() -> None:
    _, _, board = _brief()
    output = _MD.direct(_brief()[1])
    # S2's best model (flux-dev) already out-scores every fallback.
    hero_plan = output.scene_plans[1]

    renderer = _FailingRenderer(fail_first=999)
    result = _directed_scene_run(renderer, hero_plan, max_attempts=5)

    assert all(attempt.status is AttemptStatus.FAILED for attempt in result.attempts)
    assert not any(
        attempt.status is AttemptStatus.MODEL_SWITCHED for attempt in result.attempts
    )
    assert {attempt.image_model for attempt in result.attempts} == {"flux-dev"}


def test_legacy_loop_never_switches_models() -> None:
    plan, brief, board = _brief()
    renderer = _FailingRenderer(fail_first=999)
    loop = RenderLoop(renderer=renderer)
    cfg = SessionConfig(model_key="sdxl", max_attempts=5)
    result = loop.run(
        plan=plan,
        storyboard=board,
        scene=board.scenes[0],
        topic=brief.topic,
        seed=42,
        config=cfg,
    )
    assert all(attempt.status is AttemptStatus.FAILED for attempt in result.attempts)
    assert not any(
        attempt.status is AttemptStatus.MODEL_SWITCHED for attempt in result.attempts
    )
    assert all(attempt.image_model is None for attempt in result.attempts)


# -------------------------------------------------------------- pipeline e2e --


@pytest.mark.asyncio
async def test_pipeline_has_fifteen_stages_with_model_director(tmp_path) -> None:
    run_dir = tmp_path / "run"
    result = await _pipeline(run_dir).run()

    assert result.status == "complete"
    report = json.loads((run_dir / "reports" / "execution_report.json").read_text(encoding="utf-8"))
    stage_ids = [stage["stage_id"] for stage in report["stages"]]
    assert len(stage_ids) == 15
    assert stage_ids[2] == "ai_director"
    assert stage_ids[3] == "visual_intelligence"
    assert stage_ids[4] == "model_director"
    assert stage_ids[5] == "prompt_compiler"

    outputs = list((run_dir / "artifacts" / "model_director").glob("output.*.json"))
    assert outputs, "expected a persisted Model Director output artifact"
    model_output = json.loads(outputs[0].read_text(encoding="utf-8"))
    assert model_output["version"] == "10.0.0"
    assert len(model_output["scene_plans"]) == 5
    by_id = {plan["scene_id"]: plan for plan in model_output["scene_plans"]}
    assert by_id["S1"]["model_profile"]["image_model"] == "gpt-image"
    assert by_id["S1"]["model_profile"]["quality_target"] == "premium"


@pytest.mark.asyncio
async def test_pipeline_workflows_carry_the_compiled_backend(tmp_path) -> None:
    run_dir = tmp_path / "run"
    await _pipeline(run_dir).run()

    for scene_id in ("S1", "S2", "S3", "S4", "S5"):
        workflow = json.loads(
            (run_dir / "workflow" / f"{scene_id}.json").read_text(encoding="utf-8")
        )
        assert workflow["backend"] in {"gpt_image", "flux"}
        assert workflow["vae"] in {"gpt-image-vae", "flux-vae"}
        assert workflow["quality_target"] in {"premium", "balanced"}


# ---------------------------------------------------------- worked examples --


def test_worked_examples_compile_model_outputs() -> None:
    outputs = direct_all()
    assert list(outputs) == ["gyroid", "planetary_gear", "injection_molding"]
    for output in outputs.values():
        ModelOutput.model_validate(output.model_dump(mode="json"))
        assert output.version == "10.0.0"
        for plan in output.scene_plans:
            assert REGISTRY.get(plan.model_profile.image_model).kind is ModelKind.IMAGE
