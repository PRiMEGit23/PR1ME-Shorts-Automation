"""Asset reports: the studio's five deterministic JSON exports (Phase 12).

Every export is a pure function of the current registry, reuse engine,
and dependency graph - no timestamps, sorted keys, so the same studio
state always yields byte-identical JSON. The five files:

- ``asset_database.json``   every record, one entry per asset
- ``asset_statistics.json`` counts and quality aggregates per bucket
- ``asset_report.json``     the reuse decisions and the rationale trail
- ``asset_lineage.json``    version chains and genealogy, per asset
- ``asset_dashboard.json``  one compact studio-wide overview
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.asset_engine.asset_dependencies import AssetDependencies
from knowledge.asset_engine.asset_models import (
    ASSET_ENGINE_VERSION,
)
from knowledge.asset_engine.asset_quality import (
    QualitySummary,
    quality_breakdown,
    studio_quality,
)
from knowledge.asset_engine.asset_registry import AssetRegistry
from knowledge.asset_engine.asset_reuse import ReuseEngine


def build_database_payload(registry: AssetRegistry) -> dict:
    """asset_database.json: every record as a plain dict."""
    return {
        "version": ASSET_ENGINE_VERSION,
        "asset_count": registry.count(),
        "assets": [record.model_dump() for record in registry.all()],
    }


def build_statistics_payload(registry: AssetRegistry) -> dict:
    """asset_statistics.json: counts and quality per bucket."""
    breakdown = quality_breakdown(registry)
    return {
        "version": ASSET_ENGINE_VERSION,
        "studio": {
            "total_assets": registry.count(),
            "active_assets": registry.count_active(),
            "per_type": {
                asset_type.value: len(
                    [r for r in registry.all() if r.asset_type.value == asset_type.value]
                )
                for asset_type in sorted(
                    {record.asset_type for record in registry.all()},
                    key=lambda asset_type: asset_type.value,
                )
            },
            "quality": _summary_dict(studio_quality(registry)),
        },
        "breakdown": {
            bucket: {
                key: _summary_dict(summary)
                for key, summary in sorted(groups.items())
            }
            for bucket, groups in breakdown.items()
        },
    }


def _summary_dict(summary: QualitySummary) -> dict:
    """The quality aggregate as a plain dict (dataclass, not pydantic)."""
    from dataclasses import asdict

    return asdict(summary)


def build_report_payload(registry: AssetRegistry, reuse: ReuseEngine) -> dict:
    """asset_report.json: reuse events and the studio's reuse verdict."""
    return {
        "version": ASSET_ENGINE_VERSION,
        "reuse_ratio": reuse.reuse_ratio(),
        "events": [event.model_dump() for event in reuse.events()],
        "verdict": {
            "reusable_candidates": reuse.reuseable_candidates(),
            "most_used": reuse.most_used(),
        },
    }


def build_lineage_payload(registry: AssetRegistry) -> dict:
    """asset_lineage.json: genealogy of every record, by chain."""
    chains: dict[str, list[dict]] = {}
    for record in registry.all():
        chains.setdefault(record.chain_id, []).append(
            {
                "asset_id": record.asset_id,
                "version": record.version,
                "status": record.status.value,
                "parent_asset_id": record.parent_asset_id,
                "superseded_by": record.superseded_by,
                "quality_score": record.quality_score,
            }
        )
    return {
        "version": ASSET_ENGINE_VERSION,
        "chains": {
            chain: sorted(members, key=lambda member: member["version"])
            for chain, members in sorted(chains.items())
        },
    }


def build_dashboard_payload(
    registry: AssetRegistry, reuse: ReuseEngine, dependencies: AssetDependencies
) -> dict:
    """asset_dashboard.json: one compact studio-wide overview."""
    records = registry.all()
    active = [record for record in records if record.status.value == "active"]
    quality = studio_quality(registry)
    total_reuse_score = (
        sum(record.reuse_score for record in active) / len(active)
        if active
        else 0.0
    )
    return {
        "version": ASSET_ENGINE_VERSION,
        "summary": {
            "total_assets": registry.count(),
            "active_assets": len(active),
            "chains": len({record.chain_id for record in records}),
            "dependency_edges": dependencies.edge_count(),
            "reuse_events": len(reuse.events()),
            "reuse_ratio": reuse.reuse_ratio(),
            "mean_reuse_score": round(total_reuse_score, 1),
            "mean_qa": quality.mean_qa,
            "pass_rate": quality.pass_rate,
        },
        "top_reused": reuse.most_used(limit=5),
        "root_assets": dependencies.roots()[:10],
    }


def export_reports(
    registry: AssetRegistry,
    reuse: ReuseEngine,
    dependencies: AssetDependencies,
    output_dir: Path,
) -> dict[str, Path]:
    """Write the five deterministic JSON exports; returns name -> path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "asset_database.json": build_database_payload(registry),
        "asset_statistics.json": build_statistics_payload(registry),
        "asset_report.json": build_report_payload(registry, reuse),
        "asset_lineage.json": build_lineage_payload(registry),
        "asset_dashboard.json": build_dashboard_payload(
            registry, reuse, dependencies
        ),
    }
    written: dict[str, Path] = {}
    for name, payload in payloads.items():
        target = output_dir / name
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        written[name] = target
    return written
