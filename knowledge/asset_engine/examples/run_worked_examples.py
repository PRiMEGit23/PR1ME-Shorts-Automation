"""The Asset Engine's worked examples (Phase 12).

Drives the production stack through the shared collector, indexes every
artifact of six real film runs, then exercises the studio:

    Batch 1 - ingest:      every film run becomes indexed assets.
    Batch 2 - questions:   the studio's canonical search questions get
                           search + reuse verdicts (no-hit questions
                           legitimately decide GENERATE: the studio only
                           contains what the films actually produced).
    Batch 3 - reuse pass:  a scene request mirroring an existing image
                           decides REUSE - the engine's whole point.
    Batch 4 - exports:     the five JSON reports, byte-identical on rerun.

Run with:

    python -m knowledge.asset_engine.examples.run_worked_examples
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from knowledge.asset_engine import AssetEngine, AssetQuery, AssetType
from knowledge.asset_engine.examples._collector import ingest_films
from knowledge.learning_engine.examples._collector import collect_film_run
from knowledge.visual_architecture import EngineeringDomain, Modality

#: The canonical studio-wide questions (search + decision demos).
MISSION_QUERIES: tuple[tuple[str, str], ...] = (
    ("all gyroid cross-sections", "render-loop"),
    ("all macro nozzle renders", "render-loop"),
    ("all FDM diagrams", "workflow-builder"),
    ("all planetary gear animations", "publisher"),
    ("all injection molding shots", "publisher"),
    ("all brass nozzle closeups", "render-loop"),
)

#: The six real film runs that build the studio (deterministic seeds).
FILM_SPECS: tuple[tuple[str, int, EngineeringDomain, Modality], ...] = (
    ("gyroid", 42, EngineeringDomain.FDM, Modality.CROSS_SECTION),
    ("gyroid", 43, EngineeringDomain.FDM, Modality.CROSS_SECTION),
    ("planetary_gear", 42, EngineeringDomain.MECHANISMS, Modality.EXPLODED_VIEW),
    ("planetary_gear", 43, EngineeringDomain.MECHANISMS, Modality.EXPLODED_VIEW),
    ("injection_molding", 42, EngineeringDomain.INJECTION_MOLDING, Modality.MACRO_INSPECTION),
    ("injection_molding", 43, EngineeringDomain.INJECTION_MOLDING, Modality.MACRO_INSPECTION),
)

OUTPUT_DIR = Path(__file__).parent / "output"


def main() -> None:
    print("PR1ME Studio - Asset Engine (Phase 12) worked examples")
    print("=" * 62)

    engine = AssetEngine()
    films = tuple(
        collect_film_run(
            key=key,
            seed=seed,
            run_index=run_index,
            engineering_domain=domain,
            modality=modality,
        )
        for run_index, (key, seed, domain, modality) in enumerate(FILM_SPECS)
    )

    print("\n[batch 1] ingest six film runs")
    indexed = ingest_films(engine, films)
    total_scenes = sum(len(scenes) for scenes in indexed.values())
    print(f"  runs indexed : {len(indexed)}")
    print(f"  scenes       : {total_scenes}")
    print(f"  assets       : {engine.asset_count()}")
    counts = Counter(record.asset_type.value for record in engine.registry().all())
    for asset_type in sorted(counts):
        print(f"    {asset_type:<22} {counts[asset_type]}")

    print("\n[batch 2] the studio's canonical search questions")
    for query_text, consumer in MISSION_QUERIES:
        results = engine.search(query_text, limit=3)
        if results:
            top = results[0]
            print(
                f"  search {query_text!r:<34} -> "
                f"{top.asset_id} (sim {top.similarity:.2f})"
            )
        else:
            print(f"  search {query_text!r:<34} -> (no hits)")
        decision, event = engine.request(
            query_text,
            consumer=consumer,
            topic=query_text,
            candidate_key=f"{consumer}/{query_text}",
        )
        print(
            f"    {decision.decision.value:<9} "
            f"closest={event.asset_id or '-'}"
        )

    print("\n[batch 3] reuse pass: a request mirroring an existing image")
    images = engine.registry().by_type(AssetType.IMAGE)
    best = max(images, key=lambda record: record.quality_score)
    query = AssetQuery(
        topic=best.source_topic,
        asset_type=best.asset_type,
        objects=best.objects,
        materials=best.materials,
        processes=best.processes,
        camera=best.camera,
        lighting=best.lighting,
    )
    decision = engine.select(
        query,
        candidate_key=f"render-loop/{best.source_topic}",
        candidate_quality=best.quality_score,
    )
    print(f"  mirroring {best.asset_id} (qa {best.quality_score:.1f})")
    print(f"    decision : {decision.decision.value}")
    print(f"    asset    : {decision.chosen_asset_id}")
    print(f"    rationale: {decision.rationale}")
    engine.reuse_engine().apply(
        decision, consumer="render-loop", topic=best.source_topic
    )

    print("\n[batch 4] reuse policy over the studio")
    print(f"  reuse ratio        : {engine.reuse_engine().reuse_ratio()}")
    print(f"  most used          : {engine.reuse_engine().most_used(limit=3)}")
    print(
        f"  reusable candidates: "
        f"{len(engine.reuse_engine().reuseable_candidates())} of {engine.asset_count()}"
    )

    print("\n[batch 5] exports")
    written = engine.export(OUTPUT_DIR)
    for name, path in sorted(written.items()):
        print(f"  {name:<26} {path}")
    second = engine.export(OUTPUT_DIR)
    identical = all(
        first.read_bytes() == second[name].read_bytes()
        for name, first in written.items()
    )
    print(f"  exports byte-identical on rerun: {identical}")
    if not identical:
        raise SystemExit("determinism check failed: exports differ between runs")


if __name__ == "__main__":
    main()
