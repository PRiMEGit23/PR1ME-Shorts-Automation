"""Scheduler selector: pick the scheduler for a model and sampler (Phase 10).

Flow-based families (FLUX, WAN, LTX, Hunyuan, CogVideoX, Qwen) run
flow-matching schedules; SDXL-family models run karras; the rest run their
family default. Capabilities stay in the registry - this module only
decides which *supported* scheduler the chosen sampler implies.
"""

from __future__ import annotations

from knowledge.model_director.backend_rules import backend_params, default_scheduler
from knowledge.model_director.model_registry import REGISTRY

#: Sampler -> scheduler preference (best first), applied on top of the
#: model's supported set.
_SAMPLER_SCHEDULER_PREFERENCE: dict[str, tuple[str, ...]] = {
    "dpmpp_2m": ("karras", "flow_matching", "normal", "sde"),
    "dpmpp_sde": ("sde", "normal", "karras"),
    "euler": ("flow_matching", "euler", "euler_ancestral", "normal", "karras"),
    "euler_a": ("karras", "euler_ancestral", "normal"),
    "ddim": ("normal", "karras"),
    "flow_mg": ("flow_matching", "normal"),
}


def select_scheduler(model_key: str, sampler: str) -> str:
    """The model-supported scheduler most preferred for the sampler."""
    spec = REGISTRY.get(model_key)
    preference = _SAMPLER_SCHEDULER_PREFERENCE.get(sampler, ())
    for candidate in preference:
        if candidate in spec.supported_schedulers:
            return candidate
    return default_scheduler(model_key)


def select_vae(model_key: str) -> str:
    """The model family's default VAE (single source: backend rules)."""
    return backend_params(model_key).vae
