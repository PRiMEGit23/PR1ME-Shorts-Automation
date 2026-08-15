"""Workflow Builder stage contract.

The workflow builder turns the validated Visual Architecture output into one
complete, ready-to-render payload per shot. Each :class:`WorkflowFrame` carries
everything ComfyUI needs (positive/negative prompts plus the exact sampler
variables) alongside the cinematic metadata that downstream assembly uses
(block, timeline window, camera, composition, lighting, style, motion, and
transition), so nothing downstream ever re-derives or re-generates a prompt.
"""

from __future__ import annotations

from pydantic import Field

from pr1me.models.common import StableModel, ValidationDescriptor
from pr1me.models.contracts.base import StageOutput
from pr1me.models.contracts.visual import ScriptBlockName

__all__ = ["WorkflowFrame", "WorkflowPayloadOutput"]


class WorkflowFrame(StableModel):
    """One fully assembled, validated shot payload for the ComfyUI workflow.

    ``to_comfyui_variables`` returns exactly the variable set the existing
    ``workflows/comfyui.json`` template consumes, so the image generation stage
    hands the frame straight to the ComfyUI provider with no re-composition.
    """

    shot_id: int = Field(..., ge=1)
    block: ScriptBlockName
    start_second: float = Field(..., ge=0.0)
    end_second: float = Field(..., gt=0.0)
    duration_seconds: float = Field(..., gt=0.0)
    positive_prompt: str = Field(..., min_length=1)
    negative_prompt: str = Field(..., min_length=1)
    camera: str = Field(..., min_length=1)
    composition: str = Field(..., min_length=1)
    lighting: str = Field(..., min_length=1)
    style: str = Field(..., min_length=1)
    motion: str = Field(..., min_length=1)
    transition: str = Field(..., min_length=1)
    validation_score: int = Field(..., ge=0, le=100)
    is_thumbnail: bool = False
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    seed: int = Field(..., ge=0, le=2**63 - 1)
    steps: int = Field(..., ge=1, le=150)
    cfg: float = Field(..., ge=0.0, le=20.0)
    sampler: str = Field(..., min_length=1)
    scheduler: str = Field(..., min_length=1)

    def to_comfyui_variables(self) -> dict[str, object]:
        """Return the variable dict consumed by ``ComfyUIProvider.render``."""
        return {
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "width": self.width,
            "height": self.height,
            "seed": self.seed,
            "steps": self.steps,
            "cfg": self.cfg,
            "sampler": self.sampler,
            "scheduler": self.scheduler,
        }


class WorkflowPayloadOutput(StageOutput):
    """Stage 10 output: one complete ComfyUI payload per validated shot."""

    frames: list[WorkflowFrame] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)
