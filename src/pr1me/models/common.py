"""Shared, typed value descriptors defined by PIPELINE_SPEC.md.

These models encode the shared JSON shapes used across stage handoffs, so stage
contracts never redefine them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pr1me.models.meta import ValidationStatus


class StableModel(BaseModel):
    """Base model for all pipeline JSON contracts.

    JSON-only stage handoffs serialize via ``model_dump_json``. Extra fields are
    forbidden so a contract violation fails fast instead of silently passing
    unknown data downstream.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class FileDescriptor(StableModel):
    """``{ "file": string }`` exact pipeline path to one artifact."""

    file: str


class Resolution(StableModel):
    """``{ "width": number, "height": number }`` pixel descriptor."""

    width: int
    height: int


class TimedMedia(FileDescriptor):
    """Timed media descriptor: file plus a start/end window in seconds."""

    start_second: float
    end_second: float


class ValidationDescriptor(StableModel):
    """Shared validation block used across stage outputs.

    ``status`` is ``ok`` only when every required check passes.
    """

    status: ValidationStatus = ValidationStatus.OK
    checks: list[str] = Field(default_factory=list)


class FailureDescriptor(StableModel):
    """Shared failure shape ``{"status": "failed", "reason": string}``.

    Prompts may extend this with extra fields (e.g. ``stage``, ``missing``).
    """

    status: Literal["failed"] = "failed"
    reason: str


class AttemptFailure(FailureDescriptor):
    """A stage failure payload written to the JSON artifact store."""

    stage: str | None = None


class ScriptBlock(StableModel):
    """The four-block script shape shared by script, fact-check, voice stages."""

    hook: str
    explanation: str
    practical_insight: str
    ending: str

    def full_text(self) -> str:
        return " ".join(
            (self.hook, self.explanation, self.practical_insight, self.ending)
        )


class ScriptCorrections(StableModel):
    """Fact-checker correction block; null means the block needs no fix."""

    hook: str | None = None
    explanation: str | None = None
    practical_insight: str | None = None
    ending: str | None = None