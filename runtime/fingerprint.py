"""Deterministic fingerprints for the production pipeline.

Phase 7 orchestration is content-addressed: every stage computes a sha256
fingerprint over the canonical JSON of its version plus its exact inputs, so
a resumed run can prove "this stage already produced exactly this output"
and skip it. The same canonicalization feeds artifact versioning: an
artifact's version is the short fingerprint of the payload it carries, which
makes every stored file immutable and traceable back to the stage run that
wrote it.

Nothing here depends on clocks, randomness, or models.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

FINGERPRINT_VERSION = "1.0.0"

#: Length of the fingerprint prefix used as the artifact version token.
VERSION_LENGTH = 12


def canonical_json(payload: Any) -> str:
    """Serialize ``payload`` to canonical JSON (sorted keys, compact).

    Pydantic models, enums, and paths are normalized so that two logically
    equal objects always produce the same string. This is the single
    serialization path for both stage fingerprints and artifact payloads.
    """
    return json.dumps(
        _normalize(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, set):
        return sorted(_normalize(item) for item in value)
    return value


def fingerprint(payload: Any, *, salt: str | None = None) -> str:
    """sha256 over the canonical JSON of ``payload`` (optionally salted).

    The salt is for pipeline-level stability (e.g. a schema version) and is
    hashed first, so fingerprint("a", salt="x") != fingerprint("a", salt="y").
    """
    material = canonical_json(payload)
    if salt is not None:
        material = f"{salt}\n{material}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def stage_fingerprint(stage_id: str, version: str, inputs: dict[str, Any]) -> str:
    """Fingerprint of one stage execution: identity + version + exact inputs.

    Two executions of the same stage with the same version and identical
    inputs are the same execution; anything the stage could read that changes
    its output must appear in ``inputs``.
    """
    return fingerprint(
        {
            "stage_id": stage_id,
            "stage_version": version,
            "inputs": inputs,
        },
        salt=FINGERPRINT_VERSION,
    )


def artifact_version(payload_fingerprint: str) -> str:
    """The version token for an artifact: the short payload fingerprint.

    Two artifacts with identical bytes share the same version; any content
    change produces a new version, which makes stored artifacts immutable
    and cache-friendly.
    """
    return payload_fingerprint[:VERSION_LENGTH]
