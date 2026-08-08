"""Video Render stage contract (final encoded Short + verification report).

The stage consumes the frame-accurate :class:`AssemblyOutput`, encodes one
vertical MP4 through a configurable renderer backend, and returns a single
:class:`RenderManifestOutput` describing the verified deliverable.

Because the pipeline runner flattens every upstream output into one dict,
:class:`RenderInput` extends the assembly's output schema with ``extra``
ignored, so the topic/script leftovers riding along the flattened payload do
not fail validation.

These models are plain data: no transport, no FFmpeg knowledge, no probes.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from pr1me.models.common import StableModel, ValidationDescriptor
from pr1me.models.contracts.assembly import AssemblyOutput
from pr1me.models.contracts.base import StageOutput


class RenderMetadata(StableModel):
    """Technical properties read back from the encoded deliverable."""

    codec: str = Field(..., min_length=1)
    container: str = Field(..., min_length=1)
    fps: int = Field(..., ge=1, le=240)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    duration_seconds: float = Field(..., ge=0.0)
    audio_codec: str = Field(..., min_length=1)
    checksum: str = Field(..., min_length=1)
    backend: str = Field(..., min_length=1)


class RenderManifestOutput(StageOutput):
    """The verification report for the single encoded Short.

    ``file`` points at the exact deliverable and is the only media artifact
    referenced by the manifest. ``validation`` is ``ok`` only when every
    technical check passed.
    """

    output_dir: str
    file: str = Field(..., min_length=1)
    bytes: int = Field(..., ge=0)
    metadata: RenderMetadata
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)


class RenderInput(AssemblyOutput):
    """Input for the video render stage.

    Structurally identical to the assembly plan the stage consumes. ``extra``
    is ignored because the pipeline runner feeds the flattened outputs of
    every upstream stage alongside the plan.
    """

    model_config = ConfigDict(extra="ignore")