"""Fact-check stage contract (prompt 03)."""

from __future__ import annotations

from pydantic import Field

from pr1me.models.common import ScriptCorrections
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.meta import Confidence, Severity


class FactCheckInput(StageInput):
    """Input for the fact-checker stage."""

    topic: str = Field(..., min_length=1)
    script_hook: str
    script_explanation: str
    script_practical_insight: str
    script_ending: str
    word_count: int | None = Field(default=None, ge=1, le=120)


class Finding(StageOutput):
    """Per-block finding."""

    block: str
    claim: str
    defensible: bool
    note: str


class FactCheckOutput(StageOutput):
    """Verdict for the supplied script. Mirrors prompt 03's schema."""

    verdict: str  # approved | needs_correction
    confidence: Confidence
    severity: Severity
    findings: list[Finding] = Field(default_factory=list)
    corrections: ScriptCorrections = Field(default_factory=ScriptCorrections)