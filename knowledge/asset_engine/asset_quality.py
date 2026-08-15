"""Asset quality: measured performance per asset and per family (Phase 12).

Quality is never guessed: every asset carries its winner QA score, its
retention prediction, and its optimization load at creation. This module
aggregates those numbers per type, per model, per topic, per engineering
category, and across the whole studio - the numbers behind the
statistics and dashboard exports.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.asset_engine.asset_models import AssetRecord
from knowledge.asset_engine.asset_registry import AssetRegistry

#: How the quality summary buckets records.
_BUCKET_ATTRIBUTE: dict[str, str] = {
    "type": "asset_type",
    "model": "model_used",
    "topic": "source_topic",
    "engineering_category": "engineering_category",
}


@dataclass(frozen=True)
class QualitySummary:
    """One deterministic quality aggregate over a set of records."""

    count: int
    mean_qa: float
    min_qa: float
    max_qa: float
    mean_retention: float
    mean_optimization: float
    pass_rate: float = 0.0


def quality_of(records: tuple[AssetRecord, ...]) -> QualitySummary:
    """The quality aggregate of one set of records (empty set -> zeros)."""
    if not records:
        return QualitySummary(
            count=0, mean_qa=0.0, min_qa=0.0, max_qa=0.0,
            mean_retention=0.0, mean_optimization=0.0,
        )
    qa = [record.quality_score for record in records]
    retention = [record.retention_prediction for record in records]
    optimization = [record.optimization_count for record in records]
    passed = sum(1 for record in records if record.quality_score >= 75.0)
    return QualitySummary(
        count=len(records),
        mean_qa=round(sum(qa) / len(qa), 1),
        min_qa=round(min(qa), 1),
        max_qa=round(max(qa), 1),
        mean_retention=round(sum(retention) / len(retention), 1),
        mean_optimization=round(sum(optimization) / len(optimization), 2),
        pass_rate=round(passed / len(records), 3),
    )


def quality_breakdown(registry: AssetRegistry) -> dict[str, dict[str, QualitySummary]]:
    """Per-bucket quality summaries (by type, model, topic, category)."""
    breakdown: dict[str, dict[str, QualitySummary]] = {}
    for bucket, attribute in _BUCKET_ATTRIBUTE.items():
        groups: dict[str, list[AssetRecord]] = {}
        for record in registry.all():
            value = getattr(record, attribute)
            key = value.value if hasattr(value, "value") else str(value)
            groups.setdefault(key, []).append(record)
        breakdown[bucket] = {
            key: quality_of(tuple(records))
            for key, records in sorted(groups.items())
        }
    return breakdown


def studio_quality(registry: AssetRegistry) -> QualitySummary:
    """The whole studio's quality summary (active records only)."""
    active = tuple(
        record for record in registry.all() if record.status.value == "active"
    )
    return quality_of(active)
