"""Voice Generation stage contract (narration synthesis).

The stage consumes the approved :class:`ScriptOutput`, converts the four
narration blocks into exactly one audio file through a configurable TTS
backend, and returns a single :class:`VoiceManifestOutput` describing the
generated asset.

These models are plain data: no transport, no filesystem access, no TTS
engine knowledge.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from pr1me.models.common import StableModel, ValidationDescriptor
from pr1me.models.contracts.base import StageOutput
from pr1me.models.contracts.script import ScriptOutput

#: Audio encoding produced by the voice provider (PCM WAV by default).
VoiceFormat = str


class VoiceMetadata(StableModel):
    """Narration metadata attached to the generated audio asset.

    Records everything the manifest needs to audit or reproduce the synthesis:
    the exact spoken text, the configured voice, the sample rate, the encoding,
    the duration, and the backend that produced it.
    """

    text: str
    voice: str
    sample_rate: int = Field(..., ge=1, le=768000)
    format: str = Field(..., min_length=1)
    duration_seconds: float = Field(..., ge=0.0)
    provider: str
    checksum: str


class VoiceAsset(StableModel):
    """One narration audio asset referenced from the manifest."""

    file: str
    bytes: int = Field(..., ge=0)
    checksum: str
    metadata: VoiceMetadata


class VoiceManifestOutput(StageOutput):
    """A manifest of every narration generated for one script.

    The voice stage produces exactly one narration file, so ``assets`` holds a
    single entry and ``total`` is ``1`` when the run succeeds. ``validation``
    is ``ok`` only when the narration passed the post-synthesis checks.
    """

    output_dir: str
    assets: list[VoiceAsset] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)


class VoiceInput(ScriptOutput):
    """Input for the voice generation stage.

    Structurally identical to the approved script the stage consumes. ``extra``
    is ignored because the pipeline runner feeds the flattened outputs of every
    upstream stage (topic, fact-check, image manifest, ...) alongside the
    script.
    """

    model_config = ConfigDict(extra="ignore")
