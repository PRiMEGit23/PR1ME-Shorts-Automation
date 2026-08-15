"""ControlNet selector: the conditioning strategy per scene (Phase 10).

The scene's shot type implies a conditioning need (depth for inspection
shots, lineart for technical drawings, canny for comparisons); the model
decides whether it can run it. The selection is clamped into the model's
supported set, falling back to ``none`` (an unsupported ControlNet is
never silently applied).
"""

from __future__ import annotations

from knowledge.model_director.model_registry import REGISTRY
from knowledge.visual_intelligence.storyboard import ShotType

#: Shot type -> preferred ControlNet strategy.
_SHOT_CONTROLNET: dict[ShotType, str] = {
    ShotType.MACRO: "depth",
    ShotType.EXTREME_MACRO: "depth",
    ShotType.MICROSCOPE: "depth",
    ShotType.CROSS_SECTION: "depth",
    ShotType.CUTAWAY: "depth",
    ShotType.TRANSPARENT: "depth",
    ShotType.EXPLODED_VIEW: "canny",
    ShotType.BLUEPRINT: "lineart",
    ShotType.ANNOTATED_DIAGRAM: "lineart",
    ShotType.COMPARISON_SPLIT: "canny",
    ShotType.BEFORE_AFTER: "canny",
    ShotType.MANUFACTURING_SEQUENCE: "lineart",
    ShotType.PROCESS_SEQUENCE: "lineart",
    ShotType.CAD_RENDER: "lineart",
    ShotType.ORTHOGRAPHIC: "lineart",
    ShotType.ISOMETRIC: "lineart",
    ShotType.WIREFRAME_OVERLAY: "lineart",
    ShotType.XRAY: "depth",
}

#: Preferred ControlNet strategies, best first (used to clamp into the
#: model's supported set).
_CONTROLNET_PREFERENCE: tuple[str, ...] = ("depth", "canny", "lineart", "pose")


def select_controlnet(model_key: str, shot_type: ShotType) -> str:
    """The model-supported ControlNet strategy for the shot (or none)."""
    spec = REGISTRY.get(model_key)
    wanted = _SHOT_CONTROLNET.get(shot_type)
    if wanted is not None and wanted in spec.supported_controlnet:
        return wanted
    for candidate in _CONTROLNET_PREFERENCE:
        if candidate in spec.supported_controlnet:
            return candidate
    return "none"


def select_ip_adapter(model_key: str, *, is_hero: bool) -> str:
    """IPAdapter usage: style transfer only for hero beats when supported."""
    if not is_hero:
        return "none"
    spec = REGISTRY.get(model_key)
    if "style_transfer" in spec.supported_ip_adapters:
        return "style_transfer"
    return "none"


def select_depth_strategy(model_key: str, shot_type: ShotType) -> str:
    """Depth conditioning: monocular depth for inspection shots when the
    model supports it."""
    spec = REGISTRY.get(model_key)
    if shot_type in _SHOT_CONTROLNET and _SHOT_CONTROLNET[shot_type] == "depth":
        for candidate in ("monocular", "depth_map"):
            if candidate in spec.supported_depth:
                return candidate
    return "none"


def select_segmentation_strategy(model_key: str) -> str:
    """Segmentation conditioning: SAM only when the model supports it."""
    spec = REGISTRY.get(model_key)
    for candidate in ("sam",):
        if candidate in spec.supported_segmentation:
            return candidate
    return "none"
