"""Generic adapter: any registry model without a dedicated adapter.

Future models join through the registry (``ModelRegistry.register``);
until they earn a dedicated adapter they are compiled through this
generic adapter, which mirrors the canonical workflow shape from the
plan's compiled profile. Deterministic and backend-agnostic by
construction.
"""

from __future__ import annotations

from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.model_director.model_profiles import SceneModelPlan
from knowledge.render_optimizer.render_profiles import RenderProfile

from runtime.backends.base import BackendAdapter, BackendWorkflow


class GenericAdapter(BackendAdapter):
    """Compile any model from its plan alone (HiDream and future models)."""

    backend = "generic"

    def adapt(
        self,
        prompt: CompiledPrompt,
        profile: RenderProfile,
        plan: SceneModelPlan,
    ) -> BackendWorkflow:
        params = plan.model_profile
        nodes = dict(profile.node_notes)
        nodes["backend"] = params.image_model
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
