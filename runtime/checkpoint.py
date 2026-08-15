"""Stage checkpoints: the durable record of completed pipeline stages.

A checkpoint captures everything needed to safely resume a run: the stage's
content fingerprint (what its inputs were), the artifact records it produced,
and the stage version that produced them. A resumed run compares the planned
fingerprint against the checkpoint; a match plus intact artifacts means the
stage is provably already done and can be skipped.

Checkpoints live under ``<run_dir>/checkpoints/<stage_id>.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from runtime.artifact_store import ArtifactRecord
from runtime.fingerprint import canonical_json

CHECKPOINT_VERSION = "1.0.0"

#: Files this module reads/writes under the run directory.
CHECKPOINTS_DIR_NAME = "checkpoints"


class StageCheckpoint(BaseModel):
    """The durable record of one completed (or failed) stage execution."""

    model_config = {"extra": "forbid", "frozen": True}

    version: str = CHECKPOINT_VERSION
    stage_id: str = Field(min_length=1)
    fingerprint: str = Field(min_length=64, max_length=64)
    status: str = Field(pattern=r"^(completed|failed)$")
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    #: The stage's serialized output, so a resumed run can restore it.
    output: Any = None
    error: str = Field(default="", max_length=2000)


class CheckpointStore:
    """Persists and restores stage checkpoints for one run directory."""

    def __init__(self, run_dir: Path) -> None:
        self._dir = run_dir / CHECKPOINTS_DIR_NAME

    @property
    def dir(self) -> Path:
        return self._dir

    def save(self, checkpoint: StageCheckpoint) -> None:
        """Write one checkpoint atomically (canonical JSON)."""
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._dir / f"{checkpoint.stage_id}.json"
        payload = canonical_json(checkpoint.model_dump(mode="json"))
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(target)

    def load(self, stage_id: str) -> StageCheckpoint | None:
        """Load the checkpoint for one stage, or None when absent/corrupt."""
        target = self._dir / f"{stage_id}.json"
        if not target.is_file():
            return None
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            return StageCheckpoint.model_validate(raw)
        except (ValueError, TypeError, OSError):
            return None

    def all(self) -> list[StageCheckpoint]:
        """Every checkpoint present in the run directory (sorted by stage)."""
        if not self._dir.is_dir():
            return []
        checkpoints: list[StageCheckpoint] = []
        for target in sorted(self._dir.glob("*.json")):
            checkpoint = self.load(target.stem)
            if checkpoint is not None:
                checkpoints.append(checkpoint)
        return checkpoints
