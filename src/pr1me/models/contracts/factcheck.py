"""Fact-check stage contract (prompt 03)."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from pr1me.models.common import ScriptCorrections, StableModel
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.meta import Confidence, Severity


class FactCheckInput(StageInput):
    """Input for the fact-checker stage: the script produced by prompt 02.

    The runner feeds the flattened outputs of the upstream stages; only the
    narration blocks plus the topic seed are consumed here.
    """

    model_config = ConfigDict(extra="ignore")

    topic: str | None = Field(default=None, min_length=1)
    hook: str
    explanation: str
    practical_insight: str
    ending: str
    word_count: int | None = Field(default=None, ge=1, le=120)


class Finding(StableModel):
    """Per-block finding returned by the fact-checker."""

    block: str
    claim: str
    defensible: bool
    note: str


class FactSummaryOutput(StageOutput):
    """Verdict for the supplied script. Mirrors prompt 03's schema."""

    verdict: str  # approved | needs_correction
    confidence: Confidence
    severity: Severity
    findings: list[Finding] = Field(default_factory=list)
    corrections: ScriptCorrections = Field(default_factory=ScriptCorrections)