"""Asset Engine facade: the studio's single asset front door (Phase 12).

The facade owns the registry, index, reuse engine, and dependency graph,
and exposes the consumer contracts the rest of the studio relies on:
workflow builder, render loop, render optimizer, and publisher all get
their asset decisions here - no duplicated lookup logic anywhere else.
Every method is deterministic: the same studio state produces the same
answers and the same exports.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.asset_engine.asset_dependencies import AssetDependencies
from knowledge.asset_engine.asset_index import AssetIndex
from knowledge.asset_engine.asset_matcher import best_match
from knowledge.asset_engine.asset_models import (
    REUSE_QUALITY_THRESHOLD,
    AssetQuery,
    AssetRecord,
    AssetType,
    CreationEvent,
    DependencyEdge,
    ReuseDecision,
    ReuseEvent,
    SearchResult,
    SelectionDecision,
)
from knowledge.asset_engine.asset_registry import AssetRegistry, reuse_score_of
from knowledge.asset_engine.asset_reports import export_reports
from knowledge.asset_engine.asset_reuse import ReuseEngine
from knowledge.asset_engine.asset_search import parse_query
from knowledge.asset_engine.asset_selector import select
from knowledge.asset_engine.asset_versioning import add_version


class AssetEngine:
    """The studio's asset store, lookup, and decision facade."""

    def __init__(self) -> None:
        self._registry = AssetRegistry()
        self._reuse = ReuseEngine(self._registry)
        self._dependencies = AssetDependencies(self._registry)
        self._index: AssetIndex | None = None
        self._dirty = True

    # ------------------------------------------------------------ registry --

    def registry(self) -> AssetRegistry:
        return self._registry

    def reuse_engine(self) -> ReuseEngine:
        return self._reuse

    def dependencies(self) -> AssetDependencies:
        return self._dependencies

    def index(self) -> AssetIndex:
        """The read-only index, rebuilt lazily when the registry changed."""
        if self._dirty or self._index is None:
            self._index = AssetIndex(self._registry)
            self._dirty = False
        return self._index

    # -------------------------------------------------------------- ingest --

    def register(
        self,
        *,
        asset_type: AssetType,
        fingerprint: str,
        source_topic: str,
        quality_score: float,
        educational_category: str = "",
        engineering_category: str = "",
        objects: tuple[str, ...] = (),
        materials: tuple[str, ...] = (),
        processes: tuple[str, ...] = (),
        camera: str = "",
        lighting: str = "",
        model_used: str = "",
        workflow_version: str = "",
        retention_prediction: float = 0.0,
        optimization_count: int = 0,
        visual_tags: tuple[str, ...] = (),
        semantic_tags: tuple[str, ...] = (),
        run_id: str = "",
        scene_id: str = "",
        reason: str = "created",
    ) -> AssetRecord:
        """Index one generated artifact; returns its record.

        Content-addressed: registering identical content again returns
        the existing record (a ``merged`` history event is appended),
        and new records are linked into their version chain.
        """
        existing = self._registry.find_by_fingerprint(asset_type, fingerprint)
        if existing is not None:
            return self._registry.append_event(
                existing.asset_id,
                action="merged",
                reason=reason,
                run_id=run_id,
                scene_id=scene_id,
            )
        record = self._registry.add(
            asset_type=asset_type,
            fingerprint=fingerprint,
            source_topic=source_topic,
            educational_category=educational_category,
            engineering_category=engineering_category,
            objects=objects,
            materials=materials,
            processes=processes,
            camera=camera,
            lighting=lighting,
            model_used=model_used,
            workflow_version=workflow_version,
            quality_score=quality_score,
            reuse_score=reuse_score_of(0, quality_score),
            retention_prediction=retention_prediction,
            optimization_count=optimization_count,
            visual_tags=visual_tags,
            semantic_tags=semantic_tags,
            usage_count=0,
            version=1,
            chain_id="pending",
            creation_history=(
                CreationEvent(
                    sequence=0,
                    action="created",
                    reason=reason,
                    run_id=run_id,
                    scene_id=scene_id,
                ),
            ),
        )
        versioned = add_version(self._registry, record)
        self._registry.update(versioned)
        self._dirty = True
        return versioned

    def add_dependency(
        self,
        *,
        dependent: str,
        dependency: str,
        kind: str = "uses",
        reason: str = "",
    ) -> DependencyEdge:
        """Declare one validated dependency edge."""
        return self._dependencies.add(
            dependent=dependent, dependency=dependency, kind=kind, reason=reason
        )

    # ------------------------------------------------------------- requests --

    def search(self, query_text: str, *, limit: int = 20) -> tuple[SearchResult, ...]:
        """Rule-based search: parse one plain-text query and rank hits."""
        from knowledge.asset_engine.asset_search import search

        return search(self.index(), parse_query(query_text), limit=limit)

    def select(
        self,
        query: AssetQuery,
        *,
        candidate_key: str,
        candidate_quality: float | None = None,
        existing_asset_id: str | None = None,
    ) -> SelectionDecision:
        """The reuse / improve / generate / replace / merge decision."""
        return select(
            self.index(),
            query,
            candidate_key=candidate_key,
            candidate_quality=candidate_quality,
            existing_asset_id=existing_asset_id,
        )

    def request(
        self,
        query_text: str,
        *,
        consumer: str,
        topic: str,
        candidate_key: str,
        candidate_quality: float | None = None,
    ) -> tuple[SelectionDecision, ReuseEvent]:
        """Full pipeline: parse -> decide -> record. Returns (decision, event)."""
        decision = self.select(
            parse_query(query_text),
            candidate_key=candidate_key,
            candidate_quality=candidate_quality,
        )
        event = self._reuse.apply(decision, consumer=consumer, topic=topic)
        return decision, event

    # ------------------------------------------------------ consumer contracts --

    def workflow_lookup(self, topic: str, *, model: str = "") -> AssetRecord | None:
        """Workflow Builder: the best workflow JSON for a topic (reuse bar)."""
        return self._lookup_with_bar(
            AssetQuery(topic=topic, asset_type=AssetType.WORKFLOW_JSON, model=model)
        )

    def select_for_render(
        self,
        *,
        topic: str,
        objects: tuple[str, ...] = (),
        materials: tuple[str, ...] = (),
        processes: tuple[str, ...] = (),
        camera: str = "",
        lighting: str = "",
        candidate_quality: float | None = None,
        candidate_key: str = "render-scene",
    ) -> tuple[SelectionDecision, AssetRecord | None]:
        """Render Loop: decide whether an image is reused or generated.

        Returns (decision, chosen asset); the asset is None exactly when
        the studio decides to generate or improve (nothing to reuse).
        """
        query = AssetQuery(
            topic=topic,
            asset_type=AssetType.IMAGE,
            objects=objects,
            materials=materials,
            processes=processes,
            camera=camera,
            lighting=lighting,
        )
        decision = self.select(
            query, candidate_key=candidate_key, candidate_quality=candidate_quality
        )
        asset = None
        if decision.decision in (
            ReuseDecision.REUSE,
            ReuseDecision.REPLACE,
            ReuseDecision.MERGE,
        ) and decision.chosen_asset_id is not None:
            asset = self._registry.try_get(decision.chosen_asset_id)
        return decision, asset

    def optimizer_lookup(
        self, *, topic: str, workflow_asset_id: str
    ) -> AssetRecord | None:
        """Render Optimizer: the best optimization history for a workflow."""
        workflow = self._registry.try_get(workflow_asset_id)
        if workflow is None:
            return None
        return self._lookup_with_bar(
            AssetQuery(topic=topic, asset_type=AssetType.OPTIMIZATION_HISTORY)
        )

    def publisher_lookup(
        self, *, topic: str, asset_type: AssetType
    ) -> AssetRecord | None:
        """Publisher: the best reusable asset of one type for a topic."""
        return self._lookup_with_bar(AssetQuery(topic=topic, asset_type=asset_type))

    # -------------------------------------------------------------- reports --

    def export(self, output_dir: Path) -> dict[str, Path]:
        """Write the five deterministic JSON exports; returns name -> path."""
        return export_reports(
            self._registry, self._reuse, self._dependencies, output_dir
        )

    # ----------------------------------------------------------------- misc --

    def _lookup_with_bar(self, query: AssetQuery) -> AssetRecord | None:
        """The best match, or None when it does not clear the reuse bar."""
        record = best_match(self.index(), query)
        if record is None or record.quality_score < REUSE_QUALITY_THRESHOLD:
            return None
        return record

    def asset_count(self) -> int:
        """How many distinct assets the studio holds."""
        return self._registry.count()
