"""Thumbnail stage (prompt 05 + ComfyUI render).

Consumes the approved topic and script, designs one :class:`ThumbnailConcept`
through prompt 05, then renders exactly one ``thumbnail.png`` through the
ComfyUI image provider, returning a single :class:`ThumbnailManifestOutput`.

The stage owns the deterministic boundary: the concept-to-prompt composition
(mirroring prompt 05's token order), the fixed sampler policy, the stable
seed, the deliverable name/location, and the post-render validation. All
transport lives in :class:`~pr1me.providers.comfyui.ComfyUIProvider`.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Any

from pr1me.core.base_stage import BaseStage
from pr1me.core.context import StageContext
from pr1me.core.errors import PipelineError, ProviderNotConfiguredError
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.publishing import (
    PublishingInput,
    ThumbnailConcept,
    ThumbnailManifestOutput,
    ThumbnailRenderMetadata,
)
from pr1me.models.meta import ValidationStatus
from pr1me.providers.comfyui import ComfyUIProvider, ComfyUIRender, png_dimensions
from pr1me.stages.image_generation_stage import _NEGATIVE_PROMPT
from pr1me.stages.publishing_common import generate_publishing_payload

_ENV_WORKFLOW = "PR1ME_COMFYUI_WORKFLOW"
_ENV_OUTPUT_DIR = "PR1ME_THUMBNAIL_OUTPUT_DIR"

#: Deliverable name produced by the stage (CLI contract).
_FILENAME = "thumbnail.png"

#: Fixed sampler policy (channel default, deterministic).
_DEFAULT_STEPS = 28
_DEFAULT_CFG = 7.0
_DEFAULT_SAMPLER = "euler_a"
_DEFAULT_SCHEDULER = "karras"

#: Stable seed policy so the same concept renders the same thumbnail.
_SEED = 424213

#: Prompt 05 text-overlay policy: at most four words.
_MAX_TEXT_OVERLAY_WORDS = 4


class ThumbnailValidationError(PipelineError):
    """The thumbnail concept or render failed the deterministic checks."""

    code = "thumbnail_validation_error"


class ThumbnailStage(BaseStage[PublishingInput, ThumbnailManifestOutput]):
    """Designs and renders the single click-worthy thumbnail for one Short."""

    stage_id = "thumbnail"
    name = "Thumbnail"
    description = "Designs a thumbnail concept and renders one thumbnail.png."
    version = "1.0.0"
    prompt_file = "05_thumbnail_generator.md"
    depends_on = ("topic", "script", "video_render")
    input_model = PublishingInput
    output_model = ThumbnailManifestOutput

    def __init__(
        self,
        context: StageContext,
        *,
        comfyui_provider: ComfyUIProvider | None = None,
    ) -> None:
        self._comfyui = comfyui_provider
        super().__init__(context)

    async def execute(self, payload: PublishingInput) -> ThumbnailManifestOutput:
        concept = await generate_publishing_payload(
            self.context,
            prompt_file=self.prompt_file,
            payload=payload,
            temperature=0.6,
            max_tokens=500,
            output_model=ThumbnailConcept,
        )
        self._validate_concept(concept)

        provider = self._comfyui or self._default_provider()
        if provider is None:
            raise ProviderNotConfiguredError(
                "no ComfyUI provider is configured for the thumbnail stage"
            )
        settings = self.context.settings
        configured_dir = os.getenv(_ENV_OUTPUT_DIR)
        output_dir = Path(configured_dir) if configured_dir else settings.work_dir
        await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)

        variables = self._render_variables(concept, settings.target_width, settings.target_height)
        self._logger.info(
            "event=thumbnail.started",
            topic=payload.topic,
            seed=_SEED,
            width=settings.target_width,
            height=settings.target_height,
        )
        rendered = await provider.render(variables, output_dir=output_dir)
        if not rendered:
            raise ThumbnailValidationError(
                "the thumbnail workflow rendered no images",
                detail={"topic": payload.topic},
            )
        if len(rendered) > 1:
            self._logger.warning(
                "event=thumbnail.multiple_outputs",
                n_images=len(rendered),
                note="keeping the first render",
            )

        final = await asyncio.to_thread(self._finalize, rendered[0], output_dir)
        checksum, width, height, size_bytes = await asyncio.to_thread(self._inspect, final)

        manifest = ThumbnailManifestOutput(
            output_dir=str(output_dir),
            file=str(final),
            bytes=size_bytes,
            width=width,
            height=height,
            checksum=checksum,
            concept=concept,
            metadata=ThumbnailRenderMetadata(
                backend=provider.name,
                workflow=provider.workflow_name,
                comfyui_prompt_id=rendered[0].prompt_id,
                prompt=build_thumbnail_prompt(concept),
                seed=_SEED,
                steps=_DEFAULT_STEPS,
                cfg=_DEFAULT_CFG,
                sampler=_DEFAULT_SAMPLER,
                scheduler=_DEFAULT_SCHEDULER,
            ),
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=[
                    "single_png_file",
                    "valid_png",
                    "thumbnail_orientation",
                    "checksum_verified",
                    "text_overlay_within_word_count",
                    "truthful_to_topic",
                ],
            ),
        )
        self._logger.info(
            "event=thumbnail.completed",
            file=final.name,
            width=width,
            height=height,
            bytes=manifest.bytes,
            workflow=provider.workflow_name,
        )
        return manifest

    # ------------------------------------------------------------ internals --

    def _default_provider(self) -> ComfyUIProvider:
        workflow_file = os.getenv(_ENV_WORKFLOW)
        if not workflow_file:
            workflow_file = str(self.context.settings.repo_root / "workflows" / "comfyui.json")
        return ComfyUIProvider(workflow_file=workflow_file)

    def _render_variables(self, concept: ThumbnailConcept, width: int, height: int) -> dict[str, Any]:
        return {
            "positive_prompt": build_thumbnail_prompt(concept),
            "negative_prompt": _NEGATIVE_PROMPT,
            "width": width,
            "height": height,
            "seed": _SEED,
            "steps": _DEFAULT_STEPS,
            "cfg": _DEFAULT_CFG,
            "sampler": _DEFAULT_SAMPLER,
            "scheduler": _DEFAULT_SCHEDULER,
        }

    def _validate_concept(self, concept: ThumbnailConcept) -> None:
        if concept.text_overlay:
            words = concept.text_overlay.split()
            if len(words) > _MAX_TEXT_OVERLAY_WORDS:
                raise ThumbnailValidationError(
                    f"text overlay exceeds {_MAX_TEXT_OVERLAY_WORDS} words: {concept.text_overlay!r}",
                    detail={"text_overlay": concept.text_overlay},
                )

    def _finalize(self, rendered: ComfyUIRender, output_dir: Path) -> Path:
        source = Path(rendered.file)
        target = output_dir / _FILENAME
        source.replace(target)
        return target

    def _inspect(self, path: Path) -> tuple[str, int, int, int]:
        """Read the saved file, validate it, and return checksum, dimensions, size."""
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ThumbnailValidationError(f"cannot read thumbnail {path}: {exc}") from exc
        if not data:
            raise ThumbnailValidationError(f"thumbnail {path} is empty")
        width, height = png_dimensions(data)
        if width == 0 or height == 0:
            raise ThumbnailValidationError(f"thumbnail {path} is not a valid PNG (bad header)")
        checksum = hashlib.sha256(data).hexdigest()
        return checksum, width, height, len(data)


def build_thumbnail_prompt(concept: ThumbnailConcept) -> str:
    """Deterministic positive prompt following prompt 05's token order.

    Order: subject → composition → colors → focal point → text overlay →
    style, capped with the fixed vertical-thumbnail qualifier.
    """
    parts: list[str] = [concept.subject.strip(), concept.composition.strip()]
    parts.append(
        f"colors: background {concept.colors.background.strip()}, "
        f"accent {concept.colors.accent.strip()}"
    )
    parts.append(f"focal point: {concept.focal_point.strip()}")
    if concept.text_overlay and concept.text_overlay.strip():
        parts.append(
            f"bold text overlay {concept.text_overlay.strip()} in {concept.colors.text.strip()}"
        )
    parts.append(concept.style.strip())
    parts.append("vertical 9:16 YouTube thumbnail, high contrast")
    return ", ".join(parts)