"""PR1M3 Labs knowledge base schema: column contract and composition helpers."""

import json
import re

CSV_PATH = "assets/knowledge_base.csv"
TOPICS_CSV_PATH = "assets/topics.csv"

COLUMNS: list[str] = [
    "topic",
    "difficulty",
    "category",
    "subcategory",
    "keywords",
    "search_intent",
    "viewer_level",
    "core_question",
    "learning_objective",
    "engineering_summary",
    "real_world_application",
    "common_misconceptions",
    "teaching_strategy",
    "script",
    "scene_count",
    "scene_plan_json",
    "visual_spec_json",
    "thumbnail_visual_spec",
    "thumbnail_prompt",
    "thumbnail_negative_prompt",
    "image_prompt_pack_json",
    "negative_prompt",
    "camera_language",
    "lighting_style",
    "color_palette",
    "composition_style",
    "render_style",
    "materials",
    "environment",
    "motion_plan",
    "animation_notes",
    "text_overlay",
    "title",
    "title_variations_json",
    "description",
    "hashtags",
    "seo_keywords_json",
    "references_json",
    "fact_check_notes",
]

VIEWER_LEVEL = {"B": "Beginner", "I": "Intermediate", "A": "Advanced"}

GLOBAL_NEGATIVE = (
    "fantasy, sci-fi, magic, glowing fake circuitry, impossible machines, fictional engineering, "
    "cartoon, anime, illustration, watermarks, text artifacts, signatures, blurry, out of focus, "
    "low quality, low resolution, deformed geometry, distorted perspective, extra limbs, "
    "unnatural colors, oversaturated, jpeg artifacts, people, hands, logos"
)


def json_field(value: object) -> str:
    """Serialize a Python value to a compact, valid JSON string."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def lens_for(shot: str) -> str:
    """Map a curated shot description to a lens specification."""
    s = shot.lower()
    if "macro" in s or "extreme close" in s:
        return "100mm f/2.8 macro"
    if "close-up" in s or "closeup" in s or "close up" in s:
        return "85mm f/1.8"
    if "overhead" in s or "top-down" in s or "top down" in s:
        return "40mm f/2.8"
    if "wide" in s:
        return "24mm f/2.8"
    if "orbit" in s or "turntable" in s:
        return "50mm f/1.8"
    if "medium" in s:
        return "35mm f/2"
    return "35mm f/2"


def angle_for(shot: str) -> str:
    s = shot.lower()
    if "low-angle" in s or "low angle" in s:
        return "Low"
    if "overhead" in s or "top-down" in s or "top down" in s:
        return "Top-down"
    if "high-angle" in s or "high angle" in s:
        return "High"
    if "eye-level" in s or "eye level" in s:
        return "Eye-level"
    return "Slightly low"


def composition_for(shot: str, base: str) -> str:
    s = shot.lower()
    extra = []
    if "low-angle" in s or "low angle" in s:
        extra.append("low angle")
    if "overhead" in s or "top-down" in s or "top down" in s:
        extra.append("top-down framing")
    if "close" in s:
        extra.append("tight framing")
    if "wide" in s:
        extra.append("open framing")
    if "centered" in s or "centre" in s:
        extra.append("centered subject")
    if extra:
        return base + ", " + ", ".join(extra)
    return base


def camera_from(shot: str) -> str:
    """Full camera direction phrase for a shot."""
    return re.sub(r"\s+", " ", shot.strip()).strip()


def estimate_words(script: str) -> int:
    return len(script.split())


def estimated_duration(script: str) -> float:
    """Assumed narration rate: ~2.8 words per second."""
    return estimate_words(script) / 2.8


def scene_duration_sum(scenes: list[dict]) -> float:
    return round(sum(float(s.get("duration", 0)) for s in scenes), 1)