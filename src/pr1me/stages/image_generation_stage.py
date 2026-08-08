"""Image Generation stage (ComfyUI renderer).

Consumes the approved :class:`VisualPlanOutput`, renders exactly one image per
shot through the local ComfyUI server, then returns an ordered
:class:`ImageManifestOutput`.

The stage owns the deterministic boundary: the prompt composition from the
scene plan (mirroring prompt 07's token order), the fixed sampler policy, the
reproducible seed policy, and post-render validation. All transport lives in
:class:`~pr1me.providers.comfyui.ComfyUIProvider`.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from pr1me.core.base_stage import BaseStage
from pr1me.core.context import StageContext
from pr1me.core.errors import PipelineError, ProviderNotConfiguredError
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.image import (
    ImageAsset,
    ImageGenerationInput,
    ImageManifestOutput,
    ImageMetadata,
    ImageSamplerSettings,
)
from pr1me.models.contracts.visual import VisualShot
from pr1me.models.meta import ValidationStatus
from pr1me.providers.comfyui import ComfyUIProvider, ComfyUIRender, png_dimensions

_ENV_WORKFLOW = "PR1ME_COMFYUI_WORKFLOW"
_ENV_OUTPUT_DIR = "PR1ME_IMAGE_OUTPUT_DIR"

#: Deterministic seed policy so the same scene always renders the same image.
_SEED_BASE = 424242
_SEED_STEP = 7919

#: Fixed sampler policy (channel default, deterministic).
_DEFAULT_STEPS = 28
_DEFAULT_CFG = 7.0
_DEFAULT_SAMPLER = "euler_a"
_DEFAULT_SCHEDULER = "karras"

#: Render strategy bucket exposed to downstream automation.
_RENDER_PRIORITY = "Balanced"

#: Deterministic hygiene negatives (prompt 07 default library).
_NEGATIVE_PROMPT = (
    "blurry, low quality, low resolution, noise, watermark, logo, text, "
    "duplicate objects, deformed objects, incorrect geometry, cropped subject, "
    "oversaturation, cartoon, anime, unrealistic lighting, extra objects"
)


class ImageValidationError(PipelineError):
    """A generated image failed the post-render validation checks."""

    code = "image_validation_error"


class ImageGenerationStage(BaseStage[ImageGenerationInput, ImageManifestOutput]):
    """Renders one image per visual-plan shot via a local ComfyUI server."""

    stage_id = "image_generation"
    name = "Image Generation"
    description = "Renders one image per visual-plan shot via ComfyUI."
    version = "1.0.0"
    depends_on = ("visual",)
    input_model = ImageGenerationInput
    output_model = ImageManifestOutput

    def __init__(
        self,
        context: StageContext,
        *,
        comfyui_provider: ComfyUIProvider | None = None,
    ) -> None:
        self._comfyui = comfyui_provider
        super().__init__(context)

    async def execute(self, payload: ImageGenerationInput) -> ImageManifestOutput:
        provider = self._comfyui or self._default_provider()
        if provider is None:
            raise ProviderNotConfiguredError(
                "no ComfyUI provider is configured for the image generation stage"
            )
        settings = self.context.settings
        configured_dir = os.getenv(_ENV_OUTPUT_DIR)
        images_dir = Path(configured_dir) if configured_dir else settings.work_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        width = settings.target_width
        height = settings.target_height

        self._logger.info("event=image_generation.started", n_shots=len(payload.shots))

        assets: list[ImageAsset] = []
        for index, shot in enumerate(payload.shots):
            self._logger.info(
                "event=image_generation.shot",
                shot_id=shot.id,
                index=index,
                block=shot.block,
            )
            variables = self._render_variables(shot, index, width, height)
            rendered = await provider.render(variables, output_dir=images_dir)
            if not rendered:
                raise ImageValidationError(f"shot {shot.id} rendered no images", detail={"shot_id": shot.id})
            if len(rendered) > 1:
                self._logger.warning(
                    "event=image_generation.multiple_outputs",
                    shot_id=shot.id,
                    n_images=len(rendered),
                    note="keeping the first render",
                )
            final = self._finalize_path(rendered[0], images_dir, shot.id)
            assets.append(self._build_asset(shot, final, rendered[0], variables, provider))

        if len(assets) != len(payload.shots):
            raise ImageValidationError(f"expected {len(payload.shots)} images, got {len(assets)}")

        manifest = ImageManifestOutput(
            output_dir=str(images_dir),
            images=assets,
            total=len(assets),
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=[
                    "all_shots_rendered",
                    "images_in_shot_order",
                    *[f"shot_{shot.id:03d}_valid_png" for shot in payload.shots],
                ],
            ),
        )
        self._logger.info(
            "event=image_generation.completed",
            n_images=len(assets),
            output_dir=str(images_dir),
        )
        return manifest

    # ------------------------------------------------------------ internals --

    def _default_provider(self) -> ComfyUIProvider:
        workflow_file = os.getenv(_ENV_WORKFLOW)
        if not workflow_file:
            workflow_file = str(self.context.settings.repo_root / "workflows" / "comfyui.json")
        return ComfyUIProvider(workflow_file=workflow_file)

    def _render_variables(self, shot: VisualShot, index: int, width: int, height: int) -> dict[str, Any]:
        seed = (_SEED_BASE + (index + 1) * _SEED_STEP) % (2**63 - 1)
        positive = build_positive_prompt(shot)
        return {
            "positive_prompt": positive,
            "negative_prompt": _NEGATIVE_PROMPT,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": _DEFAULT_STEPS,
            "cfg": _DEFAULT_CFG,
            "sampler": _DEFAULT_SAMPLER,
            "scheduler": _DEFAULT_SCHEDULER,
        }

    def _finalize_path(self, rendered: ComfyUIRender, images_dir: Path, shot_id: int) -> Path:
        source = Path(rendered.file)
        target = images_dir / f"shot_{shot_id:03d}.png"
        source.replace(target)
        return target

    def _build_asset(
        self,
        shot: VisualShot,
        final: Path,
        render: ComfyUIRender,
        variables: dict[str, Any],
        provider: ComfyUIProvider,
    ) -> ImageAsset:
        checksum, width, height = self._inspect(final)
        requested_width = int(variables["width"])
        requested_height = int(variables["height"])
        metadata = ImageMetadata(
            shot_id=shot.id,
            block=shot.block,
            start_second=shot.start_second,
            end_second=shot.end_second,
            width=requested_width,
            height=requested_height,
            positive_prompt=str(variables["positive_prompt"]),
            negative_prompt=str(variables["negative_prompt"]),
            sampler_settings=ImageSamplerSettings(
                steps=int(variables["steps"]),
                cfg=float(variables["cfg"]),
                sampler=str(variables["sampler"]),
                scheduler=str(variables["scheduler"]),
                seed=int(variables["seed"]),
            ),
            render_priority=_RENDER_PRIORITY,
            workflow=provider.workflow_name,
            comfyui_prompt_id=render.prompt_id,
        )
        return ImageAsset(
            shot_id=shot.id,
            file=str(final),
            width=width,
            height=height,
            checksum=checksum,
            metadata=metadata,
        )

    def _inspect(self, path: Path) -> tuple[str, int, int]:
        """Read the saved file, validate it, and return checksum + dimensions."""
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ImageValidationError(f"cannot read image {path}: {exc}") from exc
        if not data:
            raise ImageValidationError(f"image {path} is empty")
        width, height = png_dimensions(data)
        if width == 0 or height == 0:
            raise ImageValidationError(f"image {path} is not a valid PNG (bad header)")
        checksum = hashlib.sha256(data).hexdigest()
        return checksum, width, height


def build_positive_prompt(shot: VisualShot) -> str:
    """Deterministic positive prompt following prompt 07's token order.

    Order: subject → action/mechanism → environment → composition → lighting →
    camera → focus → style, capped with a fixed channel-qualifier.
    """
    scene = shot.scene
    subject = scene.subject.strip()
    visual = shot.visual.strip()
    parts: list[str] = []
    if subject:
        parts.append(subject)
        if visual and visual != subject:
            parts.append(visual)
    elif visual:
        parts.append(visual)
    else:
        parts.append(shot.learning_goal.strip() or "engineering scene")
    _append_optional(parts, scene.environment)
    _append_optional(parts, scene.composition)
    _append_optional(parts, scene.lighting)
    _append_optional(parts, shot.camera if shot.camera.strip() else scene.camera_motion)
    _append_optional(parts, scene.focus)
    _append_optional(parts, scene.style)
    parts.append("vertical 9:16 engineering illustration")
    return ", ".join(parts)


def _append_optional(parts: list[str], value: Any) -> None:
    text = str(value).strip()
    if text and text.lower() not in {"n/a", "na", "none", "nan"}:
        parts.append(text)
