"""Asset registry: the studio's deterministic asset store (Phase 12).

One content-addressed store: identical content always fingerprints
identically, so registering the same artifact twice returns the same
asset id instead of duplicating. Registration is the only write path;
records are immutable, and every read (by id, type, fingerprint) is a
pure lookup. No randomness, no timestamps.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from knowledge.asset_engine.asset_models import (
    ASSET_ENGINE_VERSION,
    REUSE_SCORE_QUALITY_WEIGHT,
    REUSE_SCORE_USAGE_SATURATION,
    REUSE_SCORE_USAGE_WEIGHT,
    AssetRecord,
    AssetStatus,
    AssetType,
    CreationEvent,
)


def create_fingerprint(content: str) -> str:
    """The canonical sha256 of one artifact's content signature."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class AssetRegistry:
    """The in-memory studio store: immutable records, deterministic order.

    ``add`` is idempotent per (type, fingerprint): the second registration
    of the same content returns the first asset's id (a record in the
    creation history is appended only for the caller's audit trail).
    """

    def __init__(self) -> None:
        self._assets: dict[str, AssetRecord] = {}
        self._by_fingerprint: dict[str, list[str]] = {}
        self._version = ASSET_ENGINE_VERSION

    # ---------------------------------------------------------------- write --

    def add(
        self, *, asset_type: AssetType, fingerprint: str, **fields: Any
    ) -> AssetRecord:
        """Register one artifact; returns the (possibly existing) record."""
        existing = self.find_by_fingerprint(asset_type, fingerprint)
        if existing is not None:
            return existing
        asset_id = f"{asset_type.value}-{fingerprint[:12]}"
        record = AssetRecord(
            asset_id=asset_id,
            asset_type=asset_type,
            fingerprint=fingerprint,
            **fields,
        )
        self._assets[asset_id] = record
        self._by_fingerprint.setdefault(f"{asset_type.value}:{fingerprint}", []).append(
            asset_id
        )
        return record

    # ----------------------------------------------------------------- read --

    def get(self, asset_id: str) -> AssetRecord:
        """The record for an id; raises KeyError when unknown."""
        if asset_id not in self._assets:
            raise KeyError(f"no asset under {asset_id!r}")
        return self._assets[asset_id]

    def try_get(self, asset_id: str) -> AssetRecord | None:
        """The record for an id, or None."""
        return self._assets.get(asset_id)

    def find_by_fingerprint(
        self, asset_type: AssetType, fingerprint: str
    ) -> AssetRecord | None:
        """The first record with this type and content hash, or None."""
        ids = self._by_fingerprint.get(f"{asset_type.value}:{fingerprint}", ())
        for asset_id in ids:
            return self._assets[asset_id]
        return None

    def by_type(self, asset_type: AssetType) -> tuple[AssetRecord, ...]:
        """Every record of one type, sorted by id (deterministic)."""
        return tuple(
            record
            for record in self.all()
            if record.asset_type is asset_type
        )

    def all(self) -> tuple[AssetRecord, ...]:
        """Every record, sorted by id (deterministic)."""
        return tuple(self._assets[asset_id] for asset_id in sorted(self._assets))

    def count(self) -> int:
        """How many distinct records are stored."""
        return len(self._assets)

    def ids(self) -> tuple[str, ...]:
        """Every stored id, sorted."""
        return tuple(sorted(self._assets))

    # ------------------------------------------------------------- history --

    def append_event(
        self,
        asset_id: str,
        *,
        action: Literal["created", "improved", "reused", "merged"],
        reason: str,
        run_id: str = "",
        scene_id: str = "",
        quality_score: float | None = None,
    ) -> AssetRecord:
        """Append one deterministic creation-history event (immutable copy).

        The sequence number is the length of the existing history, so the
        same sequence of actions always yields the same history.
        """
        record = self.get(asset_id)
        events = list(record.creation_history)
        events.append(
            CreationEvent(
                sequence=len(events),
                action=action,
                reason=reason,
                run_id=run_id,
                scene_id=scene_id,
            )
        )
        fields = record.model_dump()
        fields["creation_history"] = tuple(events)
        if quality_score is not None:
            fields["quality_score"] = quality_score
        updated = AssetRecord.model_validate(fields)
        self._assets[asset_id] = updated
        return updated

    def update(self, record: AssetRecord) -> AssetRecord:
        """Swap one record for its updated copy (same id, same fingerprint).

        The only mutation path for status / usage / history: the record is
        immutable, so updates are replacement, never in-place edits.
        """
        existing = self.get(record.asset_id)
        if record.fingerprint != existing.fingerprint:
            raise ValueError(
                f"update of {record.asset_id} changed the fingerprint; "
                "create a new asset instead"
            )
        self._assets[record.asset_id] = record
        return record

    def record_reuse(
        self,
        asset_id: str,
        *,
        topic: str,
        consumer: str,
        reason: str,
    ) -> AssetRecord:
        """Record one reuse: usage count up, topic tracked, score recomputed."""
        record = self.get(asset_id)
        topics = record.topics_using
        topics = tuple(sorted(set(topics) | {topic}))
        usage = record.usage_count + 1
        fields = record.model_dump()
        fields["usage_count"] = usage
        fields["topics_using"] = topics
        fields["reuse_score"] = round(reuse_score_of(usage, record.quality_score), 1)
        fields["creation_history"] = tuple(
            list(record.creation_history)
            + [
                CreationEvent(
                    sequence=len(record.creation_history),
                    action="reused",
                    reason=f"{consumer}: {reason}",
                )
            ]
        )
        updated = AssetRecord.model_validate(fields)
        self._assets[asset_id] = updated
        return updated

    def count_active(self) -> int:
        """How many records are active (not obsolete or merged)."""
        return sum(1 for record in self.all() if record.status is AssetStatus.ACTIVE)


def reuse_score_of(usage_count: int, quality_score: float) -> float:
    """The deterministic reuse score: quality share + saturated usage share."""
    usage_share = min(usage_count, REUSE_SCORE_USAGE_SATURATION) / 5 * 100.0
    return min(
        100.0,
        REUSE_SCORE_QUALITY_WEIGHT * quality_score
        + REUSE_SCORE_USAGE_WEIGHT * usage_share,
    )
