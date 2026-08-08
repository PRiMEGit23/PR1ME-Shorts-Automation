"""``pr1me run`` command: run the topic stage against a sample CSV.

Bootstrap-only command. It wires the engine (prompt loader, DeepSeek provider,
topic stage, pipeline runner) and writes the resulting topic to
``output/topic.json``.
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

logger = get_logger("pr1me.cli.run")

#: Channel directive used unless overridden on the command line.
_DEFAULT_DIRECTIVE = (
    "balance beginner-friendly and advanced 3D-printing engineering topics; "
    "avoid repeating content already covered."
)
_DEFAULT_CSV_NAME = "topics.csv"
_DEFAULT_OUTPUT_NAME = "topic.json"


def _add_parser(sub: ArgumentParser) -> None:
    sub.add_argument(
        "--csv", metavar="PATH", default=None,
        help="recently used topics CSV (default: assets/topics.csv)",
    )
    sub.add_argument(
        "--output", metavar="PATH", default=None,
        help="output JSON path (default: output/topic.json)",
    )
    sub.add_argument(
        "--directive", metavar="TEXT", default=None,
        help="channel directive (default: built-in)",
    )
    sub.add_argument("--category", metavar="NAME", default=None, help="optional category focus")


@register_command("run", "Run the pipeline and write the topic output.", add_parser=_add_parser)
def run(args: Namespace, settings: Settings) -> int:
    """Execute the topic stage against a CSV of recently used topics."""
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

    output = _topic_output(report)
    dest = Path(args.output) if args.output else settings.work_dir / _DEFAULT_OUTPUT_NAME
    dest.write_text(json.dumps(output, indent=2), encoding="utf-8")
    logger.info("event=cli.topic_written", path=str(dest), artifact=report.final_artifact)
    return EXIT_OK


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


def _topic_output(report: RunReport) -> dict:
    """Extract the validated topic payload from the run report."""
    for record in report.stages:
        if record.stage_id == "topic" and record.status.value == "ok":
            return record.output
    raise RuntimeError("topic stage produced no output")