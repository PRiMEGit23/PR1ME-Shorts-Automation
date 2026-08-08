"""``pr1me run`` command: run the content pipeline against a sample CSV.

Bootstrap command. It wires the engine (prompt loader, providers, registered
stages, pipeline runner) and writes every completed stage's output to its
canonical artifact under ``output/``:

- ``output/topic.json``
- ``output/script.json``
- ``output/fact_summary.json``
- ``output/visual_plan.json``
- ``output/images/`` (one PNG per visual-plan shot)
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
from pr1me.providers.deepseek import DeepSeekProvider
from pr1me.stages import register_auto
from pr1me.stages.audio_mix_stage import AudioMixStage
from pr1me.stages.image_generation_stage import ImageGenerationStage
from pr1me.stages.metadata_stage import MetadataStage
from pr1me.stages.motion_stage import MotionGraphicsStage
from pr1me.stages.publisher_stage import PublisherStage
from pr1me.stages.thumbnail_stage import ThumbnailStage
from pr1me.stages.video_assembly_stage import VideoAssemblyStage
from pr1me.stages.video_render_stage import VideoRenderStage
from pr1me.stages.voice_generation_stage import VoiceGenerationStage

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


@register_command("run", "Run the content pipeline and write stage outputs.", add_parser=_add_parser)
def run(args: Namespace, settings: Settings) -> int:
    """Execute the registered pipeline against a CSV of recently used topics."""
    return asyncio.run(_run(args, settings))


async def _run(args: Namespace, settings: Settings) -> int:
    settings.ensure_dirs()
    loader = PromptLoader(settings.prompts_dir)
    provider = DeepSeekProvider(prompt_loader=loader)

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
    registry.register(ImageGenerationStage(context=context))
    registry.register(VoiceGenerationStage(context=context))
    registry.register(AudioMixStage(context=context))
    registry.register(MotionGraphicsStage(context=context))
    registry.register(VideoAssemblyStage(context=context))
    registry.register(VideoRenderStage(context=context))
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
