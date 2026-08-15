"""Asset Engine tests (Phase 12): the studio's reusable asset store.

Covers the deterministic asset engine over real and purpose-built
studios:

- registration: content-addressed dedupe, idempotent twins, merged events
- search: the studio's canonical questions ("all gyroid cross-sections",
  "all macro nozzle renders", "all FDM diagrams", "all planetary gear
  animations", "all injection molding shots", "all brass nozzle closeups")
  find the right assets, deterministically
- similarity: symmetric, bounded, exact for identical content
- selection: all five decisions - reuse, improve, generate, replace,
  merge - with the reuse bar and similarity thresholds enforced
- versioning: chains, versions, parents, supersession, lineage
- reuse engine: recorded events, usage, topics, reuse score, ratio
- dependencies: validated edges, transitive closure, roots, cycles
- quality aggregates and the five byte-identical JSON exports
- determinism and performance: 5000 assets search within the budget
- the worked examples: real runs collected through the production stack

All tests run offline; rendering is the SimulatedRenderer.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from knowledge.asset_engine import (
    ASSET_ENGINE_VERSION,
    AssetEngine,
    AssetQuery,
    AssetRecord,
    AssetType,
    ReuseDecision,
)
from knowledge.asset_engine.asset_engine import parse_query
from knowledge.asset_engine.asset_matcher import content_twins
from knowledge.asset_engine.asset_quality import quality_breakdown, studio_quality
from knowledge.asset_engine.asset_search import search
from knowledge.asset_engine.asset_similarity import similarity, similarity_to_query
from knowledge.asset_engine.asset_versioning import (
    chain_key,
    chain_members,
    lineage,
    newest_active,
)
from knowledge.asset_engine.examples._collector import ingest_films
from knowledge.learning_engine.examples._collector import collect_film_run
from knowledge.visual_architecture import EngineeringDomain, Modality

# ---------------------------------------------------------------- builders --

_MISSION_STUDIO: tuple[dict, ...] = (
    {
        "asset_type": AssetType.CROSS_SECTION,
        "topic": "Gyroid Infill Patterns",
        "objects": ("gyroid", "infill patterns", "honeycomb"),
        "materials": ("PLA", "PETG"),
        "engineering_category": "FDM",
        "visual_tags": ("cross section", "macro"),
        "processes": ("cross section", "layer-by-layer print"),
        "quality": 88.0,
    },
    {
        "asset_type": AssetType.ENGINEERING_DIAGRAM,
        "topic": "FDM Process Overview",
        "objects": ("fdm", "fused deposition", "extruder"),
        "engineering_category": "FDM",
        "visual_tags": ("diagram", "schematic"),
        "processes": ("diagram", "exploded view"),
        "quality": 82.0,
    },
    {
        "asset_type": AssetType.ANIMATION,
        "topic": "Planetary Gear Systems",
        "objects": ("planetary gear", "sun gear", "gear box"),
        "engineering_category": "Mechanisms",
        "visual_tags": ("animation", "assembly sequence"),
        "processes": ("animation", "assembly sequence"),
        "quality": 90.0,
    },
    {
        "asset_type": AssetType.IMAGE,
        "topic": "Injection Molding Process",
        "objects": ("injection molding", "mold", "molded parts"),
        "engineering_category": "Injection Molding",
        "materials": ("polypropylene",),
        "visual_tags": ("macro", "manufacturing"),
        "camera": "eye level medium",
        "quality": 86.0,
    },
    {
        "asset_type": AssetType.IMAGE,
        "topic": "Brass Nozzle Macro",
        "objects": ("nozzle", "hotend"),
        "engineering_category": "FDM",
        "materials": ("brass", "copper"),
        "visual_tags": ("closeup", "macro"),
        "camera": "macro lens",
        "quality": 93.0,
    },
)


def _engine_with(records: tuple[dict, ...]) -> AssetEngine:
    """A studio built from record specs (deterministic fingerprints)."""
    engine = AssetEngine()
    for index, spec in enumerate(records):
        engine.register(
            asset_type=spec["asset_type"],
            fingerprint=f"{index:012x}{'f' * 52}",
            source_topic=spec["topic"],
            quality_score=spec["quality"],
            educational_category=spec.get("educational_category", ""),
            engineering_category=spec.get("engineering_category", ""),
            objects=spec.get("objects", ()),
            materials=spec.get("materials", ()),
            processes=spec.get("processes", ()),
            camera=spec.get("camera", ""),
            lighting=spec.get("lighting", ""),
            model_used=spec.get("model_used", "gpt-image"),
            workflow_version=spec.get("workflow_version", "1.0"),
            retention_prediction=spec.get("retention", 70.0),
            optimization_count=spec.get("optimizations", 0),
            visual_tags=spec.get("visual_tags", ()),
            semantic_tags=spec.get("semantic_tags", ()),
            run_id=f"test-run-{index}",
            scene_id=f"S{index + 1}",
        )
    return engine


def _mission_engine() -> AssetEngine:
    return _engine_with(_MISSION_STUDIO)


# --------------------------------------------------------------- contracts --

def test_version_stamp_and_query_contract() -> None:
    assert ASSET_ENGINE_VERSION == "12.0.0"
    query = AssetQuery(topic="gyroid", asset_type=AssetType.CROSS_SECTION)
    assert not query.is_empty()
    assert AssetQuery().is_empty()


def test_registration_is_content_addressed() -> None:
    engine = AssetEngine()
    first = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="f" * 64,
        source_topic="Gyroid",
        quality_score=80.0,
    )
    second = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="f" * 64,
        source_topic="Gyroid",
        quality_score=80.0,
    )
    assert first.asset_id == second.asset_id
    assert engine.asset_count() == 1
    assert second.creation_history[-1].action == "merged"
    assert second.creation_history[-1].sequence == 1


def test_registration_requires_64_hex_fingerprint() -> None:
    engine = AssetEngine()
    with pytest.raises(ValueError):
        engine.register(
            asset_type=AssetType.IMAGE,
            fingerprint="short",
            source_topic="Gyroid",
            quality_score=80.0,
        )


def test_record_is_immutable_and_typed() -> None:
    engine = _mission_engine()
    record = engine.registry().get(engine.registry().ids()[0])
    with pytest.raises(ValueError):
        record.quality_score = 99.0  # type: ignore[misc]
    assert isinstance(record, AssetRecord)


def test_create_fingerprint_is_deterministic() -> None:
    from knowledge.asset_engine import create_fingerprint

    assert create_fingerprint("same payload") == create_fingerprint("same payload")
    assert create_fingerprint("same payload") != create_fingerprint("other payload")
    assert len(create_fingerprint("x")) == 64


# ------------------------------------------------------------------ search --

@pytest.mark.parametrize(
    ("query_text", "expected_type", "expected_topic"),
    [
        ("all gyroid cross-sections", AssetType.CROSS_SECTION, "Gyroid Infill Patterns"),
        ("all macro nozzle renders", AssetType.IMAGE, "Brass Nozzle Macro"),
        ("all FDM diagrams", AssetType.ENGINEERING_DIAGRAM, "FDM Process Overview"),
        ("all planetary gear animations", AssetType.ANIMATION, "Planetary Gear Systems"),
        ("all injection molding shots", AssetType.IMAGE, "Injection Molding Process"),
        ("all brass nozzle closeups", AssetType.IMAGE, "Brass Nozzle Macro"),
    ],
)
def test_mission_queries_find_the_right_assets(
    query_text: str, expected_type: AssetType, expected_topic: str
) -> None:
    engine = _mission_engine()
    parsed = parse_query(query_text)
    assert parsed.asset_type is expected_type
    results = search(engine.index(), parsed)
    assert results, f"{query_text!r} returned no hits"
    top = engine.registry().get(results[0].asset_id)
    assert top.asset_type is expected_type
    assert top.source_topic == expected_topic


def test_search_is_deterministic_and_sorted() -> None:
    engine = _mission_engine()
    first = search(engine.index(), parse_query("all injection molding shots"))
    second = search(engine.index(), parse_query("all injection molding shots"))
    assert [result.asset_id for result in first] == [
        result.asset_id for result in second
    ]
    scores = [result.similarity for result in first]
    assert scores == sorted(scores, reverse=True)


def test_empty_studio_search_returns_nothing() -> None:
    engine = AssetEngine()
    assert search(engine.index(), parse_query("all gyroid cross-sections")) == ()


# -------------------------------------------------------------- similarity --

def test_similarity_is_symmetric_and_bounded() -> None:
    engine = _mission_engine()
    records = engine.registry().all()
    for left in records:
        for right in records:
            score = similarity(left, right)
            assert 0.0 <= score <= 1.0
            assert score == similarity(right, left)


def test_identical_content_is_maximally_similar() -> None:
    engine = _mission_engine()
    records = engine.registry().all()
    for record in records:
        assert similarity(record, record) == 1.0


def test_similarity_query_exact_fields_score_one() -> None:
    engine = _mission_engine()
    record = engine.registry().by_type(AssetType.IMAGE)[0]
    query = AssetQuery(
        topic=record.source_topic,
        asset_type=AssetType.IMAGE,
        objects=record.objects,
        materials=record.materials,
        camera=record.camera,
        lighting=record.lighting,
    )
    assert similarity_to_query(record, query) == 1.0


# --------------------------------------------------------------- selection --

def test_selector_reuses_a_quality_asset() -> None:
    engine = _mission_engine()
    record = engine.registry().by_type(AssetType.IMAGE)[0]
    query = AssetQuery(
        topic=record.source_topic,
        asset_type=AssetType.IMAGE,
        objects=record.objects,
        materials=record.materials,
        camera=record.camera,
        lighting=record.lighting,
    )
    decision = engine.select(query, candidate_key="render-loop/scene-01")
    assert decision.decision is ReuseDecision.REUSE
    assert decision.chosen_asset_id == record.asset_id
    assert decision.similarity >= 0.85
    assert "reuse" in decision.rationale


def test_selector_generates_when_nothing_matches() -> None:
    engine = _mission_engine()
    query = AssetQuery(
        topic="quantum flux capacitors",
        asset_type=AssetType.IMAGE,
    )
    decision = engine.select(query, candidate_key="render-loop/scene-99")
    assert decision.decision is ReuseDecision.GENERATE


def test_selector_improves_a_weak_but_similar_asset() -> None:
    engine = AssetEngine()
    engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="0" * 64,
        source_topic="Weak Gyroid Render",
        quality_score=60.0,
        objects=("gyroid",),
        materials=("PLA",),
        engineering_category="FDM",
    )
    query = AssetQuery(
        topic="Weak Gyroid Render",
        asset_type=AssetType.IMAGE,
        objects=("gyroid",),
        materials=("PLA",),
    )
    decision = engine.select(query, candidate_key="render-loop/scene-02")
    assert decision.decision is ReuseDecision.IMPROVE
    assert "quality" in decision.rationale


def test_selector_merges_duplicate_assets() -> None:
    engine = AssetEngine()
    engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="1" * 64,
        source_topic="Duplicate Brass Nozzle",
        quality_score=90.0,
        objects=("nozzle",),
        materials=("brass",),
        engineering_category="FDM",
        camera="macro lens",
        lighting="key softbox",
        visual_tags=("closeup", "macro"),
        semantic_tags=("nozzle", "brass"),
        processes=("closeup",),
    )
    engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="2" * 64,
        source_topic="Duplicate Brass Nozzle",
        quality_score=90.0,
        objects=("nozzle",),
        materials=("brass",),
        engineering_category="FDM",
        camera="macro lens",
        lighting="key softbox",
        visual_tags=("closeup", "macro"),
        semantic_tags=("nozzle", "brass"),
        processes=("closeup",),
    )
    record = engine.registry().by_type(AssetType.IMAGE)[0]
    query = AssetQuery(
        topic=record.source_topic,
        asset_type=AssetType.IMAGE,
        objects=record.objects,
        materials=record.materials,
        engineering_category=record.engineering_category,
    )
    decision = engine.select(query, candidate_key="render-loop/scene-03")
    assert decision.decision is ReuseDecision.MERGE
    assert len(decision.evidence) == 2


def test_selector_replaces_when_a_better_version_exists() -> None:
    engine = AssetEngine()
    v1 = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="a" * 64,
        source_topic="Gyroid Hero",
        quality_score=80.0,
        objects=("gyroid",),
        materials=("PLA",),
    )
    v2 = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="b" * 64,
        source_topic="Gyroid Hero",
        quality_score=85.0,
        objects=("gyroid",),
        materials=("PLA",),
    )
    assert v1.asset_id != v2.asset_id
    query = AssetQuery(
        topic="Gyroid Hero",
        asset_type=AssetType.IMAGE,
        objects=("gyroid",),
        materials=("PLA",),
    )
    decision = engine.select(
        query,
        candidate_key="render-loop/scene-04",
        existing_asset_id=v1.asset_id,
    )
    assert decision.decision is ReuseDecision.REPLACE
    assert decision.chosen_asset_id == v2.asset_id
    assert decision.evidence == (v1.asset_id, v2.asset_id)


# --------------------------------------------------------------- versioning --

def test_chain_key_is_deterministic_and_semantic() -> None:
    engine = _mission_engine()
    records = engine.registry().all()
    assert chain_key(records[0]) == chain_key(records[0])
    assert chain_key(records[0]) != chain_key(records[1])


def test_versions_increment_and_link_parents() -> None:
    engine = AssetEngine()
    v1 = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="a" * 64,
        source_topic="Gyroid Hero",
        quality_score=80.0,
        objects=("gyroid",),
    )
    v2 = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="b" * 64,
        source_topic="Gyroid Hero",
        quality_score=85.0,
        objects=("gyroid",),
    )
    assert v1.version == 1
    assert v2.version == 2
    assert v2.chain_id == v1.chain_id
    assert v2.parent_asset_id == v1.asset_id
    members = chain_members(engine.registry(), v1.asset_id)
    assert [member.version for member in members] == [1, 2]


def test_supersession_marks_old_version_obsolete() -> None:
    engine = AssetEngine()
    v1 = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="a" * 64,
        source_topic="Gyroid Hero",
        quality_score=80.0,
        objects=("gyroid",),
    )
    v2 = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="b" * 64,
        source_topic="Gyroid Hero",
        quality_score=85.0,
        objects=("gyroid",),
    )
    old = engine.registry().get(v1.asset_id)
    assert old.status.value == "obsolete"
    assert old.superseded_by == v2.asset_id
    assert newest_active(engine.registry(), v1.asset_id).asset_id == v2.asset_id


def test_no_supersession_below_the_quality_gap() -> None:
    engine = AssetEngine()
    v1 = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="a" * 64,
        source_topic="Gyroid Hero",
        quality_score=80.0,
        objects=("gyroid",),
    )
    v2 = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="b" * 64,
        source_topic="Gyroid Hero",
        quality_score=81.0,
        objects=("gyroid",),
    )
    assert engine.registry().get(v1.asset_id).status.value == "active"
    assert engine.registry().get(v2.asset_id).status.value == "active"


def test_lineage_is_ancestry_oldest_first() -> None:
    engine = AssetEngine()
    engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="a" * 64,
        source_topic="Gyroid Hero",
        quality_score=80.0,
        objects=("gyroid",),
    )
    v2 = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="b" * 64,
        source_topic="Gyroid Hero",
        quality_score=85.0,
        objects=("gyroid",),
    )
    ancestors = lineage(engine.registry(), v2.asset_id)
    assert [record.version for record in ancestors] == [1, 2]


# ------------------------------------------------------------------- reuse --

def test_reuse_engine_records_usage_and_score() -> None:
    engine = _mission_engine()
    record = engine.registry().by_type(AssetType.IMAGE)[0]
    query = AssetQuery(
        topic=record.source_topic,
        asset_type=AssetType.IMAGE,
        objects=record.objects,
        materials=record.materials,
    )
    decision = engine.select(query, candidate_key="publisher/scene-01")
    assert decision.decision is ReuseDecision.REUSE
    event = engine.reuse_engine().apply(decision, consumer="publisher", topic=record.source_topic)
    assert event.consumer == "publisher"
    assert event.asset_id == record.asset_id
    assert engine.reuse_engine().usage_count(record.asset_id) == 1
    assert engine.reuse_engine().topics_using(record.asset_id) == (record.source_topic,)
    assert engine.reuse_engine().reuse_ratio() == 1.0
    assert engine.reuse_engine().most_used()[0] == record.asset_id


def test_reuse_score_combines_quality_and_usage() -> None:
    engine = AssetEngine()
    record = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="f" * 64,
        source_topic="Gyroid",
        quality_score=80.0,
    )
    assert record.reuse_score == 56.0  # 0.7 * 80 + 0.3 * 0
    for _ in range(3):
        engine.reuse_engine().apply(
            engine.select(
                AssetQuery(topic="Gyroid", asset_type=AssetType.IMAGE),
                candidate_key="publisher/scene-01",
            ),
            consumer="publisher",
            topic="gyroid",
        )
    updated = engine.registry().get(record.asset_id)
    assert updated.usage_count == 3
    assert updated.reuse_score > record.reuse_score


def test_reuse_policy_never_reuses_weak_assets() -> None:
    engine = AssetEngine()
    engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="0" * 64,
        source_topic="Weak Render",
        quality_score=50.0,
    )
    record = engine.registry().by_type(AssetType.IMAGE)[0]
    assert record.asset_id not in engine.reuse_engine().reuseable_candidates()


def test_content_twins_finds_duplicate_content() -> None:
    engine = AssetEngine()
    first = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="f" * 64,
        source_topic="Gyroid",
        quality_score=80.0,
    )
    twin = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="f" * 64,
        source_topic="Gyroid, other scene",
        quality_score=80.0,
    )
    assert first.asset_id == twin.asset_id
    assert content_twins(engine.index(), first) == ()


# ------------------------------------------------------------ dependencies --

def test_dependency_edges_validate_and_answer_both_ways() -> None:
    engine = AssetEngine()
    image = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="1" * 64,
        source_topic="Gyroid",
        quality_score=85.0,
    )
    prompt = engine.register(
        asset_type=AssetType.PROMPT_PACK,
        fingerprint="2" * 64,
        source_topic="Gyroid",
        quality_score=85.0,
    )
    workflow = engine.register(
        asset_type=AssetType.WORKFLOW_JSON,
        fingerprint="3" * 64,
        source_topic="Gyroid",
        quality_score=85.0,
    )
    deps = engine.dependencies()
    deps.add(
        dependent=image.asset_id,
        dependency=prompt.asset_id,
        kind="uses",
        reason="prompt",
    )
    deps.add(
        dependent=image.asset_id,
        dependency=workflow.asset_id,
        kind="uses",
        reason="workflow",
    )
    assert [edge.dependency for edge in deps.dependencies_of(image.asset_id)] == [
        prompt.asset_id,
        workflow.asset_id,
    ]
    assert [edge.dependent for edge in deps.dependents_of(prompt.asset_id)] == [
        image.asset_id
    ]
    assert deps.edge_count() == 2
    assert set(deps.transitive_dependencies(image.asset_id)) == {
        prompt.asset_id,
        workflow.asset_id,
    }


def test_dependencies_reject_unknown_assets() -> None:
    engine = _mission_engine()
    deps = engine.dependencies()
    with pytest.raises(KeyError):
        deps.add(dependent="nope", dependency="also-nope", kind="uses")


def test_dependencies_detect_cycles_and_roots() -> None:
    engine = AssetEngine()
    a = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="a" * 64,
        source_topic="A",
        quality_score=80.0,
    )
    b = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint="b" * 64,
        source_topic="B",
        quality_score=80.0,
    )
    deps = engine.dependencies()
    deps.add(dependent=a.asset_id, dependency=b.asset_id, kind="uses")
    deps.add(dependent=b.asset_id, dependency=a.asset_id, kind="uses")
    assert deps.has_cycle()
    assert set(deps.roots()) == set()


# ------------------------------------------------------------------ quality --

def test_quality_aggregates_per_bucket() -> None:
    engine = _mission_engine()
    breakdown = quality_breakdown(engine.registry())
    assert "type" in breakdown
    image_summary = breakdown["type"]["image"]
    assert image_summary.count == 2
    assert image_summary.mean_qa == pytest.approx((86.0 + 93.0) / 2)
    studio = studio_quality(engine.registry())
    assert studio.count == len(_MISSION_STUDIO)
    assert studio.mean_qa == pytest.approx(
        sum(spec["quality"] for spec in _MISSION_STUDIO) / len(_MISSION_STUDIO)
    )
    assert studio.pass_rate == pytest.approx(1.0)


# ------------------------------------------------------------------ reports --

def test_exports_are_byte_identical_on_rerun(tmp_path: Path) -> None:
    engine = _mission_engine()
    first = engine.export(tmp_path)
    second = engine.export(tmp_path)
    assert set(first) == set(second)
    for name, path in first.items():
        assert path.read_bytes() == second[name].read_bytes(), name
    database = json.loads(first["asset_database.json"].read_text(encoding="utf-8"))
    assert database["version"] == ASSET_ENGINE_VERSION
    assert database["asset_count"] == len(_MISSION_STUDIO)
    assert "asset_dashboard.json" in first


def test_exports_are_stable_across_engines(tmp_path: Path) -> None:
    one = _mission_engine()
    two = _mission_engine()
    one_export = one.export(tmp_path / "one")
    two_export = two.export(tmp_path / "two")
    for name in one_export:
        assert one_export[name].read_bytes() == two_export[name].read_bytes(), name


def test_dashboard_summary_counts() -> None:
    engine = _mission_engine()
    from knowledge.asset_engine.asset_reports import build_dashboard_payload

    payload = build_dashboard_payload(
        engine.registry(), engine.reuse_engine(), engine.dependencies()
    )
    assert payload["summary"]["total_assets"] == len(_MISSION_STUDIO)
    assert payload["summary"]["chains"] == len(_MISSION_STUDIO)
    assert payload["summary"]["dependency_edges"] == 0


# ------------------------------------------------------------------ request --

def test_request_pipeline_returns_decision_and_event() -> None:
    engine = _mission_engine()
    decision, event = engine.request(
        "all injection molding shots",
        consumer="publisher",
        topic="injection molding",
        candidate_key="publisher/shot-01",
    )
    assert decision.decision is ReuseDecision.GENERATE  # similarity below 0.85
    assert event.sequence == 0
    decision, event = engine.request(
        "all injection molding shots",
        consumer="publisher",
        topic="injection molding",
        candidate_key="publisher/shot-01",
    )
    assert event.sequence == 1
    assert len(engine.reuse_engine().events()) == 2


# ----------------------------------------------------------- consumer calls --

def test_workflow_lookup_returns_none_when_below_bar() -> None:
    engine = AssetEngine()
    engine.register(
        asset_type=AssetType.WORKFLOW_JSON,
        fingerprint="a" * 64,
        source_topic="Weak Workflow",
        quality_score=70.0,
    )
    assert engine.workflow_lookup("Weak Workflow") is None


def test_workflow_lookup_returns_quality_workflow() -> None:
    engine = AssetEngine()
    engine.register(
        asset_type=AssetType.WORKFLOW_JSON,
        fingerprint="b" * 64,
        source_topic="Solid Workflow",
        quality_score=85.0,
    )
    record = engine.workflow_lookup("Solid Workflow")
    assert record is not None
    assert record.source_topic == "Solid Workflow"


def test_select_for_render_returns_asset_on_reuse() -> None:
    engine = _mission_engine()
    record = engine.registry().by_type(AssetType.IMAGE)[0]
    decision, asset = engine.select_for_render(
        topic=record.source_topic,
        objects=record.objects,
        materials=record.materials,
        camera=record.camera,
        lighting=record.lighting,
        candidate_quality=record.quality_score,
    )
    assert decision.decision is ReuseDecision.REUSE
    assert asset is not None
    assert asset.asset_id == record.asset_id


def test_select_for_render_returns_none_asset_on_generate() -> None:
    engine = _mission_engine()
    decision, asset = engine.select_for_render(
        topic="quantum flux capacitors",
        candidate_key="render-loop/quantum-01",
    )
    assert decision.decision is ReuseDecision.GENERATE
    assert asset is None


# -------------------------------------------------------------------- perf --

def test_thousand_asset_studio_searches_within_budget() -> None:
    engine = AssetEngine()
    for index in range(1000):
        engine.register(
            asset_type=AssetType.IMAGE,
            fingerprint=f"{index:012d}{'f' * 52}",
            source_topic=f"Topic {index % 20}",
            quality_score=70.0 + (index % 25),
            objects=("gyroid",) if index % 2 else ("nozzle",),
            materials=("PLA", "PETG"),
            engineering_category="FDM",
        )
    assert engine.asset_count() == 1000
    started = time.perf_counter()
    results = engine.search("all gyroid macro renders", limit=5)
    elapsed = time.perf_counter() - started
    assert results
    assert elapsed < 1.0, f"search took {elapsed:.3f}s"


# ------------------------------------------------------------- worked data --

def test_worked_examples_index_real_films() -> None:
    engine = AssetEngine()
    films = tuple(
        collect_film_run(
            key=key,
            seed=seed,
            run_index=run_index,
            engineering_domain=domain,
            modality=modality,
        )
        for run_index, (key, seed, domain, modality) in enumerate(
            (
                ("gyroid", 42, EngineeringDomain.FDM, Modality.CROSS_SECTION),
                ("planetary_gear", 42, EngineeringDomain.MECHANISMS, Modality.EXPLODED_VIEW),
                ("injection_molding", 42, EngineeringDomain.INJECTION_MOLDING, Modality.MACRO_INSPECTION),
            )
        )
    )
    indexed = ingest_films(engine, films)
    assert len(indexed) == 3
    assert all(scene_ids for scene_ids in indexed.values())
    assert engine.asset_count() > 20
    types = {record.asset_type for record in engine.registry().all()}
    assert AssetType.IMAGE in types
    assert AssetType.QA_REPORT in types
    assert AssetType.WORKFLOW_JSON in types
    assert AssetType.CROSS_SECTION in types


def test_worked_examples_reuse_round_trip() -> None:
    engine = AssetEngine()
    films = (
        collect_film_run(
            key="gyroid",
            seed=42,
            run_index=0,
            engineering_domain=EngineeringDomain.FDM,
            modality=Modality.CROSS_SECTION,
        ),
    )
    ingest_films(engine, films)
    images = engine.registry().by_type(AssetType.IMAGE)
    assert images
    best = max(images, key=lambda record: record.quality_score)
    decision, asset = engine.select_for_render(
        topic=best.source_topic,
        objects=best.objects,
        materials=best.materials,
        processes=best.processes,
        camera=best.camera,
        lighting=best.lighting,
        candidate_quality=best.quality_score,
        candidate_key="render-loop/worked-01",
    )
    assert decision.decision is ReuseDecision.REUSE
    assert asset is not None
