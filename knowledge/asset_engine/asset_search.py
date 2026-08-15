"""Asset search: rule-based queries over the asset index (Phase 12).

A plain-text query like ``"all gyroid cross-sections"`` is parsed into an
``AssetQuery`` by deterministic rules - known type synonyms, engineering
domains, and leftover words tried as topic / material / object terms -
then matched against the index with ``similarity_to_query``. Results are
sorted by ``(-similarity, asset_id)``: the same query always returns the
same ordered list.
"""

from __future__ import annotations

import re

from knowledge.asset_engine.asset_index import AssetIndex
from knowledge.asset_engine.asset_models import (
    TYPE_SYNONYMS,
    AssetQuery,
    AssetRecord,
    AssetType,
    SearchResult,
)
from knowledge.asset_engine.asset_similarity import similarity_to_query
from knowledge.visual_architecture import EngineeringDomain

#: Words stripped before role assignment.
_STOP_WORDS = frozenset({"all", "the", "a", "an", "of", "for", "with", "and", "in"})

#: Engineering domains as query tokens (e.g. "fdm", "cnc machining").
#: Keys are lowercased for matching; values keep the canonical case.
_ENGINEERING_TERMS: dict[str, str] = {
    domain.value.lower(): domain.value for domain in EngineeringDomain
}


def parse_query(text: str) -> AssetQuery:
    """Parse one plain-text query into a structured AssetQuery."""
    normalized = text.lower().strip()
    words = [
        word
        for word in re.split(r"[^a-z0-9\-]+", normalized)
        if word and word not in _STOP_WORDS
    ]
    asset_type = _detect_type(normalized, words)
    engineering_category = _detect_domain(normalized)
    remaining = [
        word
        for word in words
        if not _is_type_word(word)
        and not _is_domain_word(word)
    ]
    topic = " ".join(remaining) if remaining else ""
    return AssetQuery(
        topic=topic,
        engineering_category=engineering_category,
        asset_type=asset_type,
        objects=tuple(remaining),
    )


def search(
    index: AssetIndex,
    query: AssetQuery,
    *,
    limit: int = 20,
) -> tuple[SearchResult, ...]:
    """All matching assets, sorted by (-similarity, asset_id), capped."""
    records = index.registry().all()
    if query.asset_type is not None:
        records = tuple(
            record for record in records if record.asset_type is query.asset_type
        )
    results: list[SearchResult] = []
    for record in records:
        if record.status.value != "active":
            continue
        matched = _matched_terms(record, query)
        score = similarity_to_query(record, query)
        if not query.is_empty() and score == 0.0:
            continue
        results.append(
            SearchResult(
                asset_id=record.asset_id,
                similarity=score,
                matched_terms=tuple(matched),
            )
        )
    return tuple(
        sorted(results, key=lambda result: (-result.similarity, result.asset_id))[
            :limit
        ]
    )


def _detect_type(normalized: str, words: list[str]) -> AssetType | None:
    """The first asset type whose synonyms appear in the query."""
    for asset_type in AssetType:
        for synonym in TYPE_SYNONYMS[asset_type.value]:
            if synonym in normalized or synonym in words:
                return asset_type
    return None


def _detect_domain(normalized: str) -> str:
    """The engineering domain named in the query (canonical case), or ''."""
    for term in _ENGINEERING_TERMS:
        if term in normalized:
            return _ENGINEERING_TERMS[term]
    return ""


def _is_type_word(word: str) -> bool:
    """Whether a token is a type synonym, tolerating plural ``s``."""
    return any(
        word == synonym or word.rstrip("s") == synonym
        for synonyms in TYPE_SYNONYMS.values()
        for synonym in synonyms
    )


def _is_domain_word(word: str) -> bool:
    return word in _ENGINEERING_TERMS


def _matched_terms(record: AssetRecord, query: AssetQuery) -> list[str]:
    """The query words the record's fields contain (for the result)."""
    matched: list[str] = []
    haystacks = [
        record.source_topic,
        record.engineering_category,
        record.educational_category,
        record.camera,
        record.lighting,
        " ".join(record.objects),
        " ".join(record.materials),
        " ".join(record.processes),
        " ".join(record.visual_tags),
        " ".join(record.semantic_tags),
    ]
    tokens = _query_tokens(query)
    for token in tokens:
        if any(token in haystack.lower() for haystack in haystacks):
            matched.append(token)
    return sorted(set(matched))


def _query_tokens(query: AssetQuery) -> list[str]:
    tokens = [query.topic] if query.topic else []
    tokens.extend(query.objects)
    tokens.extend(query.materials)
    if query.engineering_category:
        tokens.append(query.engineering_category)
    if query.camera:
        tokens.append(query.camera)
    return [token for token in tokens if token]
