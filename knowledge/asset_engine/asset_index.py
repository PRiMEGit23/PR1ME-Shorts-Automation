"""Asset index: deterministic lookup structures over the registry (Phase 12).

The index mirrors the registry with sorted buckets - by type, by each tag
(visual and semantic), by topic, by engineering category, by model - so
every lookup the search, matcher, and selector need is a constant-time
bucket scan over already-sorted ids. The index is read-only: it is
rebuilt from the registry with ``AssetIndex(registry)`` and never gets
out of sync, because records are immutable.
"""

from __future__ import annotations

from collections import defaultdict

from knowledge.asset_engine.asset_models import AssetRecord, AssetType
from knowledge.asset_engine.asset_registry import AssetRegistry

#: Which record fields the index buckets by.
_BUCKET_FIELDS: tuple[tuple[str, str], ...] = (
    ("topic", "source_topic"),
    ("engineering_category", "engineering_category"),
    ("educational_category", "educational_category"),
    ("model", "model_used"),
    ("visual_tag", "visual_tags"),
    ("semantic_tag", "semantic_tags"),
    ("object", "objects"),
    ("material", "materials"),
    ("process", "processes"),
)


class AssetIndex:
    """Read-only buckets over one registry (sorted ids everywhere)."""

    def __init__(self, registry: AssetRegistry) -> None:
        self._registry = registry
        self._by_type: dict[AssetType, list[str]] = defaultdict(list)
        self._buckets: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for record in registry.all():
            self._by_type[record.asset_type].append(record.asset_id)
            for bucket, attribute in _BUCKET_FIELDS:
                values = getattr(record, attribute)
                if isinstance(values, str):
                    values = [values]
                for value in values:
                    if value:
                        self._buckets[bucket][value].append(record.asset_id)

    # ----------------------------------------------------------------- read --

    def by_type(self, asset_type: AssetType) -> tuple[str, ...]:
        """Every id of one type, sorted (the bucket is built sorted)."""
        return tuple(self._by_type[asset_type])

    def by_bucket(self, bucket: str, value: str) -> tuple[str, ...]:
        """Every id holding one bucket value, sorted."""
        return tuple(self._buckets[bucket][value])

    def bucket_values(self, bucket: str) -> tuple[str, ...]:
        """All distinct values of one bucket, sorted."""
        return tuple(sorted(self._buckets[bucket]))

    def count(self) -> int:
        """The number of indexed records (mirrors the registry)."""
        return self._registry.count()

    def registry(self) -> AssetRegistry:
        """The registry this index was built from."""
        return self._registry

    def covers(self, record: AssetRecord) -> bool:
        """Whether this index still mirrors the registry (consistency check)."""
        return record.asset_id in self._by_type[record.asset_type]
