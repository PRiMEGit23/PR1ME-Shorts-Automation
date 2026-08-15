"""Workflow builder: turn a render profile and prompt into workflow JSON.

The pipeline envisioned a "Workflow Builder" between the Prompt Compiler and
ComfyUI; Phase 6 provides it as runtime orchestration. It has two jobs:

1. ``build`` - one deterministic workflow JSON from a RenderProfile and a
   compiled prompt (the ComfyUI-readable configuration: sampler, steps, CFG,
   resolution, LoRAs, node notes, and the exact prompt text).

2. ``regenerate`` - after QA rejects an image, fold the Render Optimizer's
   plan into the previous workflow: switch the profile (from
   plan.workflow_changes) and the visualization tokens (from
   plan.visualization_changes). If the plan prescribes nothing, the previous
   workflow is returned unchanged, so the fingerprint stays identical and
   the loop refuses to re-render.

The builder now uses the :class:`WorkflowCompiler` for intelligent parameter
selection (``intelligent_build``) while retaining the legacy ``build`` path
for backward compatibility.

Everything is data-only and deterministic; nothing connects to ComfyUI.
"""

from __future__ import annotations

from typing import Any

from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.model_director.model_profiles import SceneModelPlan
from knowledge.render_optimizer import (
    OptimizedRenderPlan,
    RenderProfileKey,
    profile_for,
)
from runtime.workflow_compiler import WorkflowCompiler
from knowledge.visual_intelligence.camera_language import (
    get_camera_language,
    apply_inertia,
    default_parallax_setup,
    get_foreground_animation,
    get_env_animation,
    compute_tracking,
    ContinuityContext,
)

from runtime.backends import adapt_backend
from runtime.models import WORKFLOW_VERSION


class WorkflowBuilder:
    """Deterministic workflow JSON construction and regeneration.

    Two compilation paths:

    1. ``build`` - the legacy Phase-6 path: one deterministic workflow JSON
       from a RenderProfile and a compiled prompt.
    2. ``intelligent_build`` - the Phase-11 path: workflow compiled from the
       scene content using the :class:`WorkflowCompiler`, which automatically
       chooses ControlNet, IPAdapter, LoRA, upscaler, refiner, sampler,
       scheduler and other parameters from the Model Registry.

    .. note:: ``intelligent_build`` is the recommended path for production
       quality output; ``build`` is retained for backward compatibility.
    """

    def __init__(self) -> None:
        self._compiler = WorkflowCompiler()

    def build(
        self,
        *,
        prompt: CompiledPrompt,
        profile: RenderProfileKey,
        visualization_tokens: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Build the canonical workflow JSON for one render request.

        Legacy path: one deterministic workflow JSON from a RenderProfile and
        a compiled prompt.  Kept for backward compatibility.
        """
        render_profile = profile_for(profile)
        nodes: dict[str, Any] = dict(render_profile.node_notes)
        if visualization_tokens:
            nodes["visualization"] = ", ".join(visualization_tokens)
        return {
            "workflow_version": WORKFLOW_VERSION,
            "profile": profile.value,
            "sampler": render_profile.sampler,
            "steps": render_profile.steps,
            "cfg": render_profile.cfg,
            "resolution": render_profile.resolution,
            "loras": list(render_profile.loras),
            "negative_tokens": list(render_profile.negative_tokens),
            "positive_prompt": prompt.prompt,
            "negative_prompt": prompt.negative_prompt or "",
            "nodes": nodes,
        }

    def intelligent_build(
        self,
        *,
        prompt: CompiledPrompt,
        scene: Any,  # StoryboardScene or Scene
        model_key: str | None = None,
    ) -> tuple[dict[str, Any], Any]:
        """Build a workflow intelligently from scene content + compiled prompt.

        Returns ``(workflow_dict, compile_log)`` where ``compile_log`` is a
        :class:`~runtime.workflow_compiler.WorkflowCompileLog` explaining every
        parameter choice.  The choices are fully deterministic: same scene +
        model_key → same workflow + log.

        Raises:
            KeyError: if ``model_key`` is not a registered model.
        """
        return self._compiler.intelligent_build(
            prompt=prompt, scene=scene, model_key=model_key
        )

    def regenerate(
        self,
        plan: OptimizedRenderPlan,
        previous: dict[str, Any],
    ) -> dict[str, Any]:
        """Fold the optimizer's workflow + visualization changes into the workflow.

        Returns the previous workflow unchanged when the plan prescribes no
        workflow or visualization change - the loop then detects the
        identical fingerprint and stops instead of repeating the render.
        """
        return self._compiler.regenerate(plan, previous)

    def build_from_directive(
        self,
        *,
        prompt: CompiledPrompt,
        plan: Any,  # SceneModelPlan or directive with workflow_profile
    ) -> dict[str, Any]:
        """Build a workflow from a directive (SceneModelPlan).

        Always uses the intelligent build path (Model Registry) to produce
        a complete workflow with all canonical keys (ControlNet, IPAdapter,
        LoRA, scheduler, sampler, etc.). The legacy ``build`` path is retained
        for backward compatibility via the ``build`` method directly.

        Returns a canonical workflow dict ready for the renderer.
        """
        # Extract model_key from the plan's model_profile image_model
        model_key = None
        if hasattr(plan, "model_profile") and plan.model_profile:
            model_key = getattr(plan.model_profile, "image_model", None)
        if not model_key and hasattr(plan, "workflow_profile"):
            # Fall back to workflow_profile string
            model_key = plan.workflow_profile

        # Extract scene from plan if available
        # SceneModelPlan has shot_type, is_hero, etc. that guide parameter selection
        scene = None
        if hasattr(plan, "scene_id"):
            scene = plan.scene_id
        elif hasattr(plan, "scene_index"):
            scene = plan.scene_index
        elif hasattr(plan, "shot_type"):
            # Use shot_type to create a minimal scene-like object
            from knowledge.visual_intelligence.storyboard import ShotType
            try:
                shot_type = ShotType[plan.shot_type.value.replace(' ', '_').upper()] if hasattr(plan.shot_type, 'value') else ShotType.HERO
                scene = {"shot_type": shot_type, "is_hero": getattr(plan, "is_hero", False)}
            except Exception:
                scene = None

        # Always use intelligent build for complete workflow generation
        workflow, _ = self.intelligent_build(
            prompt=prompt,
            scene=scene,
            model_key=model_key,
        )
        return workflow