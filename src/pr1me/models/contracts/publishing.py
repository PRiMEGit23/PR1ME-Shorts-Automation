"""Publishing Assets stage contracts (Metadata + Thumbnail).

The metadata stage consumes the approved topic and script, generates the
YouTube Shorts publication metadata (prompt 06), and returns a single
:class:`MetadataOutput`. The thumbnail stage turns the same topic and script
into a visual concept (prompt 05) and renders one ``thumbnail.png`` through
the ComfyUI image provider, returning a single :class:`ThumbnailManifestOutput`.

Because the pipeline runner flattens every upstream output into one dict, only
the uniquely-named columns survive intact. :class:`PublishingInput` carries
the topic and the four narration blocks -- exactly the fields the metadata and
thumbnail prompts declare as their input.

These models are plain data: no transport, no image generation, no filesystem
access.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import ConfigDict, Field

from pr1me.models.common import StableModel, ValidationDescriptor
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.meta import Visibility

#: Allowed search intents from prompt 06 (one drives the whole metadata set).
SearchIntent = Literal[
    "How To",
    "Troubleshooting",
    "Explanation",
    "Comparison",
    "Settings",
    "Beginner Guide",
    "Advanced Guide",
    "Buying Advice",
    "Optimization",
]

#: Allowed viewer levels from prompt 06.
TargetAudience = Literal["Beginner", "Intermediate", "Advanced"]

#: Allowed curiosity triggers from prompt 05 (exactly one per concept).
CuriosityTrigger = Literal[
    "Contradiction",
    "Comparison",
    "Unexpected Result",
    "Transformation",
    "Hidden Mechanism",
    "Failure",
    "Success",
    "Question",
    "Scale",
    "Precision",
]


class PublishingInput(StageInput):
    """Shared input for the metadata and thumbnail stages.

    ``topic`` carries the approved topic and the four script fields the
    approved narration. ``extra`` is ignored because the pipeline runner feeds
    the flattened outputs of every upstream stage (including the video render
    manifest) alongside these.
    """

    model_config = ConfigDict(extra="ignore")

    topic: str = Field(..., min_length=1, max_length=60)
    hook: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    practical_insight: str = Field(..., min_length=1)
    ending: str = Field(..., min_length=1)

    def script_blocks(self) -> dict[str, str]:
        """The four narration blocks as one JSON-ready dict."""
        return {
            "hook": self.hook,
            "explanation": self.explanation,
            "practical_insight": self.practical_insight,
            "ending": self.ending,
        }

    def user_message(self) -> str:
        """The user prompt handed to prompt 05/06, mirroring their input shape."""
        return "\n".join(
            [
                f"topic: {self.topic}",
                f"script: {json.dumps(self.script_blocks())}",
            ]
        )


class MetadataOutput(StageOutput):
    """The complete publication metadata for one Short (prompt 06).

    ``language`` is the stage-owned channel default ("en"); every other field
    mirrors prompt 06's output schema exactly. ``validation`` is ``ok`` only
    when every deterministic SEO check passed.
    """

    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    tags: list[str] = Field(..., min_length=5, max_length=10)
    hashtags: list[str] = Field(default_factory=list, max_length=3)
    category: str = Field(..., min_length=1)
    visibility: Visibility
    publish_at: str | None = Field(default=None)
    made_for_kids: bool = False
    primary_keyword: str = Field(..., min_length=1)
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: SearchIntent
    target_audience: TargetAudience
    language: str = Field("en", min_length=1)
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)


class ThumbnailColors(StableModel):
    """The three channel-palette colors of one thumbnail concept."""

    background: str = Field(..., min_length=1)
    accent: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class ThumbnailConcept(StableModel):
    """The concept the LLM designs (prompt 05) before ComfyUI renders it.

    Reproducible by construction: every field is a plain visual instruction
    an image generator can execute without judgment.
    """

    subject: str = Field(..., min_length=1)
    composition: str = Field(..., min_length=1)
    colors: ThumbnailColors
    curiosity_trigger: CuriosityTrigger
    eye_path: str = Field(..., min_length=1)
    text_overlay: str | None = Field(default=None)
    focal_point: str = Field(..., min_length=1)
    concept_reason: str = Field(..., min_length=1)
    style: str = Field(..., min_length=1)


class ThumbnailRenderMetadata(StableModel):
    """Render provenance recorded on one finalized thumbnail."""

    backend: str = Field(..., min_length=1)
    workflow: str = Field(..., min_length=1)
    comfyui_prompt_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    seed: int = Field(..., ge=0, le=2**63 - 1)
    steps: int = Field(..., ge=1, le=150)
    cfg: float = Field(..., ge=0.0, le=20.0)
    sampler: str = Field(..., min_length=1)
    scheduler: str = Field(..., min_length=1)


class ThumbnailManifestOutput(StageOutput):
    """The verification report for the single rendered ``thumbnail.png``.

    ``file`` points at the exact deliverable; ``concept`` records the exact
    visual instructions that produced it. ``validation`` is ``ok`` only when
    every post-render check passed.
    """

    output_dir: str
    file: str = Field(..., min_length=1)
    bytes: int = Field(..., ge=0)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    checksum: str = Field(..., min_length=1)
    concept: ThumbnailConcept
    metadata: ThumbnailRenderMetadata
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)