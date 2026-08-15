"""Knowledge base tests: every curated topic composes into a valid, self-consistent row."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_knowledge_csv import compose_row, load_curated  # noqa: E402
from knowledge.schema import COLUMNS, estimated_duration, scene_duration_sum  # noqa: E402
from knowledge.taxonomy import TAXONOMY  # noqa: E402

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

ALL_TOPICS = [e[0] for entries in TAXONOMY.values() for e in entries]


def test_taxonomy_shape() -> None:
    assert len(ALL_TOPICS) == 400
    assert len(ALL_TOPICS) == len(set(ALL_TOPICS))
    assert all(len(t) <= 60 for t in ALL_TOPICS)


def test_curated_topics_exist_in_taxonomy() -> None:
    curated = load_curated()
    unknown = [t for t in curated if t not in ALL_TOPICS]
    assert not unknown, f"topics missing from taxonomy: {unknown}"


def test_every_curated_row_is_valid() -> None:
    curated = load_curated()
    assert curated, "no curated topics loaded"
    taxonomy_by_topic = {e[0]: e for entries in TAXONOMY.values() for e in entries}

    for topic, data in curated.items():
        row = compose_row(taxonomy_by_topic[topic], data)
        assert set(row.keys()) == set(COLUMNS)

        for col in COLUMNS:
            assert row[col].strip(), f"[{topic}] empty column {col}"

        for col in JSON_COLUMNS:
            json.loads(row[col])

        duration = estimated_duration(row["script"])
        assert 20.0 <= duration <= 35.0, f"[{topic}] narration {duration:.1f}s out of budget"

        scenes = json.loads(row["scene_plan_json"])
        assert len(scenes) == int(row["scene_count"]), f"[{topic}] scene_count mismatch"
        assert len(scenes) >= 4, f"[{topic}] too few scenes"
        total = scene_duration_sum(scenes)
        assert abs(total - duration) / duration <= 0.3, f"[{topic}] scene/narration drift"

        pack = json.loads(row["image_prompt_pack_json"])
        assert len(pack) == len(scenes), f"[{topic}] prompt pack mismatch"

        for col, min_items in (("title_variations_json", 5), ("hashtags", 3), ("seo_keywords_json", 5)):
            assert len(json.loads(row[col])) >= min_items, f"[{topic}] {col} too short"
