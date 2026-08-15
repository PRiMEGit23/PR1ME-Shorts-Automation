"""Sampler selector: pick the sampler for a model and genre (Phase 10).

The genre (render profile) implies a preferred sampler; the model decides
what it can run. The rule here is a preference order, not a capability
table: capabilities live in the registry, and the selected sampler is
always clamped into the model's supported set.
"""

from __future__ import annotations

from knowledge.model_director.backend_rules import default_sampler
from knowledge.model_director.model_registry import REGISTRY
from knowledge.render_optimizer.render_profiles import RenderProfileKey

#: Preferred samplers per genre, best first. Only the names in the
#: registry's supported_samplers lists are ever chosen.
_PROFILE_SAMPLER_PREFERENCE: dict[RenderProfileKey, tuple[str, ...]] = {
    RenderProfileKey.MACRO: ("dpmpp_2m", "euler", "flow_mg", "euler_a", "ddim", "dpmpp_sde"),
    RenderProfileKey.DIAGRAM: ("dpmpp_2m", "euler", "euler_a", "ddim"),
    RenderProfileKey.CAD: ("dpmpp_2m", "euler", "euler_a", "ddim"),
    RenderProfileKey.BLUEPRINT: ("euler_a", "euler", "dpmpp_2m", "ddim"),
    RenderProfileKey.EXPLODED: ("dpmpp_2m", "euler", "euler_a"),
    RenderProfileKey.CUTAWAY: ("dpmpp_2m", "euler", "euler_a"),
    RenderProfileKey.TRANSPARENT: ("dpmpp_2m", "euler", "euler_a"),
    RenderProfileKey.STRESS_VISUALIZATION: ("dpmpp_2m", "euler", "euler_a"),
    RenderProfileKey.THERMAL_VISUALIZATION: ("dpmpp_2m", "euler", "euler_a"),
    RenderProfileKey.COMPARISON: ("dpmpp_2m", "euler", "euler_a"),
    RenderProfileKey.HERO: ("dpmpp_2m", "euler", "euler_a"),
}

_DEFAULT_PREFERENCE: tuple[str, ...] = (
    "dpmpp_2m",
    "euler",
    "euler_a",
    "flow_mg",
    "ddim",
    "dpmpp_sde",
)


def select_sampler(
    model_key: str,
    profile: RenderProfileKey,
    *,
    fallback: str | None = None,
) -> str:
    """The model-supported sampler most preferred for the genre."""
    spec = REGISTRY.get(model_key)
    preference = _PROFILE_SAMPLER_PREFERENCE.get(profile, _DEFAULT_PREFERENCE)
    if fallback is not None and fallback in spec.supported_samplers:
        return fallback
    for candidate in preference:
        if candidate in spec.supported_samplers:
            return candidate
    return default_sampler(model_key)


def preferred_samplers(profile: RenderProfileKey) -> tuple[str, ...]:
    """The genre's sampler preference order (for tests and docs)."""
    return _PROFILE_SAMPLER_PREFERENCE.get(profile, _DEFAULT_PREFERENCE)
