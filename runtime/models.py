"""Runtime schemas: the closed-loop generation contracts.

Phase 6 wires every knowledge subsystem into one deterministic loop:
render -> QA -> optimize -> render again until PASS or the retry budget
runs out. This module defines the runtime's own data shapes - attempts,
history, session results - and the content fingerprint that guarantees
"never repeat an identical render" and "same row + seed reproduces the same
sequence".
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from knowledge.image_qa.qa_models import GeneratedImageMetadata, ImageQualityReport
from knowledge.render_optimizer import OptimizedRenderPlan, RenderProfileKey
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from runtime.history import RenderHistory

RUNTIME_VERSION = "1.0.0"
DEFAULT_MAX_ATTEMPTS = 3
WORKFLOW_VERSION = "1.0.0"


def fingerprint_of(
    prompt: str,
    negative_prompt: str | None,
    workflow: dict,
    seed: int,
) -> str:
    """Content fingerprint of one render request.

    Two renders with the same (prompt, negative prompt, workflow, seed) are
    the identical render: same bytes, same QA outcome. The fingerprint is
    the sha256 over the canonical JSON of all four inputs.
    """
    canonical = json.dumps(
        {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "workflow": workflow,
            "seed": seed,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AttemptStatus(StrEnum):
    """Lifecycle of one render attempt inside the loop."""

    RENDERED = "rendered"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    MODEL_SWITCHED = "model_switched"


class RenderRequest(BaseModel):
    """Everything the renderer needs for one deterministic render."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_index: int = Field(ge=1)
    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    workflow: dict = Field(default_factory=dict)
    workflow_profile: RenderProfileKey
    seed: int
    image_model: str | None = None


class RenderResult(BaseModel):
    """What the renderer returns: observed metadata plus the image bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metadata: GeneratedImageMetadata
    image_bytes: bytes = Field(min_length=1)


class RenderAttempt(BaseModel):
    """One saved attempt: inputs, outputs, QA verdict, optimization plan."""

    model_config = ConfigDict(extra="forbid")

    attempt_id: str = Field(pattern=r"^attempt_\d{2,}$")
    index: int = Field(ge=1)
    status: AttemptStatus
    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    workflow: dict = Field(default_factory=dict)
    workflow_profile: RenderProfileKey
    seed: int
    fingerprint: str = Field(min_length=64, max_length=64)
    image_sha256: str = Field(min_length=64, max_length=64)
    image_model: str | None = None
    image_path: Path | None = None
    qa_report: ImageQualityReport | None = None
    optimization_report: OptimizedRenderPlan | None = None
    rationale: str = Field(default="", max_length=400)


class SessionConfig(BaseModel):
    """Configuration for one rendering session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=DEFAULT_MAX_ATTEMPTS, ge=1, le=10)
    model_key: str = Field(default="sdxl", min_length=1, max_length=40)
    output_root: Path = Field(default=Path("output/runtime"))
    save_artifacts: bool = True


class RenderSessionResult(BaseModel):
    """The complete outcome of one closed-loop session for one scene."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = RUNTIME_VERSION
    topic: str = Field(min_length=1, max_length=200)
    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    seed: int
    max_attempts: int = Field(ge=1, le=10)
    passed: bool
    winner: RenderAttempt | None = None
    attempts: list[RenderAttempt] = Field(default_factory=list, max_length=12)

    @property
    def attempts_used(self) -> int:
        """How many renders actually executed (switches and skips excluded)."""
        return sum(
            1
            for a in self.attempts
            if a.status
            not in (AttemptStatus.SKIPPED_DUPLICATE, AttemptStatus.MODEL_SWITCHED)
        )

    @property
    def history(self) -> RenderHistory:
        from runtime.history import RenderHistory

        return RenderHistory(
            topic=self.topic,
            scene_id=self.scene_id,
            seed=self.seed,
            max_attempts=self.max_attempts,
            attempts=self.attempts,
        )


def topic_slug(topic: str) -> str:
    """Deterministic directory-safe slug for a topic."""
    slug = "".join(ch if ch.isalnum() else "_" for ch in topic.lower())
    return slug.strip("_")[:60] or "topic"


def attempt_dir(
    output_root: Path,
    topic: str,
    scene_id: str,
    attempt_id: str,
) -> Path:
    """Where one attempt's artifacts live on disk."""
    return output_root / topic_slug(topic) / scene_id / attempt_id