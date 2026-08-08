"""Typed data contracts for the pipeline.

Subpackage ``models.contracts`` holds one input/output model pair per stage.
``models.meta`` and ``models.common`` hold the shared enums and descriptors from
PIPELINE_SPEC.md.
"""

from pr1me.models.common import (
    FailureDescriptor,
    FileDescriptor,
    Resolution,
    ScriptBlock,
    ScriptCorrections,
    StableModel,
    TimedMedia,
    ValidationDescriptor,
)
from pr1me.models.meta import (
    AssetCategory,
    ChangeType,
    Confidence,
    RunStatus,
    Severity,
    StageStatus,
    ValidationStatus,
    VerificationVerdict,
    Visibility,
)

__all__ = [
    "AssetCategory",
    "ChangeType",
    "Confidence",
    "FailureDescriptor",
    "FileDescriptor",
    "Resolution",
    "RunStatus",
    "ScriptBlock",
    "ScriptCorrections",
    "Severity",
    "StableModel",
    "StageStatus",
    "TimedMedia",
    "ValidationDescriptor",
    "ValidationStatus",
    "VerificationVerdict",
    "Visibility",
]