"""Structured pipeline events for the production orchestrator.

Every interesting moment of a production run is recorded as an ordered,
typed event: stage start/complete/failure, cache hits, checkpoint saves,
resource samples, and pipeline-level milestones. The sink keeps them in
memory for the execution report and can also stream them to a JSON file
per run, so an operator can reconstruct exactly what happened and when.

Events are deterministic in structure; timestamps are monotonic
milliseconds since the run started so they stay comparable across runs.
"""

from __future__ import annotations

import time
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from runtime.fingerprint import canonical_json

EVENTS_VERSION = "1.0.0"


class PipelineEventType(StrEnum):
    """The vocabulary of production pipeline events."""

    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    STAGE_SKIPPED = "stage_skipped"
    CHECKPOINT_SAVED = "checkpoint_saved"
    RESOURCE_SAMPLE = "resource_sample"
    CACHE_HIT = "cache_hit"


class PipelineEvent(BaseModel):
    """One recorded event in a run's timeline."""

    model_config = {"extra": "forbid", "frozen": True}

    run_id: str = Field(min_length=1)
    event_type: PipelineEventType
    #: Monotonic milliseconds since the run started (deterministic scale).
    offset_ms: float = Field(ge=0.0)
    stage_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EventSink:
    """Collects and optionally persists pipeline events for one run."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._events: list[PipelineEvent] = []
        self._started: float | None = None

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def events(self) -> list[PipelineEvent]:
        """All recorded events in emission order (read-only view)."""
        return list(self._events)

    def record(
        self,
        event_type: PipelineEventType,
        *,
        stage_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> PipelineEvent:
        """Record one event at the current run offset."""
        now = self._now_ms()
        event = PipelineEvent(
            run_id=self._run_id,
            event_type=event_type,
            offset_ms=now,
            stage_id=stage_id,
            payload=payload or {},
        )
        self._events.append(event)
        return event

    def count(self, event_type: PipelineEventType) -> int:
        """How many events of one type have been recorded."""
        return sum(1 for event in self._events if event.event_type is event_type)

    def stage_events(self, stage_id: str) -> list[PipelineEvent]:
        """Every event belonging to one stage, in emission order."""
        return [event for event in self._events if event.stage_id == stage_id]

    def start_timer(self) -> None:
        """Mark the run start; the first offset becomes zero."""
        self._started = time.monotonic()

    def write(self, path: Path) -> None:
        """Persist the event timeline as canonical JSON (atomic)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": EVENTS_VERSION,
            "run_id": self._run_id,
            "events": [event.model_dump(mode="json") for event in self._events],
        }
        tmp = path.with_suffix(f"{path.suffix}.tmp")
        tmp.write_text(canonical_json(payload), encoding="utf-8")
        tmp.replace(path)

    def _now_ms(self) -> float:
        if self._started is None:
            self._started = time.monotonic()
        return round((time.monotonic() - self._started) * 1000.0, 3)
