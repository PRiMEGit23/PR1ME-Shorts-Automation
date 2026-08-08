"""Shared status values and common scalar enums from PIPELINE_SPEC.md.

Stage-specific enums (visual types, curiosity triggers, etc.) live next to
their stage contract in :mod:`pr1me.models.contracts`.
"""

from __future__ import annotations

from enum import StrEnum


class StageStatus(StrEnum):
    """Pipeline-orchestrated stage status. Values come from PIPELINE_SPEC."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"
    BLOCKED = "blocked"


class RunStatus(StrEnum):
    """Overall orchestration result for a job."""

    COMPLETE = "complete"
    FAILED = "failed"
    PARTIAL = "partial"


class ValidationStatus(StrEnum):
    """Shared validation descriptor status."""

    OK = "ok"
    FAILED = "failed"


class VerificationVerdict(StrEnum):
    """Used by fact-check and quality gates: pass / needs work / rejection."""

    PASS = "PASS"
    REWORK = "REWORK"
    REJECT = "REJECT"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Severity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    NONE = "none"


class ChangeType(StrEnum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


class AssetCategory(StrEnum):
    """Shared asset categories from PIPELINE_SPEC."""

    BROLL = "broll"
    MUSIC = "music"
    SFX = "sfx"
    FONT = "font"
    LOGO = "logo"
    OVERLAY = "overlay"


class Visibility(StrEnum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    SCHEDULED = "scheduled"
