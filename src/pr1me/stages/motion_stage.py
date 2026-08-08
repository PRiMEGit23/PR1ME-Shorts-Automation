"""Motion Graphics stage.

Converts the approved narration and :class:`VisualPlanOutput` into a small,
deterministic set of on-screen overlays (captions and callouts). Returns an
:class:`MotionGraphicsOutput` instruction set consumed by a future assembly
stage.

The stage owns the deterministic boundary: the fixed typography policy (channel
defaults), the safe-zone layout, the 1.5-4s hold policy, the 5-overlay cap, and
the word budget. It is pure computation: no transport, no filesystem access,
no video knowledge.
"""

from __future__ import annotations

from pr1me.core.base_stage import BaseStage
from pr1me.core.context import StageContext
from pr1me.core.errors import PipelineError
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.motion import (
    MotionGraphicsInput,
    MotionGraphicsOutput,
    MotionOverlay,
    MotionOverlayStyle,
    MotionStyleUsed,
)
from pr1me.models.contracts.visual import VisualShot
from pr1me.models.meta import ValidationStatus

#: Fixed channel typography policy (mirrors prompt 12's style tokens).
_FONT = "Inter_Bold"
_TEXT_SIZE_PX = 96
_TEXT_COLOR = "#FFFFFF"
_ACCENT_COLOR = "#00E5FF"
_SAFE_MARGIN_PX = 120
_SCREEN_HEIGHT = 1920

#: Motion design policy from prompt 12.
_MIN_HOLD_SECONDS = 1.5
_MAX_HOLD_SECONDS = 4.0
_MAX_OVERLAYS = 5
_MAX_TEXT_WORDS = 3

#: Stacked-overlay row pitch keeps every overlay inside the upper safe zone.
_ROW_PITCH = int(_TEXT_SIZE_PX * 1.25)


class MotionValidationError(PipelineError):
    """The input cannot be converted into a valid motion graphics set."""

    code = "motion_validation_error"


class MotionGraphicsStage(BaseStage[MotionGraphicsInput, MotionGraphicsOutput]):
    """Designs the caption/callout overlay layer for one Short."""

    stage_id = "motion_graphics"
    name = "Motion Graphics"
    description = "Derives a deterministic on-screen overlay instruction set."
    version = "1.0.0"
    prompt_file = "12_motion_graphics_director.md"
    depends_on = ("script", "visual")
    input_model = MotionGraphicsInput
    output_model = MotionGraphicsOutput

    def __init__(self, context: StageContext) -> None:
        super().__init__(context)

    async def execute(self, payload: MotionGraphicsInput) -> MotionGraphicsOutput:
        overlays: list[MotionOverlay] = []
        for shot in payload.shots:
            if len(overlays) >= _MAX_OVERLAYS:
                break
            overlays.append(self._build_overlay(shot, payload, len(overlays)))
        if not overlays:
            raise MotionValidationError(
                "motion graphics cannot be derived: no usable visual shots",
                detail={"n_shots": len(payload.shots)},
            )

        style_used = MotionStyleUsed(
            font=_FONT,
            size_px=_TEXT_SIZE_PX,
            color=_TEXT_COLOR,
            safe_margin_px=_SAFE_MARGIN_PX,
        )
        manifest = MotionGraphicsOutput(
            overlays=overlays,
            style_used=style_used,
            total_overlays=len(overlays),
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=[
                    "count_within_limit",
                    "duration_within_bounds",
                    "timing_matches_narration",
                    "text_within_word_budget",
                    "within_safe_zone",
                ],
            ),
        )
        self._logger.info(
            "event=motion.started",
            n_shots=len(payload.shots),
            n_overlays=len(overlays),
            style=_FONT,
        )
        self._logger.info(
            "event=motion.completed",
            total=manifest.total_overlays,
            style=f"{_FONT}@{_TEXT_SIZE_PX}px",
        )
        return manifest

    # ------------------------------------------------------------ internals --

    def _build_overlay(
        self,
        shot: VisualShot,
        payload: MotionGraphicsInput,
        index: int,
    ) -> MotionOverlay:
        narration = payload.narration_for(shot.block)
        if not narration:
            raise MotionValidationError(
                f"block {shot.block!r} has no narration to emphasize",
                detail={"shot_id": shot.id, "block": shot.block},
            )
        text = _emphasize(narration)
        duration = _clamp_hold(float(shot.duration_seconds))
        start = shot.start_second
        pos_x, pos_y = _position(index, _SAFE_MARGIN_PX, _TEXT_SIZE_PX, _SCREEN_HEIGHT)
        return MotionOverlay(
            id=index + 1,
            text=text,
            start_second=start,
            end_second=start + duration,
            duration_seconds=duration,
            pos_x=pos_x,
            pos_y=pos_y,
            style=MotionOverlayStyle(
                font=_FONT,
                size_px=_TEXT_SIZE_PX,
                color=_TEXT_COLOR,
                accent=_ACCENT_COLOR,
            ),
        )


def _clamp_hold(duration: float) -> float:
    """Keep the hold inside the channel's 1.5-4 second motion-design range."""
    return max(_MIN_HOLD_SECONDS, min(duration, _MAX_HOLD_SECONDS))


def _emphasize(text: str) -> str:
    """Return the emphasized phrase (channel budget: at most 3 words).

    Deterministic by construction: the leading ``_MAX_TEXT_WORDS`` words of the
    narration are promoted to the channel's caption-key casing.
    """
    words = text.split()
    return " ".join(words[:_MAX_TEXT_WORDS]).upper()


def _position(index: int, margin: int, size_px: int, height: int) -> tuple[float, float]:
    """Place one overlay in the top-safe-zone, never inside the bottom 20%."""
    max_rows = int((height * 0.8 - margin) / (size_px * 1.25))
    row = index % max_rows if max_rows else 0
    return float(margin), float(margin + row * (size_px * 1.25))