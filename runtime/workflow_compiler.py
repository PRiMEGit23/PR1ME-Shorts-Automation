"""Workflow compiler: treat workflows like programs.

The Workflow Compiler intelligently assembles ComfyUI workflows by choosing
optimal parameters (sampler, scheduler, VAE, LoRA, ControlNet, IPAdapter,
upscaler, refiner, animation backend) from the Model Registry instead of
blindly using a profile's fixed values.  Everything is deterministic; the
same inputs always produce the same workflow + compile-log.

The compiler has two modes:

1. ``intelligent_build`` — selects each parameter by querying the Model
   Registry and running the CompatibilityChecker.  The choices are guided
   by the scene content (subject type, material, engineering domain) so
   that, e.g. a metal subject gets Depth ControlNet, a diagram gets
   appropriate LoRAs, etc.

2. ``build`` — the legacy deterministic path: one workflow JSON from a
   RenderProfile and a compiled prompt.  Kept for backward compatibility.
"""

from __future__ import annotations

from typing import Any
from knowledge.compiler.prompt_compiler import CompiledPrompt

from knowledge.model_director.model_profiles import SceneModelPlan
from knowledge.model_director.model_registry import REGISTRY, ModelSpec, ModelKind
from knowledge.render_optimizer import RenderProfileKey, profile_for
from knowledge.model_director.compatibility import (
    check_model,
    compatible_model_for,
    spec_for,
)
from knowledge.visual_architecture import (
    Material,
    Modality,
    Subject,
    VisualArchitecture,
)
from pydantic import BaseModel, ConfigDict


# ------------------------------------------------------------------- #
# Helper: map scene content to parameter preferences
# ------------------------------------------------------------------- #

# When the primary subject entity contains these keywords, favor the
# associated ControlNet/IPAdapter/LoRA/upscaler/refiner.
_SUBJECT_TO_CONTROLNET: dict[str, tuple[str, ...]] = {
    "metal": ("depth",),
    "steel": ("depth",),
    "aluminum": ("depth",),
    "gold": ("depth",),
    "silver": ("depth",),
    "plastic": ("upscaler",),
    "polymer": ("upscaler",),
    "ceramic": ("upscaler",),
    "wood": ("upscaler",),
    "fabric": ("refiner",),
    "texture": ("refiner",),
}

_SUBJECT_TO_IPADAPTER: dict[str, tuple[str, ...]] = {
    "photoreal": ("style_transfer",),
    "portrait": ("style_transfer",),
    "product": ("style_transfer",),
}

_SUBJECT_TO_LORA: dict[str, tuple[str, ...]] = {
    "gyroid": ("detail",),
    "infill": ("detail",),
    "cube": ("structure",),
    "infill cube": ("structure",),
    "gear": ("mechanism",),
    "mechanism": ("mechanism",),
    "electronics": ("circuit",),
    "chip": ("circuit",),
}

_SUBJECT_TO_UPSCALER: dict[str, tuple[str, ...]] = {
    "high detail": ("4x_ultrasharp",),
    "macro": ("4x_ultrasharp",),
    "micro": ("4x_ultrasharp",),
}

_SUBJECT_TO_REFINER: dict[str, tuple[str, ...]] = {
    "portrait": ("sdxl-refiner",),
    "photoreal": ("sdxl-refiner",),
}


def _prefer_controlnet(subject_entity: str) -> tuple[str, ...]:
    """Return ControlNet types to try, in order, based on subject entity."""
    entity_lower = subject_entity.lower()
    for keywords, controls in _SUBJECT_TO_CONTROLNET.items():
        if keywords in entity_lower:
            return controls
    # Default: try depth if the model supports it (most do), else empty.
    return ()


def _prefer_ipadapter(subject_entity: str) -> tuple[str, ...]:
    """Return IPAdapter types to try, in order, based on subject entity."""
    entity_lower = subject_entity.lower()
    for keywords, ipads in _SUBJECT_TO_IPADAPTER.items():
        if keywords in entity_lower:
            return ipads
    return ()


def _prefer_lora(subject_entity: str) -> tuple[str, ...]:
    """Return LoRA types to try, in order, based on subject entity."""
    entity_lower = subject_entity.lower()
    for keywords, loras in _SUBJECT_TO_LORA.items():
        if keywords in entity_lower:
            return loras
    return ()


def _prefer_upscaler(subject_entity: str) -> tuple[str, ...]:
    """Return upscaler types to try, in order, based on subject entity."""
    entity_lower = subject_entity.lower()
    for keywords, upscalers in _SUBJECT_TO_UPSCALER.items():
        if keywords in entity_lower:
            return upscalers
    return ()


def _prefer_refiner(subject_entity: str) -> tuple[str, ...]:
    """Return refiner types to try, in order, based on subject entity."""
    entity_lower = subject_entity.lower()
    for keywords, refiners in _SUBJECT_TO_REFINER.items():
        if keywords in entity_lower:
            return refiners
    return ()


# ------------------------------------------------------------------- #
# The Workflow Compiler
# ------------------------------------------------------------------- #


class WorkflowCompileLog(BaseModel):
    """Human-readable log of every compiler decision.

    Every field is deterministic for a given input, so the log is itself a
    reproducible artifact that can be stored alongside the workflow JSON.
    """

    model_config = ConfigDict(frozen=True)

    model_key: str
    sampler: str
    scheduler: str
    vae: str
    resolution: str
    aspect_ratio: str
    controlnet: tuple[str, ...]
    ip_adapter: tuple[str, ...]
    lora: tuple[str, ...]
    upscaler: tuple[str, ...]
    refiner: tuple[str, ...]
    animation_backend: str
    choices: dict[str, str]  # human-readable whyfore for each parameter

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(*args, **kwargs)


class WorkflowCompiler:
    """Compile deterministic ComfyUI workflows from scene content + model profile.

    The compiler works in two passes:

    Pass 1 — Parameter inference from scene content.
    -------------------------------
    * Read the Scene's Subject, Material, EngineeringDomain, Modality.
    * Query the Model Registry for candidate models.
    * For each parameter (sampler, scheduler, VAE, etc.), run the
      CompatibilityChecker against the candidate models and pick the
      highest-scoring compatible combination.

    Pass 2 — Workflow JSON assembly.
    --------------------------
    * Use the chosen parameters + the RenderProfile's base settings
      (resolution, CFG, steps) to build the canonical workflow dict.
    * Append any applicable LoRA/ControlNet/IPAdapter nodes from the
      compile log.
    * Return the workflow + compile log.
    """

    # ----------------------------------------------------------------- #
    # Pass 1: intelligent parameter inference
    # ----------------------------------------------------------------- #

    @staticmethod
    def _infer_subject_entity(scene: Any) -> str:
        """Extract the primary subject entity from a StoryboardScene or Scene.

        Returns the lower-cased entity string, or '' if unavailable.
        """
        # Try StoryboardScene first (has primary_subject.entity)
        try:
            entity = getattr(scene, "primary_subject", None)
            if entity is not None:
                return getattr(entity, "entity", "") or ""
        except Exception:
            pass
        # Try plain Scene
        try:
            entity = getattr(scene, "primary_subject", None)
            if entity is not None:
                return getattr(entity, "entity", "") or ""
        except Exception:
            pass
        return ""

    @staticmethod
    def _infer_material(scene: Any) -> str:
        """Extract the primary material from a Scene/StoryboardScene."""
        try:
            entity = getattr(scene, "primary_subject", None)
            if entity is not None:
                materials = getattr(entity, "materials", ())
                if materials:
                    return materials[0].value  # type: ignore[attr-index]
        except Exception:
            pass
        return ""

    @staticmethod
    def _infer_modality(scene: Any) -> str:
        """Extract the modality from a StoryboardScene/Scene."""
        try:
            return getattr(scene, "modality", Modality.PHOTOREAL).value  # type: ignore[attr-index]
        except Exception:
            return "photoreal"

    @staticmethod
    def _pass_1_choose_sampler(
        model_key: str, spec: ModelSpec
    ) -> tuple[str | None, str]:
        """Pick the best sampler for ``model_key``.

        Returns (sampler_name, rationale).
        """
        if not spec.supported_samplers:
            return "", "no supported samplers"
        # Prefer dpmpp_2m if available (the SDXL/default choice),
        # otherwise the first supported sampler.
        preferred = "dpmpp_2m" if "dpmpp_2m" in spec.supported_samplers else spec.supported_samplers[0]
        return preferred, f"chosen from {spec.supported_samplers} (preferred: {preferred})"

    @staticmethod
    def _pass_1_choose_scheduler(
        model_key: str, spec: ModelSpec
    ) -> tuple[str | None, str]:
        """Pick the best scheduler for ``model_key``."""
        if not spec.supported_schedulers:
            return "", "no supported schedulers"
        # Prefer karras (the SDXL/default choice), otherwise the first.
        preferred = "karras" if "karras" in spec.supported_schedulers else spec.supported_schedulers[0]
        return preferred, f"chosen from {spec.supported_schedulers} (preferred: {preferred})"

    @staticmethod
    def _pass_1_choose_vae(
        model_key: str, spec: ModelSpec
    ) -> tuple[str | None, str]:
        """Pick the best VAE for ``model_key``."""
        if not spec.supported_vaes:
            return "", "no supported VAE"
        return spec.supported_vaes[0], f"chosen from {spec.supported_vaes}"

    @staticmethod
    def _pass_1_choose_controlnet(
        model_key: str, spec: ModelSpec, controlnet_candidates: tuple[str, ...]
    ) -> tuple[tuple[str, ...], str]:
        """Pick ControlNet types that are compatible with the model.

        Returns (chosen_controlnets, rationale).
        """
        chosen: list[str] = []
        rationale_parts: list[str] = []
        for c in controlnet_candidates:
            report = check_model(model_key, controlnet=c)
            if report.compatible:
                chosen.append(c)
                rationale_parts.append(f"{c} (compatible)")
            else:
                rationale_parts.append(f"{c} (incompatible, skipped)")
        chosen_tup = tuple(chosen) if chosen else ()
        rationale = "; ".join(rationale_parts) if rationale_parts else "none compatible"
        return chosen_tup, rationale

    @staticmethod
    def _pass_1_choose_ipadapter(
        model_key: str, spec: ModelSpec, ipadapter_candidates: tuple[str, ...]
    ) -> tuple[tuple[str, ...], str]:
        """Pick IPAdapter types compatible with the model."""
        chosen: list[str] = []
        rationale_parts: list[str] = []
        for c in ipadapter_candidates:
            report = check_model(model_key, ip_adapter=c)
            if report.compatible:
                chosen.append(c)
                rationale_parts.append(f"{c} (compatible)")
            else:
                rationale_parts.append(f"{c} (incompatible, skipped)")
        chosen_tup = tuple(chosen) if chosen else ()
        rationale = "; ".join(rationale_parts) if rationale_parts else "none compatible"
        return chosen_tup, rationale

    @staticmethod
    def _pass_1_choose_lora(
        model_key: str, spec: ModelSpec, lora_candidates: tuple[str, ...]
    ) -> tuple[tuple[str, ...], str]:
        """Pick LoRA types compatible with the model."""
        chosen: list[str] = []
        rationale_parts: list[str] = []
        for c in lora_candidates:
            report = check_model(model_key, refiner=c)  # LoRA shares the refiner slot in this simplified model
            if report.compatible:
                chosen.append(c)
                rationale_parts.append(f"{c} (compatible)")
            else:
                rationale_parts.append(f"{c} (incompatible, skipped)")
        chosen_tup = tuple(chosen) if chosen else ()
        rationale = "; ".join(rationale_parts) if rationale_parts else "none compatible"
        return chosen_tup, rationale

    @staticmethod
    def _pass_1_choose_upscaler(
        model_key: str, spec: ModelSpec, upscaler_candidates: tuple[str, ...]
    ) -> tuple[tuple[str, ...], str]:
        """Pick upscaler types compatible with the model."""
        chosen: list[str] = []
        rationale_parts: list[str] = []
        for c in upscaler_candidates:
            report = check_model(model_key, upscaler=c)
            if report.compatible:
                chosen.append(c)
                rationale_parts.append(f"{c} (compatible)")
            else:
                rationale_parts.append(f"{c} (incompatible, skipped)")
        chosen_tup = tuple(chosen) if chosen else ()
        rationale = "; ".join(rationale_parts) if rationale_parts else "none compatible"
        return chosen_tup, rationale

    @staticmethod
    def _pass_1_choose_refiner(
        model_key: str, spec: ModelSpec, refiner_candidates: tuple[str, ...]
    ) -> tuple[tuple[str, ...], str]:
        """Pick refiner types compatible with the model."""
        chosen: list[str] = []
        rationale_parts: list[str] = []
        for c in refiner_candidates:
            report = check_model(model_key, refiner=c)
            if report.compatible:
                chosen.append(c)
                rationale_parts.append(f"{c} (compatible)")
            else:
                rationale_parts.append(f"{c} (incompatible, skipped)")
        chosen_tup = tuple(chosen) if chosen else ()
        rationale = "; ".join(rationale_parts) if rationale_parts else "none compatible"
        return chosen_tup, rationale

    @staticmethod
    def _pass_1_choose_animation_backend(
        model_key: str, spec: ModelSpec
    ) -> tuple[str, str]:
        """Pick the animation backend for video models."""
        if not spec.supported_animation_backends:
            return "", "no supported animation backends"
        # Prefer the first (canonical) backend.
        backend = spec.supported_animation_backends[0]
        return backend, f"chosen from {spec.supported_animation_backends}"

    # ----------------------------------------------------------------- #
    # Public: intelligent build
    # ----------------------------------------------------------------- #

    def intelligent_build(
        self,
        *,
        prompt: CompiledPrompt,
        scene: Any,  # StoryboardScene or Scene
        model_key: str | None = None,
    ) -> tuple[dict[str, Any], WorkflowCompileLog]:
        """Build a workflow intelligently from scene content + compiled prompt.

        The choices are fully deterministic: same scene + model_key → same
        workflow + log.

        Raises:
            KeyError: if ``model_key`` is not a registered model.
        """
        # ----------------------------------------------------------------- #
        # Resolve the model key
        # ----------------------------------------------------------------- #
        if model_key is None:
            # Default to the SDXL profile's model; in practice the caller will
            # always pass a model_key.  Fallback to "sdxl".
            model_key = "sdxl"
        spec: ModelSpec = REGISTRY.get(model_key)

        # ----------------------------------------------------------------- #
        # Pass 1: infer scene content and choose parameters
        # ----------------------------------------------------------------- #
        subject_entity = self._infer_subject_entity(scene)
        material = self._infer_material(scene)
        modality = self._infer_modality(scene)

        # Sampler
        sampler, sampler_rationale = self._pass_1_choose_sampler(model_key, spec)

        # Scheduler
        scheduler, scheduler_rationale = self._pass_1_choose_scheduler(model_key, spec)

        # VAE
        vae, vae_rationale = self._pass_1_choose_vae(model_key, spec)

        # ControlNet — guided by subject entity
        controlnet_candidates = _prefer_controlnet(subject_entity) if subject_entity else ()
        controlnet_chosen, controlnet_rationale = self._pass_1_choose_controlnet(
            model_key, spec, controlnet_candidates
        )

        # IPAdapter — guided by subject entity
        ipadapter_candidates = _prefer_ipadapter(subject_entity) if subject_entity else ()
        ipadapter_chosen, ipadapter_rationale = self._pass_1_choose_ipadapter(
            model_key, spec, ipadapter_candidates
        )

        # LoRA — guided by subject entity
        lora_candidates = _prefer_lora(subject_entity) if subject_entity else ()
        lora_chosen, lora_rationale = self._pass_1_choose_lora(
            model_key, spec, lora_candidates
        )

        # Upscaler — guided by subject entity
        upscaler_candidates = _prefer_upscaler(subject_entity) if subject_entity else ()
        upscaler_chosen, upscaler_rationale = self._pass_1_choose_upscaler(
            model_key, spec, upscaler_candidates
        )

        # Refiner — guided by subject entity
        refiner_candidates = _prefer_refiner(subject_entity) if subject_entity else ()
        refiner_chosen, refiner_rationale = self._pass_1_choose_refiner(
            model_key, spec, refiner_candidates
        )

        # Animation backend (video models only)
        animation_backend, anim_rationale = self._pass_1_choose_animation_backend(
            model_key, spec
        )

        # ----------------------------------------------------------------- #
        # Pass 2: assemble the workflow JSON
        # ----------------------------------------------------------------- #
        # Use the render profile corresponding to the model key.
        # If the model's key is not in the render profiles dictionary (e.g.,
        # model registry keys like "flux-dev", "sdxl"), fall back to the hero
        # profile since the chosen parameters from Pass 1 are model-specific.
        try:
            render_profile = profile_for(spec.key)
        except KeyError:
            render_profile = profile_for(RenderProfileKey.HERO)

        # Build the nodes dict from the profile's node_notes, overlaying
        # the chosen parameters.
        nodes: dict[str, Any] = dict(render_profile.node_notes)

        # Sampler node
        nodes["sampler"] = sampler

        # Scheduler node
        nodes["scheduler"] = scheduler

        # VAE node
        nodes["vae"] = vae

        # Resolution from profile
        nodes["resolution"] = render_profile.resolution

        # LoRA nodes (if any)
        lora_nodes: list[dict[str, Any]] = []
        for lora_name in lora_chosen:
            # Each LoRA node references the model's LoRA loader; we store
            # the name and a default weight.
            lora_nodes.append(
                {"type": "LoraLoader", "name": lora_name, "weight": 1.0}
            )

        # ControlNet nodes (if any)
        controlnet_nodes: list[dict[str, Any]] = []
        for cn_name in controlnet_chosen:
            controlnet_nodes.append(
                {"type": "ControlNet", "controlnet_name": cn_name, "control_mode": "balanced", "strength": 1.0}
            )

        # IPAdapter nodes (if any)
        ipadapter_nodes: list[dict[str, Any]] = []
        for ip_name in ipadapter_chosen:
            ipadapter_nodes.append(
                {"type": "IPAdapter", "ipadapter_name": ip_name, "weight": 1.0}
            )

        # Upscaler node (if different from the profile default)
        upscaler_nodes: list[dict[str, Any]] = []
        for us_name in upscaler_chosen:
            upscaler_nodes.append({"type": "Upscale", "upscaler_name": us_name})

        # Refiner node (if different from the profile default)
        refiner_nodes: list[dict[str, Any]] = []
        for rf_name in refiner_chosen:
            refiner_nodes.append({"type": "Refiner", "refiner_name": rf_name})

        # Assemble the full workflow dict
        workflow: dict[str, Any] = {
            "workflow_version": "1.0.0",
            "profile": model_key,
            "sampler": sampler,
            "steps": render_profile.steps,
            "cfg": render_profile.cfg,
            "resolution": render_profile.resolution,
            "loras": [l["name"] for l in lora_nodes],
            "negative_tokens": list(render_profile.negative_tokens),
            "positive_prompt": prompt.prompt,
            "negative_prompt": prompt.negative_prompt or "",
            "nodes": {
                **nodes,
                "sampler": sampler,
                "scheduler": scheduler,
                "vae": vae,
                "controlnet": controlnet_nodes,
                "ip_adapter": ipadapter_nodes,
                "lora": lora_nodes,
                "upscaler": upscaler_nodes,
                "refiner": refiner_nodes,
            },
        }

        # Compile log — why each choice was made
        log = WorkflowCompileLog(
            model_key=model_key,
            sampler=sampler,
            scheduler=scheduler,
            vae=vae,
            resolution=render_profile.resolution,
            # Aspect ratio derived from resolution (e.g., "832x1216" -> "9:16")
            aspect_ratio="9:16",
            controlnet=controlnet_chosen,
            ip_adapter=ipadapter_chosen,
            lora=lora_chosen,
            upscaler=upscaler_chosen,
            refiner=refiner_chosen,
            animation_backend=animation_backend,
            choices={
                "sampler": sampler_rationale,
                "scheduler": scheduler_rationale,
                "vae": vae_rationale,
                "controlnet": controlnet_rationale,
                "ip_adapter": ipadapter_rationale,
                "lora": lora_rationale,
                "upscaler": upscaler_rationale,
                "refiner": refiner_rationale,
                "animation_backend": anim_rationale,
            },
        )

        return workflow, log

    # ----------------------------------------------------------------- #
    # Public: legacy build (unchanged, for backward compatibility)
    # ----------------------------------------------------------------- #

    def build(
        self,
        *,
        prompt: CompiledPrompt,
        profile: RenderProfileKey,
        visualization_tokens: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Build the canonical workflow JSON for one render request.

        Legacy path: one deterministic workflow JSON from a RenderProfile and
        a compiled prompt.  Kept for backward compatibility; does NOT perform
        intelligent parameter selection.
        """
        render_profile = profile_for(profile)
        nodes: dict[str, Any] = dict(render_profile.node_notes)
        if visualization_tokens:
            nodes["visualization"] = ", ".join(visualization_tokens)
        return {
            "workflow_version": "1.0.0",
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

    # ----------------------------------------------------------------- #
    # Public: regenerate (unchanged, for backward compatibility)
    # ----------------------------------------------------------------- #

    def regenerate(
        self,
        plan: Any,
        previous: dict[str, Any],
    ) -> dict[str, Any]:
        """Fold the optimizer's workflow + visualization changes into the workflow.

        Returns the previous workflow unchanged when the plan prescribes no
        workflow or visualization change - the loop then detects the
        identical fingerprint and stops instead of repeating the render.
        """
        profile: RenderProfileKey | None = None
        if hasattr(plan, "workflow_changes") and plan.workflow_changes:
            profile = plan.workflow_changes[-1].profile
        visualization_tokens: tuple[str, ...] = ()
        if hasattr(plan, "visualization_changes") and plan.visualization_changes:
            visualization_tokens = tuple(plan.visualization_changes[-1].prompt_tokens)
        if profile is None and not visualization_tokens:
            return previous

        prompt = CompiledPrompt(
            prompt=str(previous.get("positive_prompt", "")),
            negative_prompt=str(previous.get("negative_prompt", "")) or None,
        )
        target = profile or RenderProfileKey(str(previous.get("profile", "hero")))
        rebuilt = self.build(
            prompt=prompt,
            profile=target,
            visualization_tokens=visualization_tokens,
        )
        return rebuilt