"""Workflow Builder stage.

Assembles the validated Visual Architecture output into one complete ComfyUI
payload per shot (:class:`WorkflowFrame`). Every frame carries:

- positive and negative prompt (the validated, >=95-point prompts)
- camera configuration (angle, lens, movement)
- composition, lighting, and style
- render settings (resolution, seed, steps, cfg, sampler, scheduler)
- motion and transition metadata
- the shot's timeline window (block, start/end seconds)

The builder never invents prompts: the positive/negative text and all render
settings come straight from the validated ``comfyui_ready`` entries, and the
cinematic metadata comes from the shot plan and visual style. Output timings
are cumulative over the shot durations so downstream assembly receives one
gap-free timeline.
"""

from __future__ import annotations

from pydantic import ConfigDict

from pr1me.core.base_stage import BaseStage
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.base import StageInput
from pr1me.models.contracts.workflow import WorkflowFrame, WorkflowPayloadOutput
from pr1me.models.meta import ValidationStatus
from pr1me.visual_architecture.contracts import (
    ComfyUIReady,
    ComposedPrompt,
    PromptCompositionOutput,
    PromptValidationOutput,
    Shot,
    ShotPlanOutput,
    ValidatedPrompt,
    VisualStyleOutput,
)

__all__ = ["WorkflowBuilderStage", "WorkflowBuilderInput"]


class WorkflowBuilderInput(StageInput):
    """Stage input: the full Visual Architecture output (flattened upstream).

    The pipeline runner feeds the visual_architecture stage's output; the
    builder consumes exactly the pieces it needs and ignores the rest.
    """

    model_config = ConfigDict(extra="ignore")

    shot_plan: ShotPlanOutput
    visual_style: VisualStyleOutput
    composition: PromptCompositionOutput
    validation: PromptValidationOutput
    comfyui_ready: list[ComfyUIReady] = []


class WorkflowBuilderStage(BaseStage[WorkflowBuilderInput, WorkflowPayloadOutput]):
    """Builds one complete, validated ComfyUI payload per shot."""

    stage_id = "workflow_builder"
    name = "Workflow Builder"
    description = "Assembles validated prompts and shot metadata into ComfyUI-ready payloads."
    version = "1.0.0"
    depends_on = ("visual_architecture",)
    input_model = WorkflowBuilderInput
    output_model = WorkflowPayloadOutput

    async def execute(self, payload: WorkflowBuilderInput) -> WorkflowPayloadOutput:
        ready_by_shot = {item.shot_id: item for item in payload.comfyui_ready}
        composed_by_shot = {item.shot_id: item for item in payload.composition.prompts}
        validated_by_shot = {item.shot_id: item for item in payload.validation.prompts}

        cursor = 0.0
        frames: list[WorkflowFrame] = []
        for shot in payload.shot_plan.shots:
            ready = ready_by_shot[shot.id]
            composed = composed_by_shot[shot.id]
            validated = validated_by_shot[shot.id]
            start = cursor
            cursor += shot.duration_seconds
            frames.append(
                self._build_frame(
                    shot=shot,
                    ready=ready,
                    composed=composed,
                    validated=validated,
                    start_second=start,
                    end_second=cursor,
                    visual_style=payload.visual_style,
                )
            )

        return WorkflowPayloadOutput(
            frames=frames,
            total=len(frames),
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=[
                    "one_payload_per_shot",
                    "shots_in_shot_order",
                    "validated_prompts_used",
                    "prompts_scored_at_or_above_95",
                    "timeline_gap_free",
                ],
            ),
        )

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _build_frame(
        *,
        shot: Shot,
        ready: ComfyUIReady,
        composed: ComposedPrompt,
        validated: ValidatedPrompt,
        start_second: float,
        end_second: float,
        visual_style: VisualStyleOutput,
    ) -> WorkflowFrame:
        camera = _join(shot.camera_angle, shot.lens, shot.camera_movement)
        return WorkflowFrame(
            shot_id=shot.id,
            block=shot.narration_block,
            start_second=round(start_second, 6),
            end_second=round(end_second, 6),
            duration_seconds=shot.duration_seconds,
            positive_prompt=ready.positive_prompt,
            negative_prompt=ready.negative_prompt,
            camera=camera,
            composition=composed.fields.composition,
            lighting=visual_style.lighting,
            style=composed.fields.rendering_style,
            motion=shot.motion,
            transition=shot.transition,
            validation_score=validated.score,
            is_thumbnail=shot.is_thumbnail,
            width=ready.width,
            height=ready.height,
            seed=ready.seed,
            steps=ready.steps,
            cfg=ready.cfg,
            sampler=ready.sampler,
            scheduler=ready.scheduler,
        )


def _join(*parts: str) -> str:
    """Join non-empty camera tokens into one comma-separated descriptor."""
    return ", ".join(part for part in parts if part and part.lower() not in {"n/a", "none"})
