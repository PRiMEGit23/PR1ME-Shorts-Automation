"""Backend adapters: the only place model-specific workflow code lives.

Dispatch maps each model family to its adapter (the eight named mission
adapters plus the generic adapter for HiDream and future registry
models). ``adapt_backend`` is the single entry point the Workflow Builder
uses; no other runtime module may carry backend-specific strings.
"""

from __future__ import annotations

from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.model_director.model_profiles import SceneModelPlan
from knowledge.model_director.model_registry import REGISTRY
from knowledge.render_optimizer.render_profiles import RenderProfile, profile_for

from runtime.backends.animatediff import AnimateDiffAdapter
from runtime.backends.base import BackendAdapter, BackendWorkflow
from runtime.backends.cogvideo import CogVideoAdapter
from runtime.backends.flux import FluxAdapter
from runtime.backends.generic import GenericAdapter
from runtime.backends.gpt_image import GPTImageAdapter
from runtime.backends.ltx import LTXAdapter
from runtime.backends.qwen import QwenAdapter
from runtime.backends.sdxl import SDXLAdapter
from runtime.backends.wan import WANAdapter

ADAPTER_BY_FAMILY: dict[str, BackendAdapter] = {
    "flux": FluxAdapter(),
    "sdxl": SDXLAdapter(),
    "qwen": QwenAdapter(),
    "gpt_image": GPTImageAdapter(),
    "wan": WANAdapter(),
    "ltx": LTXAdapter(),
    "cogvideo": CogVideoAdapter(),
    "animatediff": AnimateDiffAdapter(),
}

_GENERIC = GenericAdapter()

#: The eight named mission adapters (same instances as the family map).
NAMED_ADAPTERS: dict[str, BackendAdapter] = {
    key: ADAPTER_BY_FAMILY[key]
    for key in (
        "flux",
        "sdxl",
        "qwen",
        "gpt_image",
        "wan",
        "ltx",
        "cogvideo",
        "animatediff",
    )
}


def adapter_for(model_key: str) -> BackendAdapter:
    """The adapter for a model's family (generic for unregistered ones)."""
    try:
        family = REGISTRY.get(model_key).family
    except KeyError:
        return _GENERIC
    return ADAPTER_BY_FAMILY.get(family, _GENERIC)


def adapt_backend(
    prompt: CompiledPrompt,
    plan: SceneModelPlan,
) -> BackendWorkflow:
    """Compile one scene's backend workflow from the model plan."""
    profile = profile_for(plan.workflow_profile)
    return adapter_for(plan.model_profile.image_model).adapt(prompt, profile, plan)


def render_profile_for(plan: SceneModelPlan) -> RenderProfile:
    """The render profile a plan's workflow genre implies."""
    return profile_for(plan.workflow_profile)
