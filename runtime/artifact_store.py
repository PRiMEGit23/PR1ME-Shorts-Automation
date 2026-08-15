"""Versioned artifact storage for the production pipeline.

Every artifact a stage produces is stored under the run directory as
``artifacts/<stage_id>/<name>.<version>.<ext>`` where the version is derived
from the payload's content fingerprint. Identical content never produces a
second file, and any change produces a brand new version, so stored
artifacts are immutable and trivially cacheable. Every stored artifact is
recorded with its checksum and size for manifest traceability.

The store is transport-only: it knows nothing about stages or the pipeline.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from runtime.fingerprint import artifact_version, canonical_json

ARTIFACT_STORE_VERSION = "1.0.0"


class ArtifactRecord(BaseModel):
    """One stored artifact and its provenance."""

    model_config = {"extra": "forbid", "frozen": True}

    stage_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1)
    path: str = Field(min_length=1)
    checksum: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)
    kind: str = Field(default="json", pattern=r"^(json|binary)$")


class ArtifactStore:
    """Content-addressed artifact persistence under one run directory.

    ``root`` is the run directory; artifacts live under
    ``<root>/artifacts/<stage_id>/<name>.<version>.<ext>``.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._artifacts_dir = root / "artifacts"
        self._records: dict[str, ArtifactRecord] = {}

    @property
    def root(self) -> Path:
        return self._root

    @property
    def artifacts_dir(self) -> Path:
        return self._artifacts_dir

    # ------------------------------------------------------------ entries --

    def save_json(
        self,
        stage_id: str,
        name: str,
        payload: Any,
        *,
        kind: str = "json",
    ) -> ArtifactRecord:
        """Store one JSON-serializable payload and return its record."""
        text = canonical_json(payload)
        return self._save_bytes(
            stage_id,
            name,
            text.encode("utf-8"),
            extension=".json",
            kind=kind,
        )

    def save_bytes(
        self,
        stage_id: str,
        name: str,
        data: bytes,
        *,
        extension: str = ".bin",
    ) -> ArtifactRecord:
        """Store one binary payload and return its record."""
        return self._save_bytes(stage_id, name, data, extension=extension, kind="binary")

    def load_json(self, record: ArtifactRecord) -> Any:
        """Load a previously stored JSON artifact back into its payload."""
        import json

        return json.loads(self.load_bytes(record).decode("utf-8"))

    def load_bytes(self, record: ArtifactRecord) -> bytes:
        """Read the raw bytes of a previously stored artifact."""
        return Path(record.path).read_bytes()

    def has(self, record: ArtifactRecord) -> bool:
        """Whether the artifact still exists on disk with its checksum."""
        path = Path(record.path)
        if not path.is_file():
            return False
        return _sha256(path.read_bytes()) == record.checksum

    def records(self, stage_id: str | None = None) -> list[ArtifactRecord]:
        """All records, optionally filtered to one stage (insertion order)."""
        if stage_id is None:
            return list(self._records.values())
        return [record for record in self._records.values() if record.stage_id == stage_id]

    def find(self, stage_id: str, name: str) -> ArtifactRecord | None:
        """The record for one (stage_id, name) pair, if it was stored."""
        return self._records.get(f"{stage_id}:{name}")

    def stage_dir(self, stage_id: str) -> Path:
        return self._artifacts_dir / stage_id

    # ------------------------------------------------------------ internals --

    def _save_bytes(
        self,
        stage_id: str,
        name: str,
        data: bytes,
        *,
        extension: str,
        kind: str,
    ) -> ArtifactRecord:
        version = artifact_version(_sha256(data))
        directory = self.stage_dir(stage_id)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{name}.{version}{extension}"
        target = directory / filename
        if not target.exists():
            tmp = directory / f".{filename}.tmp"
            tmp.write_bytes(data)
            tmp.replace(target)
        record = ArtifactRecord(
            stage_id=stage_id,
            name=name,
            version=version,
            filename=filename,
            path=str(target),
            checksum=_sha256(data),
            size_bytes=len(data),
            kind=kind,
        )
        self._records[f"{stage_id}:{name}"] = record
        return record


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
