"""Asset selector: the studio's reuse / improve / generate decision (Phase 12).

For every candidate request the selector decides - deterministically,
from the matched records alone:

- ``REUSE``: a similar-enough asset with quality above the reuse bar
- ``IMPROVE``: a similar asset below the quality bar (regenerate it)
- ``GENERATE``: no similar asset exists
- ``REPLACE``: a newer version of the same chain is meaningfully better
- ``MERGE``: two records are duplicates of one another

Reuse policy: existing asset quality > ``REUSE_QUALITY_THRESHOLD`` wins;
otherwise the studio generates (or improves) instead of reusing a weak
asset. Every decision carries the evidence and the exact rationale.
"""

from __future__ import annotations

from knowledge.asset_engine.asset_index import AssetIndex
from knowledge.asset_engine.asset_matcher import best_match, nearest
from knowledge.asset_engine.asset_models import (
    IMPROVE_SIMILARITY,
    MERGE_SIMILARITY,
    REPLACE_QUALITY_GAP,
    REUSE_QUALITY_THRESHOLD,
    REUSE_SIMILARITY,
    AssetQuery,
    AssetRecord,
    ReuseDecision,
    SelectionDecision,
)


def select(
    index: AssetIndex,
    query: AssetQuery,
    *,
    candidate_key: str,
    candidate_quality: float | None = None,
    existing_asset_id: str | None = None,
) -> SelectionDecision:
    """Decide what the studio should do for one candidate request.

    ``existing_asset_id`` is the asset currently serving the candidate
    (e.g. the scene's last image): when a meaningfully better version of
    it exists, the studio decides REPLACE. Without it, REPLACE cannot
    trigger - a candidate with nothing to replace never replaces.
    """
    best = best_match(index, query, min_similarity=0.0)
    if best is None:
        return SelectionDecision(
            decision=ReuseDecision.GENERATE,
            candidate_key=candidate_key,
            similarity=0.0,
            candidate_quality=candidate_quality,
            rationale=(
                f"no matching asset in the studio for {candidate_key!r}; "
                "generate new"
            ),
        )

    if existing_asset_id is not None:
        replacement = _better_replacement(index, existing_asset_id)
        if replacement is not None:
            return SelectionDecision(
                decision=ReuseDecision.REPLACE,
                candidate_key=candidate_key,
                chosen_asset_id=replacement.asset_id,
                similarity=_query_similarity(index, replacement, query),
                candidate_quality=candidate_quality,
                rationale=(
                    f"{existing_asset_id} is superseded by "
                    f"{replacement.asset_id} (quality "
                    f"{index.registry().get(existing_asset_id).quality_score:.1f} "
                    f"-> {replacement.quality_score:.1f}); replace"
                ),
                evidence=(existing_asset_id, replacement.asset_id),
            )

    matched = nearest(
        index,
        best,
        limit=1,
        min_similarity=MERGE_SIMILARITY,
    )

    if matched:
        twin = index.registry().get(matched[0].asset_id)
        return SelectionDecision(
            decision=ReuseDecision.MERGE,
            candidate_key=candidate_key,
            chosen_asset_id=best.asset_id,
            similarity=matched[0].similarity,
            candidate_quality=candidate_quality,
            rationale=(
                f"{best.asset_id} and {twin.asset_id} are duplicates "
                f"(similarity {matched[0].similarity:.2f}); merge"
            ),
            evidence=(best.asset_id, twin.asset_id),
        )

    if (
        best.quality_score >= REUSE_QUALITY_THRESHOLD
        and _query_similarity(index, best, query) >= REUSE_SIMILARITY
    ):
        return SelectionDecision(
            decision=ReuseDecision.REUSE,
            candidate_key=candidate_key,
            chosen_asset_id=best.asset_id,
            similarity=_query_similarity(index, best, query),
            candidate_quality=candidate_quality,
            rationale=(
                f"reuse {best.asset_id}: quality {best.quality_score:.1f} "
                f"above the {REUSE_QUALITY_THRESHOLD:.0f} bar and "
                f"similarity {_query_similarity(index, best, query):.2f}"
            ),
            evidence=(best.asset_id,),
        )

    if (
        _query_similarity(index, best, query) >= IMPROVE_SIMILARITY
        and best.quality_score < REUSE_QUALITY_THRESHOLD
    ):
        return SelectionDecision(
            decision=ReuseDecision.IMPROVE,
            candidate_key=candidate_key,
            chosen_asset_id=best.asset_id,
            similarity=_query_similarity(index, best, query),
            candidate_quality=candidate_quality,
            rationale=(
                f"improve {best.asset_id}: similar but only "
                f"{best.quality_score:.1f} quality (bar "
                f"{REUSE_QUALITY_THRESHOLD:.0f}); regenerate"
            ),
            evidence=(best.asset_id,),
        )

    return SelectionDecision(
        decision=ReuseDecision.GENERATE,
        candidate_key=candidate_key,
        chosen_asset_id=best.asset_id,
        similarity=_query_similarity(index, best, query),
        candidate_quality=candidate_quality,
        rationale=(
            f"no asset clears the reuse bar for {candidate_key!r} "
            f"(closest {best.asset_id} at "
            f"{_query_similarity(index, best, query):.2f}); generate new"
        ),
        evidence=(best.asset_id,),
    )


def _better_replacement(index: AssetIndex, existing_asset_id: str) -> AssetRecord | None:
    """The newest active version of a chain when it clearly beats the existing."""
    from knowledge.asset_engine.asset_versioning import newest_active

    existing = index.registry().try_get(existing_asset_id)
    if existing is None:
        return None
    newest = newest_active(index.registry(), existing.asset_id)
    if newest is None or newest.asset_id == existing.asset_id:
        return None
    if newest.quality_score - existing.quality_score >= REPLACE_QUALITY_GAP:
        return newest
    return None


def _query_similarity(index: AssetIndex, record: AssetRecord, query: AssetQuery) -> float:
    from knowledge.asset_engine.asset_similarity import similarity_to_query

    return similarity_to_query(record, query)
