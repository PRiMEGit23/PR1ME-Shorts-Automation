"""SDXL-family adapter (SDXL, Juggernaut XL, RealVis XL).

The reference adapter: its output is the legacy Phase-6 workflow shape
plus the backend annotations. The sampler / cfg / resolution / loras /
negative tokens are the render profile's own values (single source), so
the legacy path and the director path agree for SDXL-family models.
"""

from __future__ import annotations

from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.model_director.model_profiles import SceneModelPlan
from knowledge.render_optimizer.render_profiles import RenderProfile

from runtime.backends.base import BackendAdapter, BackendWorkflow


class SDXLAdapter(BackendAdapter):
    """SDXL family: the canonical reference adapter."""

    backend = "sdxl"

    def adapt(
        self,
        prompt: CompiledPrompt,
        profile: RenderProfile,
        plan: SceneModelPlan,
    ) -> BackendWorkflow:
        params = plan.model_profile
        return BackendWorkflow(
            backend=self.backend,
            profile=params.render_profile.value,
            sampler=params.sampler,
            scheduler=params.scheduler,
            steps=params.steps,
            cfg=params.cfg,
            resolution=params.resolution,
            aspect_ratio=params.aspect_ratio,
            vae=params.vae,
            loras=params.loras or tuple(profile.loras),
            negative_tokens=params.negative_tokens or tuple(profile.negative_tokens),
            positive_prompt=prompt.prompt,
            negative_prompt=prompt.negative_prompt or "",
            controlnet=params.controlnet,
            ip_adapter=params.ip_adapter,
            depth_strategy=params.depth_strategy,
            segmentation_strategy=params.segmentation_strategy,
            upscaler=params.upscaler,
            refiner=params.refiner,
            animation_backend=params.animation_backend,
            quality_target=params.quality_target,
            nodes=dict(profile.node_notes),
        )
