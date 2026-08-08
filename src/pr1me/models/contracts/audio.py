"""Audio Mixing stage contract (mastered audio track).

The stage consumes the flattened outputs of the voice and image stages, loads
the optional background music and sound effects, mixes everything into one
mastered audio file, and returns a single :class:`AudioManifestOutput` that
describes the resulting asset.

Because the pipeline runner flattens every upstream output into one dict, only
the uniquely-named columns survive intact. :class:`AudioMixInput` carries the
``assets`` list from the :class:`VoiceManifestOutput` (the narration file) and
the ``images`` list from the :class:`ImageManifestOutput` (for provenance);
everything else is ignored.

These models are plain data: no transport, no subprocesses, no FFmpeg
knowledge.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from pr1me.models.common import StableModel, ValidationDescriptor
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.contracts.image import ImageAsset
from pr1me.models.contracts.voice import VoiceAsset


class AudioMetadata(StableModel):
    """Mastering metadata attached to the generated audio asset.

    Records the sources (narration, optional BGM, optional SFX), the target
    loudness and sample rate, the measured result, and the backend that
    produced the mix.
    """

    narration_file: str
    bgm_file: str | None = None
    sfx_file: str | None = None
    target_lufs: int = Field(..., ge=-100, le=0)
    target_sample_rate: int = Field(..., ge=1, le=768000)
    duration_seconds: float = Field(..., ge=0.0)
    backend: str
    checksum: str


class AudioAsset(StableModel):
    """One mastered audio asset referenced from the manifest."""

    file: str
    bytes: int = Field(..., ge=0)
    sample_rate: int = Field(..., ge=1, le=768000)
    duration_seconds: float = Field(..., ge=0.0)
    checksum: str
    metadata: AudioMetadata


class AudioManifestOutput(StageOutput):
    """A manifest of the mastered narration track.

    The mix stage produces exactly one mastered audio file, so ``assets`` holds
    a single entry and ``total`` is ``1`` when the run succeeds. ``validation``
    is ``ok`` only when the mix passed the post-processing checks.
    """

    output_dir: str
    assets: list[AudioAsset] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)


class AudioMixInput(StageInput):
    """Input for the audio mixing stage.

    ``assets`` carries the narration file produced by the voice stage;
    ``images`` carries the generated image manifests for provenance. ``extra``
    is ignored because the runner feeds the flattened outputs of every upstream
    stage alongside these.
    """

    model_config = ConfigDict(extra="ignore")

    assets: list[VoiceAsset] = Field(default_factory=list)
    images: list[ImageAsset] = Field(default_factory=list)
