"""Asset similarity: rule-based semantic similarity, no embeddings (Phase 12).

Two assets are similar when their semantic identity overlaps: topic,
engineering category, objects, materials, processes, camera, lighting,
model, and tags. Every field has a fixed weight (in ``asset_models``);
each field's contribution is the Jaccard overlap for tuple fields and an
exact match for string fields. The score is a pure function of the two
records - symmetric, bounded to [0, 1], and identical every time it is
computed.
"""

from __future__ import annotations

from knowledge.asset_engine.asset_models import (
    SIMILARITY_WEIGHTS,
    AssetQuery,
    AssetRecord,
)

#: Which record field each weight applies to.
_FIELD_ATTRIBUTE: dict[str, str] = {
    "topic": "source_topic",
    "engineering_category": "engineering_category",
    "objects": "objects",
    "materials": "materials",
    "processes": "processes",
    "camera": "camera",
    "lighting": "lighting",
    "model": "model_used",
    "visual_tags": "visual_tags",
    "semantic_tags": "semantic_tags",
}


def similarity(a: AssetRecord, b: AssetRecord) -> float:
    """The rule-based similarity of two assets (symmetric, deterministic)."""
    if a.fingerprint == b.fingerprint:
        return 1.0
    score = 0.0
    for weight_name, weight in SIMILARITY_WEIGHTS.items():
        attribute = _FIELD_ATTRIBUTE[weight_name]
        left = getattr(a, attribute)
        right = getattr(b, attribute)
        score += weight * _overlap(left, right)
    return round(min(1.0, score), 4)


def similarity_to_query(record: AssetRecord, query: AssetQuery) -> float:
    """How well one asset satisfies one query (query fields only)."""
    score = 0.0
    total_weight = 0.0
    for weight_name, weight in SIMILARITY_WEIGHTS.items():
        attribute = _FIELD_ATTRIBUTE[weight_name]
        query_value = getattr(query, weight_name if weight_name != "model" else "model")
        if not _is_empty(query_value):
            total_weight += weight
            record_value = getattr(record, attribute)
            if weight_name == "topic":
                score += weight * _text_match(record_value, query_value)
            elif isinstance(query_value, str):
                score += weight * (1.0 if record_value == query_value else 0.0)
            else:
                score += weight * _word_jaccard(record_value, query_value)
    if total_weight == 0.0:
        return 1.0
    return round(min(1.0, score / total_weight), 4)


def _overlap(
    left: str | tuple[str, ...], right: str | tuple[str, ...]
) -> float:
    """Word-level Jaccard for tuple fields, exact match for strings.

    Phrase fields (e.g. objects like ``"planetary gear"``) match query
    words like ``"planetary"``: both sides are split into words and
    compared as sets. Deterministic and forgiving of plural/word order.
    """
    if isinstance(left, tuple) and isinstance(right, tuple):
        return _word_jaccard(left, right)
    if isinstance(left, str) and isinstance(right, str):
        return 1.0 if left and left.lower() == right.lower() else 0.0
    return 0.0


def _word_jaccard(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_words = _word_set(left)
    right_words = _word_set(right)
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / len(left_words | right_words)


def _word_set(values: tuple[str, ...]) -> set[str]:
    words: set[str] = set()
    for value in values:
        words.update(_words_of(value))
    return words


def _words_of(value: str) -> list[str]:
    return [word for word in value.lower().split() if word]


def _text_match(record_value: str, query_value: str) -> float:
    """Topic match: shared words over all words of both topics."""
    left = _words_of(record_value)
    right = _words_of(query_value)
    if not left or not right:
        return 0.0
    return len(set(left) & set(right)) / len(set(left) | set(right))


def _is_empty(value: str | tuple[str, ...]) -> bool:
    if isinstance(value, tuple):
        return not value
    return not value
