"""WAN 2.2 adapter: the motion-first video model."""

from __future__ import annotations

from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.model_director.model_profiles import SceneModelPlan
from knowledge.render_optimizer.render_profiles import RenderProfile

from runtime.backends.base import BackendAdapter, BackendWorkflow


class WANAdapter(BackendAdapter):
    """WAN 2.2: flow-matching video generation."""

    backend = "wan"

    def adapt(
        self,
        prompt: CompiledPrompt,
        profile: RenderProfile,
        plan: SceneModelPlan,
    ) -> BackendWorkflow:
        params = plan.model_profile
        nodes = dict(profile.node_notes)
        nodes["video"] = "wan 2.2"
        nodes["frames"] = "48"
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
            loras=params.loras,
            negative_tokens=params.negative_tokens,
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
            nodes=nodes,
        )
