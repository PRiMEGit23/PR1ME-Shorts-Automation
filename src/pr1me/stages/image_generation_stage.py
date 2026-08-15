"""Image Generation stage (ComfyUI renderer + Image Critic gate).

Renders exactly one accepted image per shot through the local ComfyUI server,
then returns an ordered :class:`ImageManifestOutput` with the Image Critic's
per-render scores and the run-level quality report.

The active path consumes the validated :class:`WorkflowFrame` frames built
by the Workflow Builder stage from the Visual Architecture output; each frame
carries its own prompt, camera metadata, and deterministic sampler settings,
so the stage never composes a prompt itself. The legacy single-prompt path
(:func:`build_positive_prompt` over the visual plan) remains only as a
backward-compatible fallback and is selectable via the
``PR1ME_USE_LEGACY_IMAGE_PROMPTS`` feature flag.

The Image Critic (when enabled) scores every render against the channel's ten
quality dimensions; a render below the gate threshold is regenerated with
*targeted* corrections derived from the failed dimensions, never a blind
retry. The thumbnail shot renders ``image_critic_thumbnail_candidates``
variants, scores each, and keeps the strongest. Rejected renders are archived
under ``images/rejected/`` and reported in the manifest.

The stage owns the deterministic boundary: the fixed sampler policy, the
reproducible seed policy (each regeneration attempt advances the seed by a
fixed step), and post-render validation. All transport lives in
:class:`~pr1me.providers.comfyui.ComfyUIProvider`.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from pr1me.core.base_stage import BaseStage
from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.errors import PipelineError, ProviderNotConfiguredError
from pr1me.image_critic import ImageCritic, ImageCriticInput, ImageCritique, RejectedRender
from pr1me.image_critic.contracts import ImageQualityReport, QualityMetrics
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.image import (
    ImageAsset,
    ImageGenerationInput,
    ImageManifestOutput,
    ImageMetadata,
    ImageSamplerSettings,
)
from pr1me.models.contracts.visual import VisualShot
from pr1me.models.contracts.workflow import WorkflowFrame
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
    """Renders one accepted image per shot via a local ComfyUI server.

    Prefers the validated :class:`WorkflowFrame` frames from the Workflow
    Builder stage; falls back to the legacy visual-plan prompt path only when
    no frames are supplied or ``use_legacy_image_prompts`` is enabled. Every
    render is scored by the Image Critic when enabled; failed renders are
    regenerated with targeted corrections.
    """

    stage_id = "image_generation"
    name = "Image Generation"
    description = "Renders one image per shot via ComfyUI, critiqued and quality-gated."
    version = "2.0.0"
    depends_on = ("workflow_builder",)
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

        use_frames = bool(payload.frames) and not settings.use_legacy_image_prompts
        critic = (
            ImageCritic(threshold=settings.image_critic_threshold)
            if settings.image_critic_enabled
            else None
        )
        self._logger.info(
            "event=image_generation.started",
            n_shots=len(payload.shots),
            n_frames=len(payload.frames),
            path="validated_frames" if use_frames else "legacy_plan",
            critic_enabled=critic is not None,
        )

        assets: list[ImageAsset] = []
        critiques: list[ImageCritique] = []
        rejected: list[RejectedRender] = []
        rejected_dir = images_dir / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        if use_frames:
            for frame in payload.frames:
                self._logger.info(
                    "event=image_generation.shot",
                    shot_id=frame.shot_id,
                    block=frame.block,
                    source="workflow_builder",
                )
                budget = (
                    settings.image_critic_thumbnail_candidates
                    if frame.is_thumbnail and critic is not None
                    else settings.image_critic_max_attempts
                )
                final, variables, critique, render, attempt_critiques, attempt_rejected = (
                    await self._render_with_critic(
                        provider,
                        shot_id=frame.shot_id,
                        base_variables=frame.to_comfyui_variables(),
                        validation_score=frame.validation_score,
                        is_thumbnail=frame.is_thumbnail,
                        budget=budget,
                        critic=critic,
                        settings=settings,
                        images_dir=images_dir,
                        rejected_dir=rejected_dir,
                    )
                )
                critiques.extend(attempt_critiques)
                rejected.extend(attempt_rejected)
                assets.append(
                    self._build_frame_asset(
                        frame,
                        final,
                        render,
                        variables,
                        provider,
                        critique=critique,
                    )
                )
        else:
            width = settings.target_width
            height = settings.target_height
            for index, shot in enumerate(payload.shots):
                self._logger.info(
                    "event=image_generation.shot",
                    shot_id=shot.id,
                    index=index,
                    block=shot.block,
                    source="legacy_plan",
                )
                final, variables, critique, render, attempt_critiques, attempt_rejected = (
                    await self._render_with_critic(
                        provider,
                        shot_id=shot.id,
                        base_variables=self._render_variables(shot, index, width, height),
                        validation_score=None,
                        is_thumbnail=False,
                        budget=settings.image_critic_max_attempts,
                        critic=critic,
                        settings=settings,
                        images_dir=images_dir,
                        rejected_dir=rejected_dir,
                    )
                )
                critiques.extend(attempt_critiques)
                rejected.extend(attempt_rejected)
                assets.append(
                    self._build_asset(shot, final, render, variables, provider, critique=critique)
                )

        expected = len(payload.frames) if use_frames else len(payload.shots)
        if len(assets) != expected:
            raise ImageValidationError(f"expected {expected} images, got {len(assets)}")

        shot_ids = (
            [frame.shot_id for frame in payload.frames]
            if use_frames
            else [shot.id for shot in payload.shots]
        )
        checks = [
            "all_shots_rendered",
            "images_in_shot_order",
            *[f"shot_{shot_id:03d}_valid_png" for shot_id in shot_ids],
        ]
        if critic is not None:
            checks.append("image_critic_gate_applied")
            checks.append("image_critic_gate_passed")
        manifest = ImageManifestOutput(
            output_dir=str(images_dir),
            images=assets,
            total=len(assets),
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=checks,
            ),
            report=self._build_report(
                critiques,
                rejected,
                assets,
                threshold=settings.image_critic_threshold,
            )
            if critic is not None
            else None,
        )
        self._logger.info(
            "event=image_generation.completed",
            n_images=len(assets),
            output_dir=str(images_dir),
            path="validated_frames" if use_frames else "legacy_plan",
            n_rejected=len(rejected),
            n_critiques=len(critiques),
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

    async def _render_with_critic(
        self,
        provider: ComfyUIProvider,
        *,
        shot_id: int,
        base_variables: dict[str, Any],
        validation_score: int | None,
        is_thumbnail: bool,
        budget: int,
        critic: ImageCritic | None,
        settings: Settings,
        images_dir: Path,
        rejected_dir: Path,
    ) -> tuple[
        Path,
        dict[str, Any],
        ImageCritique | None,
        ComfyUIRender,
        list[ImageCritique],
        list[RejectedRender],
    ]:
        """Render one shot with critique-driven regeneration.

        Returns the accepted file, the variables that produced it, its
        critique (None when the critic is disabled), the winning render record,
        every attempt's critique, and the rejected renders (failed attempts
        plus losing thumbnail candidates). Each regeneration attempt applies
        the previous attempt's targeted corrections and advances the seed
        deterministically.
        """
        base_seed = int(base_variables["seed"])
        base_positive = str(base_variables["positive_prompt"])
        staged: list[tuple[Path, dict[str, Any], ImageCritique | None, int, ComfyUIRender]] = []
        corrections: list[str] = []
        for attempt in range(1, max(1, budget) + 1):
            variables = dict(base_variables)
            if attempt > 1 and corrections:
                variables["positive_prompt"] = f"{base_positive}, {', '.join(corrections)}"
            if attempt > 1:
                variables["seed"] = (base_seed + (attempt - 1) * _SEED_STEP) % (2**63 - 1)
            rendered = await provider.render(variables, output_dir=images_dir)
            if not rendered:
                raise ImageValidationError(
                    f"shot {shot_id} rendered no images", detail={"shot_id": shot_id}
                )
            if len(rendered) > 1:
                self._logger.warning(
                    "event=image_generation.multiple_outputs",
                    shot_id=shot_id,
                    n_images=len(rendered),
                    note="keeping the first render",
                )
            staged_path = images_dir / f"shot_{shot_id:03d}_a{attempt:02d}.png"
            os.replace(rendered[0].file, staged_path)
            _checksum, width, height = self._inspect(staged_path)
            attempt_critique: ImageCritique | None = None
            if critic is not None:
                attempt_critique = critic.critique(
                    ImageCriticInput(
                        shot_id=shot_id,
                        positive_prompt=str(variables["positive_prompt"]),
                        negative_prompt=str(variables["negative_prompt"]),
                        is_thumbnail=is_thumbnail,
                        validation_score=validation_score,
                        render_valid_png=True,
                        render_bytes=staged_path.stat().st_size,
                        render_width=width,
                        render_height=height,
                        requested_width=int(variables["width"]),
                        requested_height=int(variables["height"]),
                        attempt=attempt,
                        seed=int(variables["seed"]),
                    )
                )
                corrections = attempt_critique.corrections
                self._logger.info(
                    "event=image_generation.critique",
                    shot_id=shot_id,
                    attempt=attempt,
                    score=attempt_critique.score,
                    passed=attempt_critique.passed,
                    reasons=attempt_critique.reasons,
                )
            staged.append((staged_path, variables, attempt_critique, attempt, rendered[0]))
            if attempt_critique is None or attempt_critique.passed:
                break

        best_path, best_variables, best_critique, best_attempt, _best_render = max(
            staged,
            key=lambda entry: (entry[2].score if entry[2] is not None else 100, -entry[3]),
        )
        final = images_dir / f"shot_{shot_id:03d}.png"
        best_path.replace(final)

        if critic is not None and best_critique is not None and not best_critique.passed:
            self._logger.warning(
                "event=image_generation.gate_failed",
                shot_id=shot_id,
                score=best_critique.score,
                reasons=best_critique.reasons,
                strict=settings.image_critic_strict,
            )
            if settings.image_critic_strict:
                raise ImageValidationError(
                    f"shot {shot_id} failed the image critic quality gate",
                    detail={
                        "score": best_critique.score,
                        "reasons": best_critique.reasons,
                    },
                )

        rejected: list[RejectedRender] = []
        for path, _variables, critique, attempt, _render in staged:
            if path == best_path:
                continue
            if critique is not None and critique.passed:
                reasons = ["thumbnail candidate not selected"]
            else:
                reasons = critique.reasons if critique is not None else ["render not critiqued"]
            target = rejected_dir / f"shot_{shot_id:03d}_attempt{attempt:02d}.png"
            path.replace(target)
            rejected.append(
                RejectedRender(
                    shot_id=shot_id,
                    attempt=attempt,
                    file=str(target),
                    score=critique.score if critique is not None else 0,
                    reasons=reasons,
                )
            )
        return (
            final,
            best_variables,
            best_critique,
            _best_render,
            [critique for _path, _variables, critique, _attempt, _render in staged if critique is not None],
            rejected,
        )

    def _build_report(
        self,
        critiques: list[ImageCritique],
        rejected: list[RejectedRender],
        assets: list[ImageAsset],
        *,
        threshold: int,
    ) -> ImageQualityReport:
        """Assemble the end-of-run image quality report."""
        scores = [critique.score for critique in critiques]
        metrics = QualityMetrics(
            total_attempted=len(critiques),
            total_accepted=len(assets),
            total_rejected=len(rejected),
            regeneration_rate=round(len(rejected) / max(1, len(critiques)), 3),
            average_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
            min_score=min(scores) if scores else 0,
            max_score=max(scores) if scores else 0,
            gates=["prompt_validation>=95", f"image_critic>={threshold}"],
        )
        return ImageQualityReport(
            critic_scores=critiques,
            rejected_renders=rejected,
            accepted_shot_ids=[asset.shot_id for asset in assets],
            metrics=metrics,
        )

    def _finalize_path(self, rendered: ComfyUIRender, images_dir: Path, shot_id: int) -> Path:
        source = Path(rendered.file)
        target = images_dir / f"shot_{shot_id:03d}.png"
        source.replace(target)
        return target

    def _build_frame_asset(
        self,
        frame: WorkflowFrame,
        final: Path,
        render: ComfyUIRender,
        variables: dict[str, Any],
        provider: ComfyUIProvider,
        critique: ImageCritique | None = None,
    ) -> ImageAsset:
        checksum, width, height = self._inspect(final)
        metadata = ImageMetadata(
            shot_id=frame.shot_id,
            block=frame.block,
            start_second=frame.start_second,
            end_second=frame.end_second,
            width=int(variables["width"]),
            height=int(variables["height"]),
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
            shot_id=frame.shot_id,
            file=str(final),
            width=width,
            height=height,
            checksum=checksum,
            metadata=metadata,
            critique=critique,
        )

    def _build_asset(
        self,
        shot: VisualShot,
        final: Path,
        render: ComfyUIRender,
        variables: dict[str, Any],
        provider: ComfyUIProvider,
        critique: ImageCritique | None = None,
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
            critique=critique,
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
