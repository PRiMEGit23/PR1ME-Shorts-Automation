"""The production pipeline orchestrator.

Binds the fifteen mission stages into one deterministic run:

    CSV Knowledge Row -> Knowledge Loader -> Educational Director ->
    AI Director -> Visual Intelligence -> Model Director -> Prompt
    Compiler -> Workflow Builder -> Render Loop -> Voice -> Subtitles ->
    Video Assembly -> Video Render -> Thumbnail -> Metadata -> Publisher

The orchestrator owns everything a *run* needs beyond the stages:

- run identity (run id + job id) and the run directory layout
- provider injection (renderer, voice, video renderer, YouTube)
- sequential stage execution with fingerprints, resume, checkpoints, events
- the pipeline manifest, the execution report, the event timeline, and the
  pipeline context snapshot at the run root

Everything stage-internal is deterministic; the only entropy is the run id
itself (traceability). Providers are constructor-injected seams: production
defaults come from ``PR1ME_*`` configuration, tests inject fakes.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge.visual_architecture import EngineeringDomain, Modality

from pr1me.core.config import Settings
from pr1me.providers.video_renderer import VideoRendererProvider
from pr1me.providers.voice import VoiceProvider
from pr1me.providers.youtube import YouTubeProvider
from runtime.artifact_store import ArtifactStore
from runtime.checkpoint import CheckpointStore
from runtime.events import EventSink, PipelineEventType
from runtime.models import topic_slug
from runtime.pipeline_context import PIPELINE_VERSION, PipelineContext
from runtime.pipeline_stages import (
    AIDirectorStage,
    EducationalDirectorStage,
    KnowledgeLoadStage,
    MetadataGenerationStage,
    ModelDirectorStage,
    PromptCompilerStage,
    PublisherStage,
    RenderLoopStage,
    SubtitleGenerationStage,
    ThumbnailSelectionStage,
    VideoAssemblyStage,
    VideoRenderStage,
    VisualIntelligenceStage,
    VoiceGenerationStage,
    WorkflowBuilderStage,
)
from runtime.renderer import Renderer, SimulatedRenderer
from runtime.report import ExecutionReport, StageReport
from runtime.stage_runner import Stage, StageRunner, StageRunResult

#: The canonical stage order (mission order).
STAGE_ORDER: tuple[str, ...] = (
    "knowledge_load",
    "educational_director",
    "ai_director",
    "visual_intelligence",
    "model_director",
    "prompt_compiler",
    "workflow_builder",
    "render_loop",
    "voice",
    "subtitles",
    "video_assembly",
    "video_render",
    "thumbnail",
    "metadata",
    "publisher",
)


@dataclass
class PipelineResult:
    """The outcome of one production pipeline run."""

    run_id: str
    job_id: str
    topic: str
    status: str
    run_dir: Path
    manifest: dict[str, Any]
    report: dict[str, Any]
    error: str | None = None


class ProductionPipeline:
    """One deterministic end-to-end run of the mission pipeline.

    The pipeline is a value object: every directive (seed, budget, model,
    domain, modality, publish) is fixed at construction, so identical inputs
    reproduce identical stage fingerprints and resume decisions.
    """

    def __init__(
        self,
        *,
        row: dict[str, str],
        settings: Settings | None = None,
        run_dir: Path | None = None,
        seed: int = 42,
        max_attempts: int = 3,
        model_key: str = "sdxl",
        engineering_domain: EngineeringDomain = EngineeringDomain.FDM,
        modality: Modality = Modality.PHOTOREAL,
        publish: bool = False,
        renderer: Renderer | None = None,
        voice_provider: VoiceProvider | None = None,
        video_renderer_provider: VideoRendererProvider | None = None,
        youtube_provider: YouTubeProvider | None = None,
    ) -> None:
        self._row = dict(row)
        self._settings = settings if settings is not None else Settings()
        self._run_dir = run_dir
        self._seed = seed
        self._max_attempts = max_attempts
        self._model_key = model_key
        self._engineering_domain = engineering_domain
        self._modality = modality
        self._publish = publish
        self._renderer = renderer if renderer is not None else SimulatedRenderer()
        self._voice_provider = voice_provider if voice_provider is not None else VoiceProvider()
        self._video_renderer_provider = (
            video_renderer_provider
            if video_renderer_provider is not None
            else VideoRendererProvider()
        )
        #: A real YouTubeProvider is only needed when publishing; constructing
        #: one fails fast when no access token is configured, so it is built
        #: lazily here and never in a dry-run.
        self._youtube_provider = youtube_provider

    # ---------------------------------------------------------------- entry --

    async def run(self, *, resume: bool = False) -> PipelineResult:
        """Run the pipeline; returns a complete or failed result (never raises)."""
        run_id = uuid.uuid4().hex
        job_id = uuid.uuid4().hex
        topic = self._row.get("topic", "").strip() or "untitled"
        run_dir = self._resolve_run_dir(topic, run_id)
        ctx = self._build_context(run_id, job_id, topic, run_dir)
        ctx.ensure_dirs()
        ctx.events.start_timer()
        ctx.events.record(
            PipelineEventType.PIPELINE_STARTED,
            payload={"topic": topic, "seed": self._seed, "model_key": self._model_key},
        )

        runner = StageRunner(store=ctx.store, checkpoints=ctx.checkpoints, events=ctx.events)
        results: list[StageRunResult] = []
        status = "complete"
        error: str | None = None
        for stage in self._stages():
            try:
                result = await runner.run(stage, ctx, resume=resume)
                ctx.record_stage(
                    result.stage_id,
                    result.output,
                    result.artifacts,
                    duration_ms=result.duration_ms,
                    cache_hit=result.cache_hit,
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001 - fail closed at the pipeline level
                status = "failed"
                error = f"{type(exc).__name__}: {exc}"
                ctx.events.record(
                    PipelineEventType.PIPELINE_FAILED,
                    payload={"stage": stage.stage_id, "error": error},
                )
                break

        total_duration_ms = round(sum(ctx.durations_ms.values()), 3)
        ctx.events.record(
            PipelineEventType.PIPELINE_COMPLETED if status == "complete"
            else PipelineEventType.PIPELINE_FAILED,
            payload={"status": status, "total_duration_ms": total_duration_ms},
        )
        ctx.events.write(run_dir / "events.json")

        report = self._build_report(ctx, results, status, total_duration_ms, error)
        self._write_report(ctx, report)
        self._write_manifest(ctx, status, error)
        self._write_context_snapshot(ctx)
        return PipelineResult(
            run_id=run_id,
            job_id=job_id,
            topic=topic,
            status=status,
            run_dir=run_dir,
            manifest=self._read_manifest(run_dir),
            report=report.model_dump(mode="json"),
            error=error,
        )

    # ------------------------------------------------------------ internals --

    def _stages(self) -> list[Stage]:
        return [
            KnowledgeLoadStage(),
            EducationalDirectorStage(),
            AIDirectorStage(),
            VisualIntelligenceStage(),
            ModelDirectorStage(preferred_model=self._model_key),
            PromptCompilerStage(),
            WorkflowBuilderStage(),
            RenderLoopStage(renderer=self._renderer),
            VoiceGenerationStage(self._voice_provider),
            SubtitleGenerationStage(),
            VideoAssemblyStage(),
            VideoRenderStage(self._video_renderer_provider),
            ThumbnailSelectionStage(),
            MetadataGenerationStage(),
            PublisherStage(self._youtube_provider),
        ]

    def _build_context(
        self,
        run_id: str,
        job_id: str,
        topic: str,
        run_dir: Path,
    ) -> PipelineContext:
        return PipelineContext(
            run_id=run_id,
            job_id=job_id,
            topic=topic,
            settings=self._settings,
            run_dir=run_dir,
            store=ArtifactStore(run_dir),
            events=EventSink(run_id),
            checkpoints=CheckpointStore(run_dir),
            row=self._row,
            seed=self._seed,
            max_attempts=self._max_attempts,
            model_key=self._model_key,
            engineering_domain=self._engineering_domain,
            modality=self._modality,
            publish=self._publish,
        )

    def _resolve_run_dir(self, topic: str, run_id: str) -> Path:
        if self._run_dir is not None:
            return self._run_dir
        return self._settings.work_dir / "runs" / run_id / topic_slug(topic)

    def _build_report(
        self,
        ctx: PipelineContext,
        results: list[StageRunResult],
        status: str,
        total_duration_ms: float,
        error: str | None,
    ) -> ExecutionReport:
        stage_reports = [
            StageReport(
                stage_id=result.stage_id,
                name=result.stage_id,
                version="1.0.0",
                status=result.status,
                duration_ms=result.duration_ms,
                cache_hit=result.cache_hit,
                fingerprint=result.fingerprint,
                memory_peak_mb=result.memory_peak_mb,
                gpu_time_ms=result.gpu_time_ms,
                metrics=result.metrics,
                artifacts=result.artifacts,
            )
            for result in results
        ]
        return ExecutionReport(
            run_id=ctx.run_id,
            job_id=ctx.job_id,
            topic=ctx.topic,
            status=status,
            total_duration_ms=total_duration_ms,
            stages=stage_reports,
            final_artifacts=self._final_artifacts(ctx),
        )

    def _write_report(self, ctx: PipelineContext, report: ExecutionReport) -> None:
        report.write(ctx.reports_dir / "execution_report.json")

    def _write_manifest(self, ctx: PipelineContext, status: str, error: str | None) -> None:
        manifest = {
            "version": PIPELINE_VERSION,
            "run_id": ctx.run_id,
            "job_id": ctx.job_id,
            "topic": ctx.topic,
            "status": status,
            "finished_at": datetime.now(UTC).isoformat(),
            "run_dir": str(ctx.run_dir),
            "error": error,
            "stages": [
                {
                    "stage_id": stage_id,
                    "status": "completed" if stage_id in ctx.outputs else "skipped_or_failed",
                    "cache_hit": ctx.cache_hits.get(stage_id, False),
                    "duration_ms": ctx.durations_ms.get(stage_id, 0.0),
                }
                for stage_id in STAGE_ORDER
            ],
            "final_artifacts": self._final_artifacts(ctx),
            "report": str(ctx.reports_dir / "execution_report.json"),
        }
        target = ctx.run_dir / "manifest.json"
        target.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    def _write_context_snapshot(self, ctx: PipelineContext) -> None:
        snapshot = {
            "version": PIPELINE_VERSION,
            "run_id": ctx.run_id,
            "job_id": ctx.job_id,
            "topic": ctx.topic,
            "seed": ctx.seed,
            "max_attempts": ctx.max_attempts,
            "model_key": ctx.model_key,
            "engineering_domain": ctx.engineering_domain.value,
            "modality": ctx.modality.value,
            "publish": ctx.publish,
            "row": {str(key): value for key, value in ctx.row.items()},
            "run_dir": str(ctx.run_dir),
            "dirs": {
                "images": str(ctx.images_dir),
                "audio": str(ctx.audio_dir),
                "subtitles": str(ctx.subtitles_dir),
                "video": str(ctx.video_dir),
                "thumbnail": str(ctx.thumbnail_dir),
                "metadata": str(ctx.metadata_dir),
                "workflow": str(ctx.workflow_dir),
                "history": str(ctx.history_dir),
                "reports": str(ctx.reports_dir),
            },
        }
        target = ctx.run_dir / "pipeline_context.json"
        target.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _final_artifacts(ctx: PipelineContext) -> dict[str, Any]:
        artifacts: dict[str, Any] = {}
        if "video_render" in ctx.outputs:
            artifacts["video"] = ctx.outputs["video_render"]["file"]
        if "thumbnail" in ctx.outputs:
            artifacts["thumbnail"] = ctx.outputs["thumbnail"]["file"]
        if "metadata" in ctx.outputs:
            metadata_file = ctx.metadata_dir / "metadata.json"
            artifacts["metadata"] = str(metadata_file) if metadata_file.is_file() else None
        if "voice" in ctx.outputs:
            artifacts["audio"] = ctx.outputs["voice"]["file"]
        if "subtitles" in ctx.outputs:
            artifacts["subtitles"] = ctx.outputs["subtitles"]["file"]
        if "render_loop" in ctx.outputs:
            artifacts["images"] = sorted(
                str(path) for path in ctx.images_dir.glob("S*.png")
            )
        if "workflow_builder" in ctx.outputs:
            artifacts["workflows"] = sorted(
                str(path) for path in ctx.workflow_dir.glob("S*.json")
            )
        publish_manifest = ctx.run_dir / "publish_manifest.json"
        artifacts["publish_manifest"] = (
            str(publish_manifest) if publish_manifest.is_file() else None
        )
        return {key: value for key, value in artifacts.items() if value is not None}

    @staticmethod
    def _read_manifest(run_dir: Path) -> dict[str, Any]:
        target = run_dir / "manifest.json"
        if not target.is_file():
            return {}
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
