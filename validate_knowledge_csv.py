"""PR1M3 Labs knowledge base validator.

QA gate for assets/knowledge_base.csv. Every row must satisfy:

- exact 39-column schema, no empty cells
- every JSON column parses and has no trailing commas
- script narration lands in the 20-35 second Short budget (~2.8 wps)
- scene durations sum close to the narration duration
- scene_count matches the scene plan
- SEO completeness: 5 title variations, >=3 hashtags, >=5 seo keywords
- fact check and references present
- no duplicate topics

Exits non-zero on any failure so CI / the pipeline can gate on it.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from knowledge.schema import COLUMNS, CSV_PATH, scene_duration_sum  # noqa: E402

JSON_COLUMNS = {
    "keywords",
    "common_misconceptions",
    "scene_plan_json",
    "visual_spec_json",
    "thumbnail_visual_spec",
    "image_prompt_pack_json",
    "materials",
    "text_overlay",
    "title_variations_json",
    "hashtags",
    "seo_keywords_json",
    "references_json",
    "fact_check_notes",
}

NARRATION_WPS = 2.8
MIN_SECONDS, MAX_SECONDS = 20.0, 35.0


def load_rows() -> list[dict[str, str]]:
    path = ROOT / CSV_PATH
    if not path.exists():
        print(f"FAIL: {CSV_PATH} does not exist")
        raise SystemExit(1)
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            print(f"FAIL: header mismatch\n  got: {reader.fieldnames}\n  expected: {COLUMNS}")
            raise SystemExit(1)
        return [dict(r) for r in reader]


def check_row(row: dict[str, str], errors: list[str]) -> None:
    topic = row["topic"]

    for col in COLUMNS:
        if not row.get(col, "").strip():
            errors.append(f"[{topic}] empty column: {col}")

    for col in JSON_COLUMNS:
        raw = row.get(col, "")
        if not raw:
            continue
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"[{topic}] invalid JSON in {col}: {exc}")

    words = len(row["script"].split())
    duration = words / NARRATION_WPS
    if not (MIN_SECONDS <= duration <= MAX_SECONDS):
        errors.append(f"[{topic}] script {words} words -> {duration:.1f}s outside budget")

    try:
        scenes = json.loads(row["scene_plan_json"])
        if len(scenes) != int(row["scene_count"]):
            errors.append(f"[{topic}] scene_count {row['scene_count']} != plan scenes {len(scenes)}")
        if len(scenes) < 4:
            errors.append(f"[{topic}] only {len(scenes)} scenes (min 4)")
        total = scene_duration_sum(scenes)
        if not (18.0 <= total <= 40.0):
            errors.append(f"[{topic}] scene durations sum to {total}s (expected 18-40s)")
        elif abs(total - duration) / duration > 0.3:
            errors.append(f"[{topic}] scene sum {total}s vs narration {duration:.1f}s drift >30%")
        for scene in scenes:
            for field in (
                "scene_id",
                "goal",
                "teaching_point",
                "camera",
                "lens",
                "composition",
                "foreground",
                "background",
                "lighting",
                "motion",
                "objects",
                "transition",
                "duration",
            ):
                if field not in scene:
                    errors.append(f"[{topic}] scene {scene.get('scene_id')} missing field {field}")
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        errors.append(f"[{topic}] scene plan unreadable: {exc}")

    try:
        pack = json.loads(row["image_prompt_pack_json"])
        if len(pack) != int(row["scene_count"]):
            errors.append(f"[{topic}] prompt pack {len(pack)} != scene_count {row['scene_count']}")
        for shot in pack:
            for field in (
                "shot_id",
                "positive_prompt",
                "negative_prompt",
                "camera",
                "lens",
                "lighting",
                "composition",
                "style",
                "render_notes",
            ):
                if field not in shot:
                    errors.append(f"[{topic}] prompt pack missing field {field}")
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        errors.append(f"[{topic}] prompt pack unreadable: {exc}")

    for col, min_len in (("title_variations_json", 5), ("hashtags", 3), ("seo_keywords_json", 5)):
        try:
            value = json.loads(row.get(col, "[]"))
            if len(value) < min_len:
                errors.append(f"[{topic}] {col} has {len(value)} items (min {min_len})")
        except json.JSONDecodeError:
            pass

    for col in ("fact_check_notes", "references_json"):
        try:
            value = json.loads(row.get(col, "[]"))
            if not value:
                errors.append(f"[{topic}] {col} is empty")
        except json.JSONDecodeError:
            pass

    try:
        thumb = json.loads(row["thumbnail_visual_spec"])
        for field in (
            "concept",
            "subject",
            "background",
            "angle",
            "lighting",
            "composition",
            "text",
            "elements",
            "style",
            "mood",
        ):
            if field not in thumb:
                errors.append(f"[{topic}] thumbnail spec missing {field}")
    except json.JSONDecodeError:
        pass

    if len(row["thumbnail_prompt"].split()) < 40:
        errors.append(f"[{topic}] thumbnail prompt too thin ({len(row['thumbnail_prompt'].split())} words)")
    if len(row["negative_prompt"].split()) < 10:
        errors.append(f"[{topic}] negative prompt too thin")
    if len(row["description"].split()) < 60:
        errors.append(f"[{topic}] description too thin ({len(row['description'].split())} words)")


def main() -> None:
    rows = load_rows()
    topics = [r["topic"] for r in rows]
    if len(topics) != len(set(topics)):
        dupes = {t for t in topics if topics.count(t) > 1}
        print(f"FAIL: duplicate topics: {sorted(dupes)}")
        raise SystemExit(1)

    errors: list[str] = []
    for row in rows:
        check_row(row, errors)

    durations = [len(r["script"].split()) / NARRATION_WPS for r in rows]
    avg_scenes = sum(int(r["scene_count"]) for r in rows) / len(rows)
    total_script_words = sum(len(r["script"].split()) for r in rows)

    if errors:
        print(f"FAIL: {len(errors)} problems across {len(rows)} rows")
        for err in errors[:50]:
            print("  - " + err)
        print(f"  ... and {max(0, len(errors) - 50)} more" if len(errors) > 50 else "")
        raise SystemExit(1)

    print(f"PASS: {len(rows)} rows fully validated")
    print(f"  narration range: {min(durations):.1f}s - {max(durations):.1f}s (target 20-35s)")
    print(f"  mean narration: {sum(durations) / len(durations):.1f}s")
    print(f"  mean scene count: {avg_scenes:.1f}")
    print(f"  total script words: {total_script_words}")
    print(f"  total CSV bytes: {(ROOT / CSV_PATH).stat().st_size:,}")


if __name__ == "__main__":
    main()
