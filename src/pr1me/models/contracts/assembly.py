"""Video Assembly stage contract (master timeline / EDL builder).

The stage consumes the rendered images, the mastered audio, and the motion
graphics overlays, then derives a frame-accurate master timeline for one Short.
It returns a single :class:`AssemblyOutput` describing every cut, placement,
and overlay timestamp an automated renderer can execute without judgment.

Because the pipeline runner flattens every upstream output into one dict, only
the uniquely-named columns survive intact. :class:`VideoAssemblyInput` carries
the ``images`` list from the :class:`ImageManifestOutput`, the ``overlays`` list
from the :class:`MotionGraphicsOutput`, and the ``assets`` list from the
:class:`AudioManifestOutput`. The voice manifest's narration file reaches this
stage as provenance on the mastered audio asset
(``AudioMetadata.narration_file``); every other upstream field is ignored.

These models are plain data: no transport, no FFmpeg, no rendering knowledge.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from pr1me.models.common import Resolution, StableModel, ValidationDescriptor
from pr1me.models.contracts.audio import AudioAsset
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.contracts.image import ImageAsset
from pr1me.models.contracts.motion import MotionOverlay, MotionOverlayStyle


class VideoClip(StableModel):
    """One rendered shot placed on the video track, in shot order."""

    shot_id: int = Field(..., gt=0)
    file: str = Field(..., min_length=1)
    start_frame: int = Field(..., ge=0)
    end_frame: int = Field(..., gt=0)
    start_second: float = Field(..., ge=0.0)
    end_second: float = Field(..., gt=0.0)
    transition: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _frames_span_forward(self) -> VideoClip:
        if self.end_frame <= self.start_frame:
            raise ValueError("end_frame must be greater than start_frame")
        return self


class VoiceTrack(StableModel):
    """The narration placement on the master timeline."""

    file: str = Field(..., min_length=1)
    start_frame: int = Field(..., ge=0)
    end_frame: int = Field(..., gt=0)
    volume: float = Field(..., ge=0.0, le=1.0)


class AudioTrack(StableModel):
    """The mastered audio placement; ducking was already applied upstream."""

    file: str = Field(..., min_length=1)
    start_frame: int = Field(..., ge=0)
    end_frame: int = Field(..., gt=0)
    volume: float = Field(..., ge=0.0, le=1.0)
    duck_during_voice: bool


class AssemblyOverlay(StableModel):
    """One motion-graphics overlay pinned to a single shot on the timeline."""

    id: int
    text: str = Field(..., min_length=1)
    start_frame: int = Field(..., ge=0)
    end_frame: int = Field(..., gt=0)
    track_index: int = Field(..., ge=0)
    pos_x: float = Field(..., ge=0.0)
    pos_y: float = Field(..., ge=0.0)
    style: MotionOverlayStyle


class AssemblyTracks(StableModel):
    """The track stack: video base, voice, mastered audio, overlays."""

    video: list[VideoClip] = Field(default_factory=list)
    voice: VoiceTrack
    audio: AudioTrack
    overlays: list[AssemblyOverlay] = Field(default_factory=list)


class AssemblyFile(StableModel):
    """One media file placed on the timeline, keyed by its role."""

    kind: Literal["video", "voice", "audio"]
    file: str = Field(..., min_length=1)
    start_frame: int = Field(..., ge=0)
    end_frame: int = Field(..., gt=0)


class AssemblyCut(StableModel):
    """One cut between two adjacent shots on the master timeline."""

    cut_at_frame: int = Field(..., ge=0)
    from_shot: int = Field(..., gt=0)
    to_shot: int = Field(..., gt=0)
    transition: str = Field(..., min_length=1)


class AssemblyOutput(StageOutput):
    """The machine-executable master timeline for one Short.

    ``total_frames`` equals ``fps * total_seconds`` where ``total_seconds`` is
    the visual plan's total duration. Every track lists media by exact file
    path and exact frame range. ``validation`` is ``ok`` only when every
    assembly check passed.
    """

    total_frames: int = Field(..., gt=0)
    fps: int = Field(..., ge=1, le=240)
    resolution: Resolution
    tracks: AssemblyTracks
    files: list[AssemblyFile] = Field(default_factory=list)
    cut_list: list[AssemblyCut] = Field(default_factory=list)
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)


class VideoAssemblyInput(StageInput):
    """Input for the video assembly stage.

    ``images`` carries the rendered shots in plan order, ``overlays`` the
    motion graphics layer, and ``assets`` the mastered audio produced by the
    audio mix stage. ``extra`` is ignored because the pipeline runner feeds the
    flattened outputs of every upstream stage alongside these.
    """

    model_config = ConfigDict(extra="ignore")

    images: list[ImageAsset] = Field(default_factory=list)
    overlays: list[MotionOverlay] = Field(default_factory=list)
    assets: list[AudioAsset] = Field(default_factory=list)
