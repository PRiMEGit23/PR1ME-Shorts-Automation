"""Image Critic.

Scores every generated image against the channel's ten quality dimensions and
feeds targeted corrections back into the render loop when an image fails the
quality gate.

Pipeline position:

    ComfyUI -> Image Critic -> Accepted Images

The critic evaluates engineering correctness, teaching effectiveness,
composition, readability, object hierarchy, visual clutter, camera quality,
lighting, consistency, and thumbnail potential, returning one score per
render. Images below the gate threshold are regenerated with *targeted*
corrections — the failed dimensions map onto concrete prompt guidance — never
a blind retry.
"""

from __future__ import annotations

from pr1me.image_critic.contracts import (
    CriticDimension,
    ImageCriticInput,
    ImageCritique,
    ImageQualityReport,
    QualityMetrics,
    RejectedRender,
)
from pr1me.image_critic.critic import ImageCritic, critique_render

__all__ = [
    "CriticDimension",
    "ImageCritic",
    "ImageCriticInput",
    "ImageCritique",
    "ImageQualityReport",
    "QualityMetrics",
    "RejectedRender",
    "critique_render",
]
