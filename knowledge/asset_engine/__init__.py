"""PR1ME Studio - Asset Engine (Phase 12).

Every generated artifact becomes an indexed, reusable asset. The engine
answers the studio's eternal question - *reuse, improve, generate,
replace, or merge* - deterministically, from measured quality and
rule-based similarity alone. No LLM, no embeddings, no timestamps.
"""

from knowledge.asset_engine.asset_dependencies import AssetDependencies
from knowledge.asset_engine.asset_engine import AssetEngine
from knowledge.asset_engine.asset_index import AssetIndex
from knowledge.asset_engine.asset_matcher import best_match, content_twins, nearest, of_type, ranked
from knowledge.asset_engine.asset_models import (
    ASSET_ENGINE_VERSION,
    IMPROVE_SIMILARITY,
    MERGE_SIMILARITY,
    REPLACE_QUALITY_GAP,
    REUSE_QUALITY_THRESHOLD,
    REUSE_SCORE_QUALITY_WEIGHT,
    REUSE_SCORE_USAGE_SATURATION,
    REUSE_SCORE_USAGE_WEIGHT,
    REUSE_SIMILARITY,
    SIMILARITY_WEIGHTS,
    AssetQuery,
    AssetRecord,
    AssetStatus,
    AssetType,
    CreationEvent,
    DependencyEdge,
    ReuseDecision,
    ReuseEvent,
    SearchResult,
    SelectionDecision,
)
from knowledge.asset_engine.asset_quality import QualitySummary, quality_breakdown, quality_of, studio_quality
from knowledge.asset_engine.asset_registry import AssetRegistry, create_fingerprint, reuse_score_of
from knowledge.asset_engine.asset_reports import (
    build_dashboard_payload,
    build_database_payload,
    build_lineage_payload,
    build_report_payload,
    build_statistics_payload,
    export_reports,
)
from knowledge.asset_engine.asset_reuse import ReuseEngine
from knowledge.asset_engine.asset_search import parse_query, search
from knowledge.asset_engine.asset_selector import select
from knowledge.asset_engine.asset_similarity import similarity, similarity_to_query
from knowledge.asset_engine.asset_versioning import (
    add_version,
    chain_key,
    chain_members,
    lineage,
    newest_active,
)

__all__ = [
    "ASSET_ENGINE_VERSION",
    "AssetDependencies",
    "AssetEngine",
    "AssetIndex",
    "AssetQuery",
    "AssetRecord",
    "AssetRegistry",
    "AssetStatus",
    "AssetType",
    "CreationEvent",
    "DependencyEdge",
    "IMPROVE_SIMILARITY",
    "MERGE_SIMILARITY",
    "QualitySummary",
    "REPLACE_QUALITY_GAP",
    "REUSE_QUALITY_THRESHOLD",
    "REUSE_SCORE_QUALITY_WEIGHT",
    "REUSE_SCORE_USAGE_SATURATION",
    "REUSE_SCORE_USAGE_WEIGHT",
    "REUSE_SIMILARITY",
    "ReuseDecision",
    "ReuseEngine",
    "ReuseEvent",
    "SIMILARITY_WEIGHTS",
    "SearchResult",
    "SelectionDecision",
    "add_version",
    "best_match",
    "build_dashboard_payload",
    "build_database_payload",
    "build_lineage_payload",
    "build_report_payload",
    "build_statistics_payload",
    "chain_key",
    "chain_members",
    "content_twins",
    "create_fingerprint",
    "export_reports",
    "lineage",
    "nearest",
    "newest_active",
    "of_type",
    "parse_query",
    "quality_breakdown",
    "quality_of",
    "ranked",
    "reuse_score_of",
    "search",
    "select",
    "similarity",
    "similarity_to_query",
    "studio_quality",
]
