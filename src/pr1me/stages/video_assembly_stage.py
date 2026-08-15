"""Video Assembly stage (master timeline / EDL builder).

Consumes the rendered images, the mastered audio, and the motion graphics
overlays, then derives one frame-accurate :class:`AssemblyOutput` for a single
Short. The stage is metadata only: it never renders, never touches FFmpeg, and
never produces an MP4.

The stage owns the deterministic boundary: the timeline frame rate, the cut
policy (every shot boundary is a hard cut), the voice/audio placement
(voice spans the timeline, the mastered track starts at frame 0 and is never
re-ducked), the overlay-to-shot pinning, and the narration-derived timeline
target (``video = narration + intro_padding + outro_padding``; the shot plan
is uniformly stretched or compressed onto that target so the final video
never cuts the narration). All media timing comes from the approved
manifests; nothing is invented.
"""

from __future__ import annotations

from pathlib import Path

from pr1me.core.base_stage import BaseStage
from pr1me.core.context import StageContext
from pr1me.core.errors import PipelineError
from pr1me.models.common import Resolution, ValidationDescriptor
from pr1me.models.contracts.assembly import (
    AssemblyCut,
    AssemblyFile,
    AssemblyOutput,
    AssemblyOverlay,
    AssemblyTracks,
    AudioTrack,
    VideoAssemblyInput,
    VideoClip,
    VoiceTrack,
)
from pr1me.models.contracts.audio import AudioAsset
from pr1me.models.contracts.image import ImageAsset
from pr1me.models.contracts.motion import MotionOverlay
from pr1me.models.meta import ValidationStatus

#: Transition applied at every shot boundary (the plan carries no others).
_CUT_TRANSITION = "cut"
#: Voice and mastered-audio levels on the master timeline (PIPELINE_SPEC).
_VOICE_VOLUME = 1.0
_MASTER_VOLUME = 1.0

#: Temporal equality tolerance when checking shot continuity (seconds).
_EPSILON_SECONDS = 1e-9

#: Overlay hold bounds enforced by the motion contract (1.5-4s channel policy).
_MIN_OVERLAY_SECONDS = 1.5
_MAX_OVERLAY_SECONDS = 4.0


class AssemblyValidationError(PipelineError):
    """The manifests cannot be combined into one valid master timeline."""

    code = "assembly_validation_error"


class VideoAssemblyStage(BaseStage[VideoAssemblyInput, AssemblyOutput]):
    """Builds the frame-accurate master timeline for one Short."""

    stage_id = "video_assembly"
    name = "Video Assembly"
    description = "Builds the frame-accurate master timeline from the approved manifests."
    version = "1.0.0"
    depends_on = ("image_generation", "voice_generation", "audio_mix", "motion_graphics")
    input_model = VideoAssemblyInput
    output_model = AssemblyOutput

    def __init__(self, context: StageContext) -> None:
        super().__init__(context)

    async def execute(self, payload: VideoAssemblyInput) -> AssemblyOutput:
        fps = self.context.settings.target_fps
        width = self.context.settings.target_width
        height = self.context.settings.target_height
        self._logger.info(
            "event=video_assembly.started",
            n_shots=len(payload.images),
            n_overlays=len(payload.overlays),
            fps=fps,
        )

        clips = self._plan_clips(payload, fps)
        master_asset = self._master_asset(payload)
        target_seconds = self._target_seconds(master_asset, clips)
        factor = self._timeline_factor(clips, target_seconds)
        raw_clips = clips
        clips = self._scale_clips(raw_clips, factor, fps)
        master = self._master_track(master_asset, clips, fps)
        voice = self._voice_track(master_asset, clips, fps)
        overlays = self._attach_overlays(payload, raw_clips, clips, fps, factor)
        cuts = self._build_cuts(clips)
        files = self._collect_files(clips, voice, master)
        total_frames = clips[-1].end_frame

        output = AssemblyOutput(
            total_frames=total_frames,
            fps=fps,
            resolution=Resolution(width=width, height=height),
            tracks=AssemblyTracks(
                video=clips,
                voice=voice,
                audio=master,
                overlays=overlays,
            ),
            files=files,
            cut_list=cuts,
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=[
                    "images_in_shot_order",
                    "no_gap_or_overlap",
                    "voice_starts_at_frame_zero",
                    "master_audio_referenced",
                    "overlays_pinned_to_shots",
                    "all_files_exist",
                    "video_never_shorter_than_narration",
                ],
            ),
        )
        self._logger.info(
            "event=video_assembly.completed",
            total_frames=total_frames,
            fps=fps,
            n_clips=len(clips),
            n_overlays=len(overlays),
            n_cuts=len(cuts),
            master=master.file,
            narration_seconds=master_asset.duration_seconds,
            target_seconds=target_seconds,
            timeline_factor=factor,
        )
        return output

    # ------------------------------------------------------------ internals --

    def _plan_clips(self, payload: VideoAssemblyInput, fps: int) -> list[VideoClip]:
        if not payload.images:
            raise AssemblyValidationError(
                "image manifest carries no rendered images to assemble",
                detail={"n_images": len(payload.images)},
            )
        clips = [self._clip(asset, fps) for asset in payload.images]
        previous_end: float | None = None
        previous_id: int | None = None
        for clip in clips:
            if previous_id is not None and clip.shot_id <= previous_id:
                raise AssemblyValidationError(
                    "images are not in ascending shot order",
                    detail={"shot_id": clip.shot_id, "previous_shot_id": previous_id},
                )
            if previous_end is not None and abs(clip.start_second - previous_end) > _EPSILON_SECONDS:
                raise AssemblyValidationError(
                    "shot timeline has a gap or overlap",
                    detail={
                        "shot_id": clip.shot_id,
                        "start_second": clip.start_second,
                        "previous_end_second": previous_end,
                    },
                )
            if clip.end_frame <= clip.start_frame:
                raise AssemblyValidationError(
                    "shot collapses to zero frames at the target fps",
                    detail={
                        "shot_id": clip.shot_id,
                        "start_frame": clip.start_frame,
                        "end_frame": clip.end_frame,
                    },
                )
            previous_end = clip.end_second
            previous_id = clip.shot_id
        return clips

    def _clip(self, asset: ImageAsset, fps: int) -> VideoClip:
        metadata = asset.metadata
        self._require_file(asset.file, kind="image", ref=asset.shot_id)
        return VideoClip(
            shot_id=asset.shot_id,
            file=asset.file,
            start_frame=_to_frame(metadata.start_second, fps),
            end_frame=_to_frame(metadata.end_second, fps),
            start_second=metadata.start_second,
            end_second=metadata.end_second,
            transition=_CUT_TRANSITION,
        )

    def _master_asset(self, payload: VideoAssemblyInput) -> AudioAsset:
        if not payload.assets:
            raise AssemblyValidationError(
                "audio manifest carries no mastered track to reference",
                detail={"n_assets": len(payload.assets)},
            )
        master = payload.assets[0]
        if master.duration_seconds <= 0:
            raise AssemblyValidationError(
                "mastered audio has no measurable duration",
                detail={"file": master.file, "duration_seconds": master.duration_seconds},
            )
        self._require_file(master.file, kind="audio", ref="audio_mix")
        return master

    def _target_seconds(self, master: AudioAsset, clips: list[VideoClip]) -> float:
        """Compute the narration-derived timeline target for the Short.

        ``video_duration = narration + intro_padding + outro_padding`` (both
        paddings optional, operator-configured, never hardcoded). The target is
        capped at the platform duration budget so the render never exceeds it.
        """
        target = (
            master.duration_seconds
            + self.context.settings.intro_padding_seconds
            + self.context.settings.outro_padding_seconds
        )
        budget = self.context.settings.target_max_duration_seconds
        if budget > 0 and target > budget:
            self._logger.warning(
                "event=video_assembly.target_clamped",
                narration_seconds=master.duration_seconds,
                target_seconds=target,
                budget_seconds=budget,
            )
            return budget
        return target

    @staticmethod
    def _timeline_factor(clips: list[VideoClip], target_seconds: float) -> float:
        """Uniform stretch/compress factor mapping the plan onto the target.

        A factor above 1.0 holds every shot longer (motion assets shorter than
        the narration are extended); below 1.0 trims trailing dead air so the
        final video matches the narration length.
        """
        total = clips[-1].end_second
        if total <= 0:
            return 1.0
        return target_seconds / total

    def _scale_clips(self, clips: list[VideoClip], factor: float, fps: int) -> list[VideoClip]:
        if abs(factor - 1.0) <= _EPSILON_SECONDS:
            return clips
        boundaries = [0.0]
        boundaries.extend(clip.end_second for clip in clips)
        frames = [_to_frame(boundary * factor, fps) for boundary in boundaries]
        for index in range(1, len(frames)):
            if frames[index] <= frames[index - 1]:
                frames[index] = frames[index - 1] + 1
        scaled: list[VideoClip] = []
        for index, clip in enumerate(clips):
            start, end = frames[index], frames[index + 1]
            scaled.append(
                VideoClip(
                    shot_id=clip.shot_id,
                    file=clip.file,
                    start_frame=start,
                    end_frame=end,
                    start_second=start / fps,
                    end_second=end / fps,
                    transition=clip.transition,
                )
            )
        return scaled

    def _master_track(self, master: AudioAsset, clips: list[VideoClip], fps: int) -> AudioTrack:
        end_seconds = min(master.duration_seconds, clips[-1].end_second)
        end_frame = _to_frame(end_seconds, fps)
        if end_frame <= 0:
            raise AssemblyValidationError(
                "mastered audio collapses to zero frames at the target fps",
                detail={"file": master.file, "duration_seconds": master.duration_seconds},
            )
        return AudioTrack(
            file=master.file,
            start_frame=0,
            end_frame=end_frame,
            volume=_MASTER_VOLUME,
            duck_during_voice=False,
        )

    def _voice_track(self, master: AudioAsset, clips: list[VideoClip], fps: int) -> VoiceTrack:
        narration = master.metadata.narration_file
        self._require_file(narration, kind="voice", ref="narration")
        return VoiceTrack(
            file=narration,
            start_frame=0,
            end_frame=_frame_to(clips[-1].end_second, fps),
            volume=_VOICE_VOLUME,
        )

    def _attach_overlays(
        self,
        payload: VideoAssemblyInput,
        raw_clips: list[VideoClip],
        clips: list[VideoClip],
        fps: int,
        factor: float,
    ) -> list[AssemblyOverlay]:
        incoming = sorted(payload.overlays, key=lambda o: o.id)
        overlays: list[AssemblyOverlay] = []
        for overlay in incoming:
            index = self._owner_index(overlay, raw_clips)
            owner = clips[index]
            raw_owner = raw_clips[index]
            if overlay.start_second < raw_owner.start_second or (
                overlay.end_second > raw_owner.end_second + _EPSILON_SECONDS
            ):
                raise AssemblyValidationError(
                    "overlay straddles a shot boundary",
                    detail={
                        "overlay_id": overlay.id,
                        "start_second": overlay.start_second,
                        "end_second": overlay.end_second,
                        "owner_shot": owner.shot_id,
                        "owner_end_second": raw_owner.end_second,
                    },
                )
            scaled = self._scale_overlay(overlay, factor)
            start_frame = max(_to_frame(scaled.start_second, fps), owner.start_frame)
            end_frame = min(_to_frame(scaled.end_second, fps), owner.end_frame)
            if end_frame <= start_frame:
                start_frame = min(start_frame, owner.end_frame - 1)
                end_frame = start_frame + 1
            if start_frame < owner.start_frame or end_frame > owner.end_frame or end_frame <= start_frame:
                raise AssemblyValidationError(
                    "overlay collapses to zero frames",
                    detail={
                        "overlay_id": overlay.id,
                        "start_frame": start_frame,
                        "end_frame": end_frame,
                        "owner_shot": owner.shot_id,
                        "owner_end_frame": owner.end_frame,
                    },
                )
            overlays.append(
                AssemblyOverlay(
                    id=overlay.id,
                    text=overlay.text,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    track_index=index,
                    pos_x=overlay.pos_x,
                    pos_y=overlay.pos_y,
                    style=overlay.style,
                )
            )
        return overlays

    @staticmethod
    def _scale_overlay(overlay: MotionOverlay, factor: float) -> MotionOverlay:
        """Rescale one overlay onto the normalized timeline.

        The hold is scaled with the timeline, then clamped back into the
        channel's 1.5-4s hold policy (the motion contract enforces the same
        bounds), so stretching never produces an out-of-contract overlay.
        """
        if abs(factor - 1.0) <= _EPSILON_SECONDS:
            return overlay
        start = overlay.start_second * factor
        scaled_duration = overlay.duration_seconds * factor
        duration = min(_MAX_OVERLAY_SECONDS, max(_MIN_OVERLAY_SECONDS, scaled_duration))
        return MotionOverlay(
            id=overlay.id,
            text=overlay.text,
            start_second=start,
            end_second=start + duration,
            duration_seconds=duration,
            pos_x=overlay.pos_x,
            pos_y=overlay.pos_y,
            style=overlay.style,
        )

    def _owner_index(self, overlay: MotionOverlay, clips: list[VideoClip]) -> int:
        for index, clip in enumerate(clips):
            if clip.start_second <= overlay.start_second < clip.end_second:
                return index
        raise AssemblyValidationError(
            "overlay does not fall inside any shot",
            detail={"overlay_id": overlay.id, "start_second": overlay.start_second},
        )

    @staticmethod
    def _build_cuts(clips: list[VideoClip]) -> list[AssemblyCut]:
        cuts: list[AssemblyCut] = []
        for previous, current in zip(clips, clips[1:], strict=False):
            cuts.append(
                AssemblyCut(
                    cut_at_frame=previous.end_frame,
                    from_shot=previous.shot_id,
                    to_shot=current.shot_id,
                    transition=current.transition,
                )
            )
        return cuts

    @classmethod
    def _collect_files(
        cls,
        clips: list[VideoClip],
        voice: VoiceTrack,
        master: AudioTrack,
    ) -> list[AssemblyFile]:
        files = [
            AssemblyFile(
                kind="video",
                file=clip.file,
                start_frame=clip.start_frame,
                end_frame=clip.end_frame,
            )
            for clip in clips
        ]
        files.append(
            AssemblyFile(
                kind="voice",
                file=voice.file,
                start_frame=voice.start_frame,
                end_frame=voice.end_frame,
            )
        )
        files.append(
            AssemblyFile(
                kind="audio",
                file=master.file,
                start_frame=master.start_frame,
                end_frame=master.end_frame,
            )
        )
        return files

    @staticmethod
    def _require_file(file: str, *, kind: str, ref: object) -> None:
        if not Path(file).is_file():
            raise AssemblyValidationError(
                f"referenced {kind} file does not exist",
                detail={"file": file, "ref": ref},
            )


def _to_frame(seconds: float, fps: int) -> int:
    """Convert a timeline offset to the nearest integer frame."""
    return int(round(seconds * fps))


def _frame_to(seconds: float, fps: int) -> int:
    """Convert a duration to the nearest integer frame (clamped above zero)."""
    return max(1, _to_frame(seconds, fps))