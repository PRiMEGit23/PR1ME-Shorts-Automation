"""PR1M3 Labs knowledge base builder.

Deterministically composes `assets/knowledge_base.csv` from:
- knowledge/taxonomy.py          (the 400-topic spine)
- knowledge/batches/*.py         (curated per-topic content)
- knowledge/category_defaults.py (channel visual identity defaults)

The CSV is the frozen runtime artifact: the pipeline reads it and never
needs an LLM for scripting, visuals, prompts, or metadata.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from knowledge.category_defaults import CATEGORY_DEFAULTS, STANDARD_REFERENCES  # noqa: E402
from knowledge.schema import (  # noqa: E402
    COLUMNS,
    CSV_PATH,
    GLOBAL_NEGATIVE,
    TOPICS_CSV_PATH,
    VIEWER_LEVEL,
    angle_for,
    camera_from,
    composition_for,
    json_field,
    lens_for,
)
from knowledge.taxonomy import CATEGORIES, TAXONOMY  # noqa: E402


def load_curated() -> dict[str, dict[str, Any]]:
    """Merge every curated batch file into one topic-keyed dictionary."""
    curated: dict[str, dict[str, Any]] = {}
    batches_dir = ROOT / "knowledge" / "batches"
    for path in sorted(batches_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        namespace: dict[str, Any] = {}
        exec(path.read_text(encoding="utf-8"), namespace)
        for entry in namespace.get("CURATED", []):
            topic = entry["topic"]
            if topic in curated:
                raise ValueError(f"duplicate curated topic: {topic}")
            curated[topic] = entry
    return curated


def compose_scene_plan(scenes: list[dict], defaults: dict) -> list[dict]:
    plan = []
    for idx, s in enumerate(scenes, start=1):
        plan.append(
            {
                "scene_id": f"S{idx}",
                "goal": s["goal"],
                "teaching_point": s["teaching_point"],
                "camera": camera_from(s["shot"]),
                "lens": lens_for(s["shot"]),
                "composition": composition_for(s["shot"], defaults["composition_style"]),
                "foreground": f"Subject: {s['objects'][0]}",
                "background": s["background"],
                "lighting": s["lighting"],
                "motion": s["motion"],
                "objects": s["objects"],
                "transition": s["transition"],
                "duration": float(s["duration"]),
            }
        )
    return plan


def compose_visual_spec(scenes: list[dict], defaults: dict) -> dict:
    s0 = scenes[0]
    return {
        "subject": s0["objects"][0],
        "environment": defaults["environment"],
        "camera": lens_for(s0["shot"]),
        "angle": angle_for(s0["shot"]),
        "lighting": defaults["lighting_style"],
        "materials": defaults["materials"],
        "focus": s0["goal"],
        "style": defaults["render_style"],
    }


def compose_prompt_pack(scenes: list[dict], defaults: dict) -> list[dict]:
    pack = []
    for idx, s in enumerate(scenes, start=1):
        pack.append(
            {
                "shot_id": f"shot_{idx:03d}",
                "positive_prompt": (
                    f"{s['prompt']}, {camera_from(s['shot'])}, {s['lighting']}, "
                    f"{composition_for(s['shot'], defaults['composition_style'])}, "
                    f"{defaults['style_tokens']}"
                ),
                "negative_prompt": GLOBAL_NEGATIVE,
                "camera": camera_from(s["shot"]),
                "lens": lens_for(s["shot"]),
                "lighting": s["lighting"],
                "composition": composition_for(s["shot"], defaults["composition_style"]),
                "style": defaults["render_style"],
                "render_notes": defaults["render_notes"],
            }
        )
    return pack


def compose_thumbnail_visual_spec(t: dict) -> dict:
    return {
        "concept": t["concept"],
        "subject": t["subject"],
        "background": t["background"],
        "angle": t["angle"],
        "lighting": t["lighting"],
        "composition": t["composition"],
        "text": t["text"],
        "elements": t["elements"],
        "style": t["style"],
        "mood": t["mood"],
    }


def category_key_for(topic: str) -> str:
    for key, entries in TAXONOMY.items():
        if any(e[0] == topic for e in entries):
            return key
    raise KeyError(f"topic not in taxonomy: {topic}")


THUMBNAIL_SUFFIX = (
    "ultra sharp, high detail, strong subject contrast, bold readable composition, "
    "professional YouTube thumbnail style, vertical 9:16"
)


def compose_row(tax: tuple, curated: dict) -> dict[str, str]:
    topic, difficulty, subcategory, keywords, search_intent = tax
    key = category_key_for(topic)
    defaults = CATEGORY_DEFAULTS[key]
    scenes = curated["scenes"]
    seo = curated["seo"]
    thumb_prompt = curated["thumbnail"]["prompt"].strip()
    if not thumb_prompt.endswith("."):
        thumb_prompt += "."
    thumb_prompt = f"{thumb_prompt} {THUMBNAIL_SUFFIX}"

    return {
        "topic": topic,
        "difficulty": difficulty,
        "category": CATEGORIES[key],
        "subcategory": subcategory,
        "keywords": json_field(keywords.split(";")),
        "search_intent": curated.get("search_intent", search_intent),
        "viewer_level": curated.get("viewer_level", VIEWER_LEVEL[difficulty]),
        "core_question": curated["core_question"],
        "learning_objective": curated["learning_objective"],
        "engineering_summary": curated["engineering_summary"],
        "real_world_application": curated["real_world_application"],
        "common_misconceptions": json_field(curated["common_misconceptions"]),
        "teaching_strategy": curated["teaching_strategy"],
        "script": curated["script"],
        "scene_count": str(len(scenes)),
        "scene_plan_json": json_field(compose_scene_plan(scenes, defaults)),
        "visual_spec_json": json_field(compose_visual_spec(scenes, defaults)),
        "thumbnail_visual_spec": json_field(compose_thumbnail_visual_spec(curated["thumbnail"])),
        "thumbnail_prompt": thumb_prompt,
        "thumbnail_negative_prompt": curated["thumbnail"]["negative_prompt"],
        "image_prompt_pack_json": json_field(compose_prompt_pack(scenes, defaults)),
        "negative_prompt": GLOBAL_NEGATIVE,
        "camera_language": curated.get("camera_language", defaults["camera_language"]),
        "lighting_style": curated.get("lighting_style", defaults["lighting_style"]),
        "color_palette": curated.get("color_palette", defaults["color_palette"]),
        "composition_style": curated.get("composition_style", defaults["composition_style"]),
        "render_style": curated.get("render_style", defaults["render_style"]),
        "materials": json_field(curated.get("materials", defaults["materials"])),
        "environment": curated.get("environment", defaults["environment"]),
        "motion_plan": curated.get("motion_plan", defaults["motion_plan"]),
        "animation_notes": curated.get("animation_notes", defaults["animation_notes"]),
        "text_overlay": json_field(curated["text_overlay"]),
        "title": seo["title"],
        "title_variations_json": json_field(seo["title_variations"]),
        "description": seo["description"],
        "hashtags": json_field(seo["hashtags"]),
        "seo_keywords_json": json_field(seo["seo_keywords"]),
        "references_json": json_field(curated.get("references") or STANDARD_REFERENCES[key]),
        "fact_check_notes": json_field(curated["fact_check"]),
    }


def main() -> None:
    curated = load_curated()
    present_entries: list[tuple] = [
        e for _, entries in TAXONOMY.items() for e in entries if e[0] in curated
    ]
    missing = [e[0] for _, entries in TAXONOMY.items() for e in entries if e[0] not in curated]

    if not present_entries:
        print("ERROR: no curated topics available")
        raise SystemExit(1)

    rows = [compose_row(e, curated[e[0]]) for e in present_entries]

    with (ROOT / CSV_PATH).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    with (ROOT / TOPICS_CSV_PATH).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["topic", "difficulty", "category", "subcategory", "keywords", "search_intent"])
        for key, entries in TAXONOMY.items():
            for e in entries:
                writer.writerow([e[0], e[1], CATEGORIES[key], e[2], e[3], e[4]])

    print(f"wrote {CSV_PATH}: {len(rows)} rows")
    total_topics = sum(len(v) for v in TAXONOMY.values())
    print(f"wrote {TOPICS_CSV_PATH}: {total_topics} topics")
    print(f"coverage: {len(rows)}/{total_topics} topics curated; missing={len(missing)}")


if __name__ == "__main__":
    main()
