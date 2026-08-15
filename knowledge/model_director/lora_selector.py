"""LoRA selector: the LoRA set for a model family and genre (Phase 10).

The render profiles (``knowledge.render_optimizer``) already own the
SDXL-family genre LoRAs (macro-detail, cad-sharp, hero-contrast); this
module reuses them as the base for the SDXL family and only *adds*
model-family-specific LoRAs for other families. No genre rule is
duplicated: the render profile remains the single source for the SDXL
set, this module owns the family-specific sets.
"""

from __future__ import annotations

from knowledge.model_director.model_registry import REGISTRY
from knowledge.render_optimizer.render_profiles import RenderProfileKey, profile_for

#: Family -> genre -> model-specific LoRAs (SDXL family adds nothing; the
#: render profile's own loras are the single source there).
_FAMILY_LORAS: dict[str, dict[RenderProfileKey, tuple[str, ...]]] = {
    "flux": {
        RenderProfileKey.MACRO: ("flux-macro-detail",),
        RenderProfileKey.HERO: ("flux-hero-contrast",),
        RenderProfileKey.CAD: ("flux-cad-sharp",),
    },
    "qwen": {
        RenderProfileKey.HERO: ("qwen-hero",),
    },
    "hiredream": {
        RenderProfileKey.HERO: ("hiredream-hero",),
    },
    "gpt_image": {
        RenderProfileKey.HERO: ("gpt-image-hero",),
    },
}


def select_loras(model_key: str, profile: RenderProfileKey) -> tuple[str, ...]:
    """The complete LoRA set: render-profile genre LoRAs plus family LoRAs.

    For the SDXL family the render profile's own ``loras`` are returned
    verbatim (no family additions), so the SDXL workflow stays identical
    to the legacy workflow builder output.
    """
    spec = REGISTRY.get(model_key)
    family_loras = _FAMILY_LORAS.get(spec.family, {}).get(profile, ())
    if spec.family == "sdxl":
        return tuple(profile_for(profile).loras)
    return family_loras
