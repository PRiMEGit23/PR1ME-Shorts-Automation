"""Asset matcher: the deterministic candidate lookup (Phase 12).

Given a structured request (an ``AssetQuery`` or a candidate record),
the matcher ranks active assets by rule-based similarity and returns the
best candidates above a threshold. It is the single lookup path for the
selector and for every consumer (render loop, workflow builder, render
optimizer, publisher) - no duplicated lookup logic.
"""

from __future__ import annotations

from knowledge.asset_engine.asset_index import AssetIndex
from knowledge.asset_engine.asset_models import (
    AssetQuery,
    AssetRecord,
    AssetType,
    SearchResult,
)
from knowledge.asset_engine.asset_similarity import (
    similarity,
    similarity_to_query,
)


def best_match(
    index: AssetIndex,
    query: AssetQuery,
    *,
    min_similarity: float = 0.0,
) -> AssetRecord | None:
    """The single best active asset for a query, or None below the bar."""
    results = ranked(index, query, limit=1)
    if not results:
        return None
    result = results[0]
    if result.similarity < min_similarity:
        return None
    return index.registry().get(result.asset_id)


def ranked(
    index: AssetIndex,
    query: AssetQuery,
    *,
    limit: int = 10,
    min_similarity: float = 0.0,
) -> tuple[SearchResult, ...]:
    """Active assets for a query, sorted by (-similarity, asset_id)."""
    records = index.registry().all()
    if query.asset_type is not None:
        records = tuple(
            record for record in records if record.asset_type is query.asset_type
        )
    results: list[SearchResult] = []
    for record in records:
        if record.status.value != "active":
            continue
        score = similarity_to_query(record, query)
        if score < min_similarity:
            continue
        results.append(SearchResult(asset_id=record.asset_id, similarity=score))
    return tuple(
        sorted(results, key=lambda result: (-result.similarity, result.asset_id))[:limit]
    )


def nearest(
    index: AssetIndex,
    record: AssetRecord,
    *,
    limit: int = 5,
    min_similarity: float = 0.0,
) -> tuple[SearchResult, ...]:
    """The assets most similar to one record (duplicate detection input)."""
    results: list[SearchResult] = []
    for other in index.registry().all():
        if other.asset_id == record.asset_id:
            continue
        score = similarity(record, other)
        if score < min_similarity:
            continue
        results.append(SearchResult(asset_id=other.asset_id, similarity=score))
    return tuple(
        sorted(results, key=lambda result: (-result.similarity, result.asset_id))[:limit]
    )


def content_twins(
    index: AssetIndex, record: AssetRecord
) -> tuple[AssetRecord, ...]:
    """Every *other* asset with identical content (same fingerprint)."""
    twins = [
        other
        for other in index.registry().all()
        if other.asset_id != record.asset_id
        and other.fingerprint == record.fingerprint
    ]
    return tuple(sorted(twins, key=lambda twin: twin.asset_id))


def of_type(index: AssetIndex, asset_type: AssetType) -> tuple[AssetRecord, ...]:
    """Every active asset of one type (the index bucket, deterministic)."""
    return tuple(
        record
        for record in (index.registry().get(asset_id) for asset_id in index.by_type(asset_type))
        if record.status.value == "active"
    )
