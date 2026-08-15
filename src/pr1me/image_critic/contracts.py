"""Image Critic contracts.

The critic is a pure data engine: it receives everything it needs to evaluate
one render (the prompts that produced it, the render's integrity signals, and
— for the active pipeline path — the prompt validator's score carried on the
workflow frame) and returns a structured :class:`ImageCritique`. Rejected
renders and run-level quality metrics are reported through
:class:`RejectedRender` and :class:`QualityMetrics`.
"""

from __future__ import annotations

from pydantic import Field

from pr1me.models.common import StableModel

__all__ = [
    "CriticDimension",
    "ImageCritique",
    "ImageCriticInput",
    "ImageQualityReport",
    "QualityMetrics",
    "RejectedRender",
]

#: The critic's ten quality dimensions, in report order. Each is scored 0-10.
#: Pixel-level verification of every dimension requires a vision-capable
#: provider; without one, the deterministic core scores the evidence it can
#: verify (render integrity + prompt contract) and records the limitation in
#: each dimension's notes.
DIMENSIONS: tuple[str, ...] = (
    "engineering_correctness",
    "teaching_effectiveness",
    "composition",
    "readability",
    "object_hierarchy",
    "visual_clutter",
    "camera_quality",
    "lighting",
    "consistency",
    "thumbnail_potential",
)


class CriticDimension(StableModel):
    """Score of one critic dimension."""

    name: str = Field(..., min_length=1)
    score: int = Field(..., ge=0, le=10)
    max: int = Field(default=10, ge=1)
    note: str = ""


class ImageCritique(StableModel):
    """The critic's verdict on one rendered image."""

    shot_id: int = Field(..., ge=1)
    attempt: int = Field(default=1, ge=1)
    score: int = Field(..., ge=0, le=100)
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    dimensions: list[CriticDimension] = Field(default_factory=list)
    seed: int | None = Field(default=None, ge=0)

    @property
    def failed_dimensions(self) -> list[str]:
        """Names of the dimensions that scored below their maximum."""
        return [dim.name for dim in self.dimensions if dim.score < dim.max]


class ImageCriticInput(StableModel):
    """Everything the critic needs to evaluate one render."""

    shot_id: int = Field(..., ge=1)
    positive_prompt: str = Field(..., min_length=1)
    negative_prompt: str = Field(..., min_length=1)
    is_thumbnail: bool = False
    validation_score: int | None = Field(default=None, ge=0, le=100)
    render_valid_png: bool = True
    render_bytes: int = Field(default=0, ge=0)
    render_width: int = Field(default=0, ge=0)
    render_height: int = Field(default=0, ge=0)
    requested_width: int = Field(default=0, ge=0)
    requested_height: int = Field(default=0, ge=0)
    attempt: int = 1
    seed: int | None = Field(default=None, ge=0)


class RejectedRender(StableModel):
    """One render that failed the quality gate (or lost a thumbnail contest)."""

    shot_id: int = Field(..., ge=1)
    attempt: int = Field(..., ge=1)
    file: str = Field(..., min_length=1)
    score: int = Field(..., ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class QualityMetrics(StableModel):
    """Run-level image quality numbers for the end-of-run report."""

    total_attempted: int = Field(..., ge=0)
    total_accepted: int = Field(..., ge=0)
    total_rejected: int = Field(..., ge=0)
    regeneration_rate: float = Field(..., ge=0.0, le=1.0)
    average_score: float = Field(..., ge=0.0, le=100.0)
    min_score: int = Field(..., ge=0, le=100)
    max_score: int = Field(..., ge=0, le=100)
    gates: list[str] = Field(default_factory=list)


class ImageQualityReport(StableModel):
    """The end-of-run image quality report.

    Covers every report item the channel requires: per-render critic scores,
    rejected images (with the reason each failed), the final accepted images,
    and the run-level quality metrics.
    """

    critic_scores: list[ImageCritique] = Field(default_factory=list)
    rejected_renders: list[RejectedRender] = Field(default_factory=list)
    accepted_shot_ids: list[int] = Field(default_factory=list)
    metrics: QualityMetrics
