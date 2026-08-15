"""Model profiles: per-model-family compilation rules.

Profiles are pure data. Rendering quality tokens, aspect phrasing, negative
syntax, guidance, and step defaults all live here and never inside the
knowledge base. A new image model only needs a new profile plus a compiler
implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

SHORTS_SIZE = (1080, 1920)


class PromptStyle(StrEnum):
    COMMA_LIST = "comma_list"
    NATURAL_PARAGRAPH = "natural_paragraph"
    CHAT_PARAGRAPH = "chat_paragraph"
    STRUCTURED_LIST = "structured_list"


@dataclass(frozen=True)
class ModelProfile:
    key: str
    family: str
    prompt_style: PromptStyle
    supports_negatives: bool
    quality_tokens: tuple[str, ...]
    style_prefix: str
    max_positive_words: int
    guidance_default: float
    steps_default: int
    negative_tokens: tuple[str, ...]
    aspect_phrase: str
    thumbnail_tokens: tuple[str, ...]


SDXL = ModelProfile(
    key="sdxl",
    family="sdxl",
    prompt_style=PromptStyle.COMMA_LIST,
    supports_negatives=True,
    quality_tokens=("ultra sharp", "high detail", "professional product photography"),
    style_prefix="",
    max_positive_words=120,
    guidance_default=7.0,
    steps_default=30,
    negative_tokens=(
        "fantasy",
        "sci-fi",
        "magic",
        "cartoon",
        "anime",
        "illustration",
        "watermarks",
        "text artifacts",
        "signatures",
        "blurry",
        "out of focus",
        "low quality",
        "low resolution",
        "deformed geometry",
        "distorted perspective",
        "extra limbs",
        "unnatural colors",
        "oversaturated",
        "jpeg artifacts",
        "people",
        "hands",
        "logos",
    ),
    aspect_phrase="vertical 9:16 composition",
    thumbnail_tokens=("high contrast", "strong subject separation", "bold readable composition"),
)

FLUX = ModelProfile(
    key="flux",
    family="flux",
    prompt_style=PromptStyle.NATURAL_PARAGRAPH,
    supports_negatives=False,
    quality_tokens=("sharp focus", "detailed"),
    style_prefix="",
    max_positive_words=150,
    guidance_default=3.5,
    steps_default=28,
    negative_tokens=(),
    aspect_phrase="",
    thumbnail_tokens=("bold composition", "high contrast"),
)

GPT_IMAGE = ModelProfile(
    key="gpt_image",
    family="openai",
    prompt_style=PromptStyle.CHAT_PARAGRAPH,
    supports_negatives=False,
    quality_tokens=("high detail",),
    style_prefix="",
    max_positive_words=110,
    guidance_default=0.0,
    steps_default=0,
    negative_tokens=(),
    aspect_phrase="9:16",
    thumbnail_tokens=("bold", "high contrast"),
)

QWEN_IMAGE = ModelProfile(
    key="qwen_image",
    family="qwen",
    prompt_style=PromptStyle.STRUCTURED_LIST,
    supports_negatives=True,
    quality_tokens=("high detail",),
    style_prefix="",
    max_positive_words=200,
    guidance_default=4.5,
    steps_default=24,
    negative_tokens=(
        "low quality",
        "blurry",
        "deformed geometry",
        "people",
        "hands",
        "text",
        "logos",
    ),
    aspect_phrase="9:16",
    thumbnail_tokens=("high contrast",),
)

PROFILES: dict[str, ModelProfile] = {p.key: p for p in (SDXL, FLUX, GPT_IMAGE, QWEN_IMAGE)}
