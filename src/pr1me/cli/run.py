"""``pr1me run`` command: run the content pipeline against a sample CSV.

Bootstrap command. It wires the engine (prompt loader, providers, registered
stages, pipeline runner) and writes every completed stage's output to its
canonical artifact under ``output/``:

- ``output/topic.json``
- ``output/script.json``
- ``output/fact_summary.json``
- ``output/visual_plan.json``
- ``output/visual_architecture.json`` (knowledge, strategy, scene plan, shot plan,
  visual style, consistency, prompts, validation)
- ``output/workflow.json`` (one validated ComfyUI payload per shot)
- ``output/images/`` (one PNG per shot)
- ``output/image_manifest.json``
- ``output/audio/`` (the narration WAV and the mastered track)
- ``output/voice_manifest.json``
- ``output/audio_manifest.json``
- ``output/motion_graphics.json``
- ``output/assembly.json``
- ``output/short.mp4``
- ``output/render_manifest.json``
- ``output/metadata.json``
- ``output/thumbnail.png``
- ``output/thumbnail_manifest.json``
- ``output/publish_manifest.json``
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import shutil
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from uuid import uuid4

from pr1me.cli.main import EXIT_ERROR, EXIT_OK, register_command
from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.logging import get_logger
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.contracts.topic import TopicInput
from pr1me.pipeline.runner import PipelineRunner, RunReport
from pr1me.providers.audio import AudioProvider, FFmpegAudioMixer
from pr1me.providers.base_provider import BaseProvider
from pr1me.providers.deepseek import DeepSeekProvider
from pr1me.providers.ollama import OllamaProvider
from pr1me.providers.video_renderer import FFmpegVideoRenderer, VideoRendererProvider
from pr1me.providers.voice import HTTPVoiceBackend, VoiceProvider
from pr1me.stages import register_auto
from pr1me.stages.audio_mix_stage import AudioMixStage
from pr1me.stages.image_generation_stage import ImageGenerationStage
from pr1me.stages.metadata_stage import MetadataStage
from pr1me.stages.motion_stage import MotionGraphicsStage
from pr1me.stages.publisher_stage import PublisherStage
from pr1me.stages.thumbnail_stage import ThumbnailStage
from pr1me.stages.video_assembly_stage import VideoAssemblyStage
from pr1me.stages.video_render_stage import VideoRenderStage
from pr1me.stages.visual_architecture_stage import VisualArchitectureStage
from pr1me.stages.voice_generation_stage import VoiceGenerationStage
from pr1me.stages.workflow_builder_stage import WorkflowBuilderStage

logger = get_logger("pr1me.cli.run")

#: Channel directive used unless overridden on the command line.
_DEFAULT_DIRECTIVE = (
    "balance beginner-friendly and advanced 3D-printing engineering topics; "
    "avoid repeating content already covered."
)
_DEFAULT_CSV_NAME = "topics.csv"

#: stage_id -> default artifact filename written by ``pr1me run``.
_STAGE_OUTPUTS: dict[str, str] = {
    "topic": "topic.json",
    "script": "script.json",
    "fact_check": "fact_summary.json",
    "visual": "visual_plan.json",
    "visual_architecture": "visual_architecture.json",
    "workflow_builder": "workflow.json",
    "image_generation": "image_manifest.json",
    "voice_generation": "voice_manifest.json",
    "audio_mix": "audio_manifest.json",
    "motion_graphics": "motion_graphics.json",
    "video_assembly": "assembly.json",
    "video_render": "render_manifest.json",
    "metadata": "metadata.json",
    "thumbnail": "thumbnail_manifest.json",
    "publisher": "publish_manifest.json",
}


def _add_parser(sub: ArgumentParser) -> None:
    sub.add_argument(
        "--csv",
        metavar="PATH",
        default=None,
        help="recently used topics CSV (default: assets/topics.csv)",
    )
    sub.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="output JSON path (default: output/topic.json)",
    )
    sub.add_argument(
        "--directive",
        metavar="TEXT",
        default=None,
        help="channel directive (default: built-in)",
    )
    sub.add_argument("--category", metavar="NAME", default=None, help="optional category focus")
    sub.add_argument(
        "--dry-run",
        action="store_true",
        help="validate every stage and emit the upload payload without uploading to YouTube",
    )

    # ---- Phase 7: deterministic production pipeline (knowledge row -> Short) ----
    sub.add_argument(
        "--knowledge-csv",
        metavar="PATH",
        default=None,
        help="Knowledge Base CSV (default: assets/knowledge_base.csv)",
    )
    sub.add_argument(
        "--row",
        metavar="TOPIC",
        default=None,
        help="exact topic of the Knowledge Base row to run",
    )
    sub.add_argument(
        "--row-index",
        metavar="N",
        default=None,
        type=int,
        help="0-based index of the row to run inside the CSV",
    )
    sub.add_argument(
        "--run-dir",
        metavar="PATH",
        default=None,
        help="output directory for this run (default: output/runs/<run-id>/<topic>)",
    )
    sub.add_argument(
        "--resume",
        action="store_true",
        help="skip stages whose checkpoint matches and artifacts are intact",
    )
    sub.add_argument(
        "--seed",
        metavar="N",
        default=None,
        type=int,
        help="deterministic render seed (default: 42)",
    )
    sub.add_argument(
        "--max-attempts",
        metavar="N",
        default=None,
        type=int,
        help="per-scene render retry budget (default: 3)",
    )
    sub.add_argument(
        "--publish",
        action="store_true",
        help="actually upload to YouTube (default: dry-run manifest only)",
    )


@register_command("run", "Run the content pipeline and write stage outputs.", add_parser=_add_parser)
def run(args: Namespace, settings: Settings) -> int:
    """Execute the registered pipeline against a CSV of recently used topics."""
    return asyncio.run(_run(args, settings))


async def _run(args: Namespace, settings: Settings) -> int:
    if _is_production_run(args):
        return await _run_production(args, settings)
    settings.ensure_dirs()
    if getattr(args, "dry_run", False):
        os.environ["PR1ME_PUBLISH_DRY_RUN"] = "1"
    loader = PromptLoader(settings.prompts_dir)
    provider = _select_provider(loader)

    context = StageContext(
        settings=settings,
        logger=get_logger("pr1me.cli.run", job_id="cli"),
        prompt_loader=loader,
        provider=provider,
        job_id="cli",
        run_id=f"cli-{uuid4().hex[:8]}",
    )
    registry = StageRegistry(context=context)
    register_auto(registry)
    registry.register(VisualArchitectureStage(context=context))
    registry.register(WorkflowBuilderStage(context=context))
    registry.register(ImageGenerationStage(context=context))
    registry.register(VoiceGenerationStage(context=context, voice_provider=_select_voice_provider()))
    registry.register(AudioMixStage(context=context, audio_provider=_select_audio_provider()))
    registry.register(MotionGraphicsStage(context=context))
    registry.register(VideoAssemblyStage(context=context))
    registry.register(VideoRenderStage(context=context, renderer=_select_renderer()))
    registry.register(MetadataStage(context=context))
    registry.register(ThumbnailStage(context=context))
    registry.register(PublisherStage(context=context))

    csv_file = Path(args.csv) if args.csv else settings.assets_dir / _DEFAULT_CSV_NAME
    job_input = TopicInput(
        existing_topics=_read_topics_csv(csv_file),
        directive=args.directive or _DEFAULT_DIRECTIVE,
        category_focus=args.category,
    )

    runner = PipelineRunner(registry, context=context, artifact_dir=settings.work_dir)
    report = await runner.run(job_input, job_id="cli")

    if report.run_status.value != "complete":
        logger.error("event=cli.run_failed", status=report.run_status.value)
        return EXIT_ERROR

    written = _write_artifacts(report, settings.work_dir, topic_output=args.output)
    logger.info("event=cli.artifacts_written", paths=written)
    return EXIT_OK


def _select_provider(loader: PromptLoader) -> BaseProvider:
    """Pick the LLM backend: local Ollama by default, DeepSeek when keyed.

    DeepSeek is used only when a DeepSeek API key is explicitly supplied
    (``PR1ME_DEEPSEEK_API_KEY`` or legacy ``DEEPSEEK_API_KEY``); otherwise the
    pipeline runs fully local against Ollama and never asks for credentials.
    """
    if os.getenv("PR1ME_DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY"):
        return DeepSeekProvider(prompt_loader=loader)
    return OllamaProvider(prompt_loader=loader)


def _select_voice_provider() -> VoiceProvider:
    """Build the TTS backend: local Kokoro by default, overridable by env.

    ``PR1ME_VOICE_BASE_URL`` (and the other ``PR1ME_VOICE_*`` variables) take
    precedence; when unset the pipeline talks to the local Kokoro server that
    ships with the engine.
    """
    base_url = os.getenv("PR1ME_VOICE_BASE_URL") or "http://127.0.0.1:8890"
    voice = os.getenv("PR1ME_VOICE") or "af_heart"
    return VoiceProvider(backend=HTTPVoiceBackend(base_url=base_url), voice=voice)


def _find_ffmpeg() -> str:
    """Locate a usable ffmpeg binary for audio mastering and video encoding.

    Preference order: ``PR1ME_AUDIO_FFMPEG_BIN``/``PR1ME_RENDER_FFMPEG_BIN``,
    then ``ffmpeg`` on ``PATH``, then well-known local installations.
    """
    for env_name in ("PR1ME_AUDIO_FFMPEG_BIN", "PR1ME_RENDER_FFMPEG_BIN"):
        configured = os.getenv(env_name)
        if configured:
            return configured
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    candidates = [
        r"C:\Program Files\Krita (x64)\bin\ffmpeg.exe",
        r"C:\Program Files\Live2D Cubism 5.3\tools\ffmpeg\ffmpeg.exe",
        r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS Flow Simulation\binCFW\ffmpeg.exe",
        r"C:\MediaToolkit\ffmpeg.exe",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    return "ffmpeg"


def _find_ffmpeg_encoder() -> str:
    """Locate an ffmpeg with an H.264 encoder (``libx264`` or OpenH264).

    The audio-mix binary must support ``loudnorm`` (Krita 7.x, Live2D 5.x);
    the renderer needs an H.264 encoder with ``-crf`` support (libx264).
    """
    for env_name in ("PR1ME_AUDIO_FFMPEG_BIN", "PR1ME_RENDER_FFMPEG_BIN"):
        configured = os.getenv(env_name)
        if configured:
            return configured
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    encoder_candidates = [
        r"D:\ZORO\Downloads 3\ffmpeg\ffmpeg-2026-05-06-git-f2e5eff3ff-full_build\bin\ffmpeg.exe",
        r"C:\MediaToolkit\ffmpeg.exe",
        r"C:\Program Files\Live2D Cubism 5.3\tools\ffmpeg\ffmpeg.exe",
        r"C:\Program Files\Krita (x64)\bin\ffmpeg.exe",
    ]
    for candidate in encoder_candidates:
        if Path(candidate).is_file():
            return candidate
    return "ffmpeg"


def _select_audio_provider() -> AudioProvider:
    """Build the audio mastering backend against the discovered ffmpeg."""
    return AudioProvider(backend=FFmpegAudioMixer(binary=_find_ffmpeg()))


def _select_renderer() -> VideoRendererProvider:
    """Build the video encoding backend against the discovered ffmpeg."""
    return VideoRendererProvider(backend=FFmpegVideoRenderer(binary=_find_ffmpeg_encoder()))


def _write_artifacts(
    report: RunReport,
    work_dir: Path,
    *,
    topic_output: str | None = None,
) -> list[str]:
    """Write each completed stage's output to its canonical artifact filename.

    ``topic_output`` overrides the topic artifact path (CLI ``--output``);
    all other stages write to ``work_dir``.
    """
    written: list[str] = []
    per_stage: dict[str, dict] = {}
    for record in report.stages:
        if record.status.value == "ok":
            per_stage.setdefault(record.stage_id, record.output)
    for stage_id, filename in _STAGE_OUTPUTS.items():
        if stage_id not in per_stage:
            continue
        dest = Path(topic_output) if topic_output and stage_id == "topic" else work_dir / filename
        dest.write_text(json.dumps(per_stage[stage_id], indent=2), encoding="utf-8")
        written.append(str(dest))
    return written


def _read_topics_csv(path: Path) -> list[str]:
    """Read the ``topic`` column from a topics CSV (header row required)."""
    if not path.is_file():
        raise FileNotFoundError(f"topics CSV not found: {path}")
    topics: list[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            topic = (row.get("topic") or "").strip()
            if topic:
                topics.append(topic)
    return topics


# ------------------------------------------------------- production pipeline --


def _is_production_run(args: Namespace) -> bool:
    """True when any Phase 7 flag is present (deterministic pipeline mode)."""
    return any(
        getattr(args, name, None)
        for name in (
            "knowledge_csv",
            "row",
            "row_index",
            "run_dir",
            "resume",
            "seed",
            "max_attempts",
            "publish",
        )
    )


async def _run_production(args: Namespace, settings: Settings) -> int:
    """Run the deterministic thirteen-stage production pipeline."""
    _ensure_runtime_importable()
    from knowledge.visual_architecture import EngineeringDomain, Modality
    from runtime.pipeline import ProductionPipeline
    from runtime.renderer import SimulatedRenderer

    from pr1me.providers.video_renderer import FFmpegVideoRenderer, VideoRendererProvider
    from pr1me.providers.voice import VoiceProvider
    from pr1me.providers.youtube import YouTubeProvider

    csv_path = (
        Path(args.knowledge_csv)
        if args.knowledge_csv
        else settings.assets_dir / "knowledge_base.csv"
    )
    row = _select_row(csv_path, topic=args.row, index=args.row_index)
    logger.info(
        "event=cli.production.started",
        topic=row["topic"],
        run_dir=args.run_dir or "auto",
        resume=bool(args.resume),
        publish=bool(args.publish),
    )

    youtube_provider = YouTubeProvider() if args.publish else None
    pipeline = ProductionPipeline(
        row=row,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        seed=args.seed if args.seed is not None else 42,
        max_attempts=args.max_attempts if args.max_attempts is not None else 3,
        engineering_domain=EngineeringDomain.FDM,
        modality=Modality.PHOTOREAL,
        publish=bool(args.publish),
        renderer=SimulatedRenderer(),
        voice_provider=VoiceProvider(),
        video_renderer_provider=VideoRendererProvider(
            backend=FFmpegVideoRenderer(binary=_find_ffmpeg_encoder())
        ),
        youtube_provider=youtube_provider,
    )
    result = await pipeline.run(resume=bool(args.resume))
    if result.status != "complete":
        logger.error(
            "event=cli.production.failed",
            status=result.status,
            stage_or_error=result.error,
        )
        return EXIT_ERROR
    logger.info(
        "event=cli.production.completed",
        run_id=result.run_id,
        run_dir=str(result.run_dir),
        report=str(result.run_dir / "reports" / "execution_report.json"),
    )
    return EXIT_OK


def _select_row(path: Path, *, topic: str | None, index: int | None) -> dict[str, str]:
    """Pick one Knowledge Base row by exact topic, index, or the first row."""
    if not path.is_file():
        raise FileNotFoundError(f"knowledge CSV not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"knowledge CSV is empty: {path}")
    if index is not None:
        return dict(rows[index])
    if topic:
        for row in rows:
            if (row.get("topic") or "").strip() == topic.strip():
                return dict(row)
        raise KeyError(f"no knowledge row with topic {topic!r}")
    return dict(rows[0])


def _ensure_runtime_importable() -> None:
    """Add the repository root to ``sys.path`` so ``runtime`` is importable.

    The Phase 7 pipeline lives in the repo-root ``runtime`` package, outside
    the installed ``pr1me`` distribution; this bridge makes it reachable from
    the console script without installing the package.
    """
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
