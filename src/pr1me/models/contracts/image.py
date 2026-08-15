"""Image Generation stage contract (pipeline step between Visual and Assembly).

The stage consumes the approved :class:`VisualPlanOutput`, renders one image
per shot through a local ComfyUI server, and returns a single
:class:`ImageManifestOutput` that records every generated asset in shot order.

These models are plain data: no transport, no filesystem access, no ComfyUI
knowledge.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from pr1me.image_critic.contracts import ImageCritique, ImageQualityReport
from pr1me.models.common import StableModel, ValidationDescriptor
from pr1me.models.contracts.base import StageOutput
from pr1me.models.contracts.visual import ScriptBlockName, VisualPlanOutput
from pr1me.models.contracts.workflow import WorkflowFrame

#: Render strategy bucket used by downstream automation (mirrors prompt 07).
RenderPriority = str


class ImageSamplerSettings(StableModel):
    """Fixed, reproducible sampler settings for one render."""

    steps: int = Field(..., ge=1, le=150)
    cfg: float = Field(..., ge=0.0, le=20.0)
    sampler: str = Field(..., min_length=1)
    scheduler: str = Field(..., min_length=1)
    seed: int = Field(..., ge=0, le=2**63 - 1)


class ImageMetadata(StableModel):
    """Render metadata attached to one generated image asset.

    Records everything the manifest needs to reproduce or audit the render:
    the shot it belongs to, the exact prompt sent to ComfyUI, the sampler
    settings, the requested resolution, and the workflow provenance.
    """

    shot_id: int
    block: ScriptBlockName
    start_second: float
    end_second: float
    width: int
    height: int
    positive_prompt: str
    negative_prompt: str
    sampler_settings: ImageSamplerSettings
    render_priority: str
    workflow: str
    comfyui_prompt_id: str


class ImageAsset(StableModel):
    """One rendered image asset referenced from the manifest."""

    shot_id: int
    file: str
    width: int
    height: int
    checksum: str
    metadata: ImageMetadata
    critique: ImageCritique | None = None


class ImageManifestOutput(StageOutput):
    """An ordered manifest of every image generated for one visual plan.

    ``images`` preserves the visual plan's shot ordering. ``total`` is the
    count of successfully rendered assets. ``validation`` is ``ok`` only when
    every shot produced a render that passed the post-render checks. When the
    Image Critic is enabled, ``report`` carries the per-render critic scores,
    the rejected renders, and the run-level quality metrics.
    """

    output_dir: str
    images: list[ImageAsset] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)
    report: ImageQualityReport | None = None


class ImageGenerationInput(VisualPlanOutput):
    """Input for the image generation stage.

    Structurally identical to the visual plan the stage consumes, plus an
    optional list of validated :class:`WorkflowFrame` payloads produced by the
    Workflow Builder stage (its ``frames`` output is merged into this field by
    the runner). When ``frames`` is non-empty (and the legacy flag is off), the
    stage renders exactly those frames; otherwise it falls back to composing a
    prompt per shot from the visual plan. ``extra`` is ignored because the
    pipeline runner feeds the flattened outputs of every upstream stage
    alongside the plan.
    """

    model_config = ConfigDict(extra="ignore")

    frames: list[WorkflowFrame] = Field(default_factory=list)
