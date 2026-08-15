"""The fifteen production stages: CSV row -> publish-ready Short.

This module implements the mission pipeline exactly:

    CSV Knowledge Row -> Knowledge Loader -> Educational Director ->
    AI Director (Phase 8: the deterministic creative decision engine) ->
    Visual Intelligence (produces the VisualStoryboard; the mission's
    separate "Storyboard" step is one transformation) ->
    Model Director (Phase 10: the deterministic multi-model engine) ->
    Prompt Compiler -> Workflow Builder (compiles from the Model Profile)
    -> Runtime Render Loop (approved images) -> Voice Generation ->
    Subtitle Generation -> Video Assembly -> Video Render ->
    Thumbnail Selection -> Metadata Generation -> Publisher

Everything is deterministic: no LLM calls, no randomness, no clock-driven
decisions. The knowledge layers, the Educational Director, the AI
Director, the Model Director, Visual Intelligence, the prompt compiler,
and the Phase 6 runtime engine are used as-is; this module only wires
them into stages. Providers (voice, video renderer, YouTube) are injected
seams so tests can fake them and production can configure them through
``PR1ME_*`` environment variables.

Each stage declares the exact inputs its output depends on (:meth:`Stage.inputs`)
so the fingerprinting resume logic can prove a stage is already done.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from knowledge.ai_director import AIDirector
from knowledge.ai_director.director_models import DirectorOutput
from knowledge.compiler import compile_for_storyboard
from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.model_director import ModelDirector
from knowledge.model_director.model_profiles import ModelOutput
from knowledge.visual_intelligence.storyboard import VisualStoryboard
from knowledge.visual_intelligence.visual_intelligence import KnowledgeBaseRow

from pr1me.providers.video_renderer import (
    RenderSegment,
    VideoRendererProvider,
    VideoRenderRequest,
)
from pr1me.providers.voice import VoiceProvider
from pr1me.providers.youtube import YouTubeProvider, YouTubeUploadRequest, youtube_category_id
from runtime.models import RenderSessionResult, SessionConfig
from runtime.pipeline_context import PipelineContext
from runtime.render_loop import RenderLoop
from runtime.renderer import Renderer
from runtime.stage_runner import Stage, StageError
from runtime.storyboard_builder import StoryboardBuilder
from runtime.workflow_builder import WorkflowBuilder

# ------------------------------------------------------------------ narration --


def compose_narration(plan: EducationalPlan) -> str:
    """Deterministic narration text from the plan (no LLM).

    The narration is the plan's attention hook, the knowledge-flow concepts
    in order, and the final takeaway - joined into one flowing sentence.
    """
    concepts = " ".join(step.concept for step in plan.knowledge_flow)
    parts = [plan.attention_hook, concepts, plan.final_takeaway]
    return " ".join(part.strip() for part in parts if part.strip())


# ------------------------------------------------------------------ subtitles --


def _split_sentences(text: str) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text)]
    return [part for part in sentences if part]


def build_srt(text: str, duration_seconds: float) -> str:
    """Deterministic SRT subtitles: sentences spread by word share.

    Each sentence is timed proportionally to its word count over the total
    narration duration, so identical text + duration always yields the same
    subtitle file.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    words = [len(part.split()) for part in sentences]
    total_words = sum(words) or 1
    blocks: list[str] = []
    start = 0.0
    for index, (sentence, count) in enumerate(zip(sentences, words, strict=True), start=1):
        share = count / total_words
        end = min(start + share * duration_seconds, duration_seconds)
        blocks.append(
            f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{sentence}\n"
        )
        start = end
    return "\n".join(blocks)


def _srt_time(seconds: float) -> str:
    ms = round(max(0.0, seconds) * 1000.0)
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, msecs = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"


def _copy_file(source: Path, target: Path) -> None:
    """Copy one file (run in a worker thread by async stages)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


# ------------------------------------------------------------- stage 1: load --


class KnowledgeLoadStage(Stage):
    """CSV row -> canonical knowledge row (validated, fail-fast)."""

    stage_id = "knowledge_load"
    name = "Knowledge Loader"
    version = "1.0.0"
    description = "Loads and validates one Knowledge Base CSV row."
    dependencies: tuple[str, ...] = ()

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {"row": ctx.row}

    async def execute(self, ctx: PipelineContext) -> Any:
        # Fail-fast validation: an invalid row never reaches the director.
        KnowledgeBaseRow.from_csv_row(ctx.row)
        return dict(ctx.row)


# ------------------------------------------------------------ stage 2: plan --


class EducationalDirectorStage(Stage):
    """Knowledge row -> EducationalPlan (deterministic knowledge layer)."""

    stage_id = "educational_director"
    name = "Educational Director"
    version = "1.0.0"
    description = "Directs the educational strategy for the row."
    dependencies = ("knowledge_load",)

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {"row": ctx.stage_output("knowledge_load")}

    async def execute(self, ctx: PipelineContext) -> Any:
        row = ctx.stage_output("knowledge_load")
        plan = EducationalDirector().direct_from_csv(row)
        return plan.model_dump(mode="json")


# --------------------------------------------------- stage 3: AI Director --


class AIDirectorStage(Stage):
    """EducationalPlan -> DirectorOutput (the deterministic creative brief).

    Phase 8: the AI Director decides the arc, per-scene budgets, cinematic
    plans, hero / thumbnail / recap scenes, reveal / pacing / emotion
    profiles, and predicted attention / retention - before any prompt is
    generated. It is not an LLM: every decision is a pure function of the
    plan.
    """

    stage_id = "ai_director"
    name = "AI Director"
    version = "1.0.0"
    description = "Directs the EducationalPlan into a full creative brief."
    dependencies = ("educational_director",)

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {"plan": ctx.stage_output("educational_director")}

    async def execute(self, ctx: PipelineContext) -> Any:
        plan = EducationalPlan.model_validate(ctx.stage_output("educational_director"))
        output = AIDirector().direct(plan)
        return output.model_dump(mode="json")


# -------------------------------------------------- stage 4: visual+storyboard --

class VisualIntelligenceStage(Stage):
    """DirectorOutput -> VisualStoryboard (visual intelligence + storyboard).

    The mission's "Visual Intelligence" and "Storyboard" steps are one
    deterministic transformation: the StoryboardBuilder adapter translates
    the AI Director's brief onto the storyboard scenes verbatim, so no
    creative heuristic lives here.
    """

    stage_id = "visual_intelligence"
    name = "Visual Intelligence"
    version = "1.0.0"
    description = "Translates the AI Director's brief onto a VisualStoryboard."
    dependencies = ("educational_director", "ai_director")

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {
            "plan": ctx.stage_output("educational_director"),
            "director": ctx.stage_output("ai_director"),
            "engineering_domain": ctx.engineering_domain.value,
            "modality": ctx.modality.value,
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        plan = EducationalPlan.model_validate(ctx.stage_output("educational_director"))
        director = DirectorOutput.model_validate(ctx.stage_output("ai_director"))
        storyboard = StoryboardBuilder().build(
            plan,
            engineering_domain=ctx.engineering_domain,
            modality=ctx.modality,
            director=director,
        )
        return storyboard.model_dump(mode="json")


# --------------------------------------------------------- stage 5: model dir --


class ModelDirectorStage(Stage):
    """DirectorOutput + storyboard -> ModelOutput (the compiled backends).

    Phase 10: for every scene the Model Director deterministically picks
    the best image model, video model, VAE, sampler, scheduler, CFG,
    resolution, aspect ratio, render profile, LoRA set, ControlNet /
    IPAdapter / depth / segmentation strategy, upscaler, refiner, and
    animation backend, and predicts VRAM, time, QA, success probability,
    and retry count - before any prompt is generated. The workflow
    builder and render loop consume these plans; no backend-specific
    logic lives outside the knowledge tables and the backend adapters.
    """

    stage_id = "model_director"
    name = "Model Director"
    version = "1.0.0"
    description = "Compiles the deterministic multi-model plan for every scene."
    dependencies = ("ai_director", "visual_intelligence")

    def __init__(
        self,
        *,
        preferred_model: str | None = None,
        vram_budget_mb: int | None = None,
    ) -> None:
        self._preferred_model = preferred_model
        self._vram_budget_mb = vram_budget_mb

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {
            "director": ctx.stage_output("ai_director"),
            "storyboard": ctx.stage_output("visual_intelligence"),
            "preferred_model": self._preferred_model or ctx.model_key,
            "vram_budget_mb": self._vram_budget_mb,
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        director = DirectorOutput.model_validate(ctx.stage_output("ai_director"))
        output = ModelDirector().direct(
            director,
            preferred_model=self._preferred_model or ctx.model_key,
            vram_budget_mb=self._vram_budget_mb,
        )
        return output.model_dump(mode="json")

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        output = ctx.outputs.get(self.stage_id, {})
        models: list[str] = []
        for plan in output.get("scene_plans", []):
            models.append(plan["model_profile"]["image_model"])
        return {
            "token_usage": 0,
            "model_usage": ", ".join(dict.fromkeys(models)),
            "scene_count": output.get("scene_count", 0),
        }


# --------------------------------------------------------- stage 5: compiler --


class PromptCompilerStage(Stage):
    """VisualStoryboard -> compiled prompts for the configured model."""

    stage_id = "prompt_compiler"
    name = "Prompt Compiler"
    version = "1.0.0"
    description = "Compiles the storyboard into model-ready prompts."
    dependencies = ("visual_intelligence",)

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {
            "storyboard": ctx.stage_output("visual_intelligence"),
            "model_key": ctx.model_key,
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        storyboard = VisualStoryboard.model_validate(ctx.stage_output("visual_intelligence"))
        compiled = compile_for_storyboard(storyboard, ctx.model_key, topic=ctx.topic)
        return compiled.model_dump(mode="json")


# ---------------------------------------------------------- stage 5: workflow --


class WorkflowBuilderStage(Stage):
    """Model plans + compiled prompts -> one backend workflow per scene.

    Phase 10: each workflow compiles from the Model Director's
    SceneModelPlan (the compiled backend profile) through the backend
    adapters - no backend-specific logic lives in this stage. The legacy
    builder path remains for tests and direct use.
    """

    stage_id = "workflow_builder"
    name = "Workflow Builder"
    version = "1.0.0"
    description = "Compiles the model plans into backend workflow JSON."
    dependencies = ("prompt_compiler", "visual_intelligence", "model_director")

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {
            "compiled": ctx.stage_output("prompt_compiler"),
            "storyboard": ctx.stage_output("visual_intelligence"),
            "model_plans": ctx.stage_output("model_director"),
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        compiled = ctx.stage_output("prompt_compiler")
        storyboard = VisualStoryboard.model_validate(ctx.stage_output("visual_intelligence"))
        model_output = ModelOutput.model_validate(ctx.stage_output("model_director"))
        builder = WorkflowBuilder()
        workflows: dict[str, Any] = {}
        for scene in storyboard.scenes:
            plan = model_output.plan_for(scene.scene_id)
            prompt = CompiledPrompt.model_validate(compiled["scenes"][scene.scene_id])
            workflows[scene.scene_id] = builder.build_from_directive(
                prompt=prompt, plan=plan
            )
        self._write_workflows(ctx, workflows)
        return workflows

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        workflows = ctx.outputs.get(self.stage_id, {})
        backends = [
            workflow.get("backend", "")
            for workflow in workflows.values()
        ]
        return {
            "token_usage": 0,
            "model_usage": ", ".join(dict.fromkeys(b for b in backends if b)),
        }

    @staticmethod
    def _write_workflows(ctx: PipelineContext, workflows: dict[str, Any]) -> None:
        for scene_id, workflow in workflows.items():
            path = ctx.workflow_dir / f"{scene_id}.json"
            path.write_text(json.dumps(workflow, indent=2, sort_keys=True), encoding="utf-8")


# ---------------------------------------------------------- stage 6: render --


class RenderLoopStage(Stage):
    """The closed-loop render engine: approved images per scene.

    This is the ComfyUI touch point: the injected :class:`Renderer` stands in
    for a live ComfyUI deployment, and a renderer failure here is the classic
    "ComfyUI crash" resume scenario. The approved (winner) image of every
    scene is copied to ``<run_dir>/images/<scene_id>.png``.

    Phase 10: every scene renders with its Model Director plan (the
    compiled backend profile); on repeated QA failures the loop's
    deterministic fallback strategy may switch the image model (recorded
    as ``model_switched`` attempts and visible in the metrics).
    """

    stage_id = "render_loop"
    name = "Runtime Render Loop"
    version = "1.0.0"
    description = "Closed-loop render -> QA -> optimize -> re-render per scene."
    dependencies = ("visual_intelligence", "prompt_compiler", "model_director")

    def __init__(self, renderer: Renderer) -> None:
        self._renderer = renderer

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        storyboard = ctx.stage_output("visual_intelligence")
        return {
            "row": ctx.row,
            "seed": ctx.seed,
            "max_attempts": ctx.max_attempts,
            "model_key": ctx.model_key,
            "engineering_domain": ctx.engineering_domain.value,
            "modality": ctx.modality.value,
            "scene_ids": [scene["scene_id"] for scene in storyboard["scenes"]],
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        storyboard = VisualStoryboard.model_validate(ctx.stage_output("visual_intelligence"))
        model_output = ModelOutput.model_validate(ctx.stage_output("model_director"))
        results: dict[str, Any] = {}
        for index, scene in enumerate(storyboard.scenes):
            scene_seed = ctx.seed + index
            loop = RenderLoop(renderer=self._renderer)
            plan = EducationalPlan.model_validate(ctx.stage_output("educational_director"))
            result = loop.run(
                plan=plan,
                storyboard=storyboard,
                scene=scene,
                topic=ctx.topic,
                seed=scene_seed,
                config=SessionConfig(
                    output_root=ctx.history_dir,
                    max_attempts=ctx.max_attempts,
                    model_key=ctx.model_key,
                ),
                directive=model_output.plan_for(scene.scene_id),
            )
            self._save_approved(ctx, scene.scene_id, result)
            results[scene.scene_id] = self._serialize_scene_result(scene.scene_id, result)
        return results

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        results = ctx.outputs.get(self.stage_id, {})
        attempts = 0
        qa_scores: list[float] = []
        optimization_rounds = 0
        final_scores: dict[str, float] = {}
        profiles: list[str] = []
        models: list[str] = []
        for scene_id, payload in results.items():
            attempts += payload["attempts"]
            qa_scores.extend(payload["qa_scores"])
            optimization_rounds += payload["optimization_rounds"]
            final_scores[scene_id] = payload["final_qa_score"]
            profiles.append(payload["render_profile"])
            if payload.get("image_model"):
                models.append(payload["image_model"])
        return {
            "token_usage": 0,
            "model_usage": ", ".join(dict.fromkeys(models)) or ctx.model_key,
            "scenes": len(results),
            "attempts": attempts,
            "qa_scores": qa_scores,
            "optimization_rounds": optimization_rounds,
            "final_image_scores": final_scores,
            "final_render_profile": profiles[-1] if profiles else "",
        }

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _save_approved(ctx: PipelineContext, scene_id: str, result: RenderSessionResult) -> None:
        if result.winner is None or result.winner.image_path is None:
            raise StageError(
                RenderLoopStage.stage_id,
                f"scene {scene_id}: no approved image (render budget exhausted)",
            )
        ctx.images_dir.mkdir(parents=True, exist_ok=True)
        target = ctx.images_dir / f"{scene_id}.png"
        source = Path(result.winner.image_path)
        target.write_bytes(source.read_bytes())

    @staticmethod
    def _serialize_scene_result(scene_id: str, result: RenderSessionResult) -> dict[str, Any]:
        winner = result.winner
        return {
            "scene_id": scene_id,
            "passed": result.passed,
            "seed": result.seed,
            "max_attempts": result.max_attempts,
            "attempts": len(result.attempts),
            "model_switches": sum(
                1
                for attempt in result.attempts
                if attempt.status.value == "model_switched"
            ),
            "image_model": (
                winner.image_model if winner and winner.image_model else None
            ),
            "cache_hits": sum(
                1 for attempt in result.attempts if attempt.status.value == "skipped_duplicate"
            ),
            "qa_scores": [
                attempt.qa_report.overall_score
                for attempt in result.attempts
                if attempt.qa_report is not None
            ],
            "optimization_rounds": sum(
                1 for attempt in result.attempts if attempt.optimization_report is not None
            ),
            "final_qa_score": winner.qa_report.overall_score if winner and winner.qa_report else 0.0,
            "render_profile": winner.workflow_profile.value if winner else "",
            "image": (
                str(Path(winner.image_path)) if winner and winner.image_path else None
            ),
        }


# ------------------------------------------------------------ stage 7: voice --


class VoiceGenerationStage(Stage):
    """Narration -> TTS audio asset via the injected VoiceProvider."""

    stage_id = "voice"
    name = "Voice Generation"
    version = "1.0.0"
    description = "Synthesizes the narration into a WAV asset."
    dependencies = ("educational_director",)

    _DEFAULT_VOICE = "default"
    _DEFAULT_SAMPLE_RATE = 22050
    _DEFAULT_FORMAT = "wav"

    def __init__(
        self,
        provider: VoiceProvider,
        *,
        voice: str | None = None,
        sample_rate: int | None = None,
        format_: str | None = None,
    ) -> None:
        self._provider = provider
        self._voice = voice or self._DEFAULT_VOICE
        self._sample_rate = sample_rate or self._DEFAULT_SAMPLE_RATE
        self._format = format_ or self._DEFAULT_FORMAT

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {
            "narration": self._narration(ctx),
            "provider": self._provider.provider_name,
            "voice": self._voice,
            "sample_rate": self._sample_rate,
            "format": self._format,
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        narration = self._narration(ctx)
        render = await self._provider.synthesize(
            narration,
            output_dir=ctx.audio_dir,
            voice=self._voice,
            sample_rate=self._sample_rate,
            format_=self._format,
        )
        return {
            "file": render.file,
            "text": render.text,
            "voice": render.voice,
            "sample_rate": render.sample_rate,
            "format": render.format,
            "duration_seconds": render.duration_seconds,
            "checksum": render.checksum,
        }

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        voice = ctx.outputs.get(self.stage_id, {})
        return {
            "token_usage": 0,
            "model_usage": self._provider.provider_name,
            "duration_seconds": voice.get("duration_seconds", 0.0),
        }

    def _narration(self, ctx: PipelineContext) -> str:
        plan = EducationalPlan.model_validate(ctx.stage_output("educational_director"))
        return compose_narration(plan)


# ---------------------------------------------------------- stage 8: subtitles --


class SubtitleGenerationStage(Stage):
    """Narration + duration -> deterministic SRT subtitle file."""

    stage_id = "subtitles"
    name = "Subtitle Generation"
    version = "1.0.0"
    description = "Generates deterministic SRT subtitles from the narration."
    dependencies = ("voice",)

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        voice = ctx.stage_output("voice")
        return {
            "text": voice["text"],
            "duration_seconds": voice["duration_seconds"],
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        voice = ctx.stage_output("voice")
        srt = build_srt(voice["text"], float(voice["duration_seconds"]))
        path = ctx.subtitles_dir / "narration.srt"
        await asyncio.to_thread(path.write_text, srt, encoding="utf-8")
        return {
            "file": str(path),
            "entries": len(_split_sentences(voice["text"])),
        }

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        subtitles = ctx.outputs.get(self.stage_id, {})
        return {
            "token_usage": 0,
            "model_usage": "none",
            "entries": subtitles.get("entries", 0),
        }


# --------------------------------------------------------- stage 9: assembly --


class VideoAssemblyStage(Stage):
    """Approved images + narration -> the assembly timeline manifest.

    One segment per storyboard scene; the target duration is the narration
    duration clamped into the Shorts budget (settings.target_min..max), and
    every segment shares it equally. Deterministic by construction.
    """

    stage_id = "video_assembly"
    name = "Video Assembly"
    version = "1.0.0"
    description = "Builds the image + audio timeline for the renderer."
    dependencies = ("render_loop", "voice", "visual_intelligence")

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {
            "images": self._segment_images(ctx),
            "audio": ctx.stage_output("voice")["file"],
            "fps": ctx.settings.target_fps,
            "width": ctx.settings.target_width,
            "height": ctx.settings.target_height,
            "duration_seconds": self._target_duration(ctx),
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        images = self._segment_images(ctx)
        audio = ctx.stage_output("voice")["file"]
        duration = self._target_duration(ctx)
        per_scene = duration / len(images)
        segments = [
            {
                "file": str(image),
                "duration_seconds": round(per_scene, 4),
            }
            for image in images
        ]
        return {
            "segments": segments,
            "audio": audio,
            "fps": ctx.settings.target_fps,
            "width": ctx.settings.target_width,
            "height": ctx.settings.target_height,
            "duration_seconds": round(duration, 4),
        }

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        assembly = ctx.outputs.get(self.stage_id, {})
        return {
            "token_usage": 0,
            "model_usage": "none",
            "segments": len(assembly.get("segments", [])),
            "duration_seconds": assembly.get("duration_seconds", 0.0),
        }

    # ------------------------------------------------------------ internals --

    def _segment_images(self, ctx: PipelineContext) -> list[Path]:
        storyboard = VisualStoryboard.model_validate(ctx.stage_output("visual_intelligence"))
        images: list[Path] = []
        for scene in storyboard.scenes:
            image = ctx.images_dir / f"{scene.scene_id}.png"
            if not image.is_file():
                raise StageError(
                    self.stage_id,
                    f"approved image missing for scene {scene.scene_id}: {image}",
                )
            images.append(image)
        return images

    def _target_duration(self, ctx: PipelineContext) -> float:
        narration = float(ctx.stage_output("voice")["duration_seconds"])
        lower = ctx.settings.target_min_duration_seconds
        upper = ctx.settings.target_max_duration_seconds
        return min(max(narration, lower), upper)


# ---------------------------------------------------------- stage 10: render --


class VideoRenderStage(Stage):
    """Assembly manifest -> the encoded short.mp4 via the injected renderer."""

    stage_id = "video_render"
    name = "Video Render"
    version = "1.0.0"
    description = "Encodes the assembly timeline into short.mp4."
    dependencies = ("video_assembly",)

    def __init__(self, provider: VideoRendererProvider) -> None:
        self._provider = provider

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        assembly = ctx.stage_output("video_assembly")
        return {
            "segments": assembly["segments"],
            "audio": assembly["audio"],
            "fps": assembly["fps"],
            "width": assembly["width"],
            "height": assembly["height"],
            "codec": self._provider.codec,
            "container": self._provider.container,
            "crf": self._provider.crf,
            "audio_codec": self._provider.audio_codec,
            "audio_bitrate_kbps": self._provider.audio_bitrate_kbps,
            "provider": self._provider.provider_name,
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        assembly = ctx.stage_output("video_assembly")
        request = VideoRenderRequest(
            segments=[
                RenderSegment(
                    file=segment["file"],
                    duration_seconds=segment["duration_seconds"],
                )
                for segment in assembly["segments"]
            ],
            audio=assembly["audio"],
            fps=assembly["fps"],
            width=assembly["width"],
            height=assembly["height"],
            codec=self._provider.codec,
            container=self._provider.container,
            crf=self._provider.crf,
            audio_codec=self._provider.audio_codec,
            audio_bitrate_kbps=self._provider.audio_bitrate_kbps,
        )
        render = await self._provider.render(
            request,
            output_dir=ctx.video_dir,
            filename="short.mp4",
        )
        return {
            "file": render.file,
            "fps": render.fps,
            "width": render.width,
            "height": render.height,
            "duration_seconds": render.duration_seconds,
            "size_bytes": render.size_bytes,
            "checksum": render.checksum,
        }

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        render = ctx.outputs.get(self.stage_id, {})
        return {
            "token_usage": 0,
            "model_usage": self._provider.provider_name,
            "duration_seconds": render.get("duration_seconds", 0.0),
        }


# ----------------------------------------------------------- stage 11: thumb --


class ThumbnailSelectionStage(Stage):
    """Deterministic thumbnail pick: the storyboard's thumbnail scene winner."""

    stage_id = "thumbnail"
    name = "Thumbnail Selection"
    version = "1.0.0"
    description = "Selects the storyboard-designated thumbnail image."
    dependencies = ("render_loop", "visual_intelligence")

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {
            "thumbnail_scene_id": self._thumbnail_scene_id(ctx),
            "render_loop": ctx.stage_output("render_loop"),
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        scene_id = self._thumbnail_scene_id(ctx)
        result = ctx.stage_output("render_loop").get(scene_id)
        if result is None or result.get("image") is None:
            raise StageError(
                self.stage_id,
                f"thumbnail scene {scene_id} produced no approved image",
            )
        source = Path(result["image"])
        target = ctx.thumbnail_dir / "thumbnail.png"
        await asyncio.to_thread(_copy_file, source, target)
        return {
            "file": str(target),
            "scene_id": scene_id,
            "source": str(source),
        }

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        thumbnail = ctx.outputs.get(self.stage_id, {})
        return {
            "token_usage": 0,
            "model_usage": "none",
            "scene_id": thumbnail.get("scene_id", ""),
        }

    def _thumbnail_scene_id(self, ctx: PipelineContext) -> str:
        storyboard = VisualStoryboard.model_validate(ctx.stage_output("visual_intelligence"))
        return storyboard.thumbnail_scene_id


# ------------------------------------------------------------ stage 12: meta --


class MetadataGenerationStage(Stage):
    """Deterministic publishing metadata from the row, plan, and storyboard.

    No LLM: the title, description, tags, and category are derived from the
    curated knowledge row, falling back to plan fields when the row omits
    them. The category id maps through the canonical YouTube taxonomy and
    stays ``None`` for unknown names (the publisher fails closed).
    """

    stage_id = "metadata"
    name = "Metadata Generation"
    version = "1.0.0"
    description = "Derives deterministic title, description, tags, and category."
    dependencies = ("knowledge_load", "educational_director", "visual_intelligence")

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {
            "row": ctx.stage_output("knowledge_load"),
            "plan": ctx.stage_output("educational_director"),
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        row = ctx.stage_output("knowledge_load")
        plan = EducationalPlan.model_validate(ctx.stage_output("educational_director"))
        title = (row.get("title") or "").strip() or f"{plan.topic} in 45 seconds"
        description = self._description(row, plan)
        tags = self._tags(row)
        category_id = youtube_category_id(row.get("category", ""))
        payload = {
            "title": title,
            "description": description,
            "tags": tags,
            "category": row.get("category", ""),
            "category_id": category_id,
            "visibility": "private",
            "made_for_kids": False,
        }
        path = ctx.metadata_dir / "metadata.json"
        await asyncio.to_thread(
            path.write_text,
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return payload

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        metadata = ctx.outputs.get(self.stage_id, {})
        return {
            "token_usage": 0,
            "model_usage": "none",
            "tags": len(metadata.get("tags", [])),
            "category_id": metadata.get("category_id"),
        }

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _description(row: dict[str, str], plan: EducationalPlan) -> str:
        curated = (row.get("description") or "").strip()
        if curated:
            return curated
        return (
            f"{plan.attention_hook} {plan.final_takeaway} "
            f"Learn more about {plan.topic}."
        )

    @staticmethod
    def _tags(row: dict[str, str]) -> list[str]:
        def parse_list(field: str) -> list[str]:
            text = row.get(field, "").strip()
            if not text:
                return []
            if text.startswith("["):
                import ast

                try:
                    items = ast.literal_eval(text)
                except (ValueError, SyntaxError):
                    items = []
            else:
                items = [text]
            return [str(item).strip() for item in items if str(item).strip()]

        tags = parse_list("hashtags") or parse_list("keywords")
        return tags[:20]


# ------------------------------------------------------------ stage 13: pub --


class PublisherStage(Stage):
    """Metadata + deliverable -> publish manifest (dry-run by default).

    With ``ctx.publish`` False (the default) the stage writes a dry-run
    manifest with no network access. When publishing is enabled the stage
    requires the injected YouTubeProvider and fails closed if the category
    id is unknown.
    """

    stage_id = "publisher"
    name = "Publisher"
    version = "1.0.0"
    description = "Publishes the Short to YouTube (dry-run by default)."
    dependencies = ("video_render", "thumbnail", "metadata")

    def __init__(self, provider: YouTubeProvider | None = None) -> None:
        self._provider = provider

    def inputs(self, ctx: PipelineContext) -> dict[str, Any]:
        return {
            "video": ctx.stage_output("video_render")["file"],
            "thumbnail": ctx.stage_output("thumbnail")["file"],
            "metadata": ctx.stage_output("metadata"),
            "publish": ctx.publish,
            "provider": self._provider.provider_name if self._provider else "dry-run",
        }

    async def execute(self, ctx: PipelineContext) -> Any:
        video = ctx.stage_output("video_render")["file"]
        thumbnail = ctx.stage_output("thumbnail")["file"]
        metadata = ctx.stage_output("metadata")
        if ctx.publish:
            payload = await self._publish_real(ctx, video, thumbnail, metadata)
        else:
            payload = self._dry_run(ctx, metadata)
        path = ctx.run_dir / "publish_manifest.json"
        await asyncio.to_thread(
            path.write_text,
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return payload

    def metrics(self, ctx: PipelineContext) -> dict[str, Any]:
        manifest = ctx.outputs.get(self.stage_id, {})
        return {
            "token_usage": 0,
            "model_usage": manifest.get("backend", "dry-run"),
            "dry_run": manifest.get("dry_run", True),
            "video_id": manifest.get("video_id", ""),
        }

    # ------------------------------------------------------------ internals --

    async def _publish_real(
        self,
        ctx: PipelineContext,
        video: str,
        thumbnail: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if self._provider is None:
            raise StageError(self.stage_id, "publishing requires a YouTubeProvider")
        category_id = metadata.get("category_id")
        if not category_id:
            raise StageError(
                self.stage_id,
                f"unknown channel category {metadata.get('category', '')!r}; publish fails closed",
            )
        request = YouTubeUploadRequest(
            video_file=video,
            thumbnail_file=thumbnail,
            title=metadata["title"],
            description=metadata["description"],
            tags=metadata["tags"],
            category_id=str(category_id),
            visibility=metadata["visibility"],
            made_for_kids=bool(metadata["made_for_kids"]),
        )
        result = await self._provider.publish(request)
        return {
            "dry_run": False,
            "backend": self._provider.provider_name,
            "video_id": result.video_id,
            "url": result.url,
            "visibility": result.visibility,
            "published_at": result.published_at,
            "upload_status": result.upload_status,
        }

    @staticmethod
    def _dry_run(ctx: PipelineContext, metadata: dict[str, Any]) -> dict[str, Any]:
        video_id = f"dry-run-{ctx.run_id}"
        return {
            "dry_run": True,
            "backend": "dry-run",
            "video_id": video_id,
            "url": f"https://youtu.be/{video_id}",
            "visibility": metadata["visibility"],
            "published_at": None,
            "upload_status": "dry-run",
        }
