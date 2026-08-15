# PR1ME Studio: The Asset Engine (Phase 12)

The Asset Engine is PR1ME's **production memory**: every artifact the studio
generates becomes an indexed, reusable asset, and the engine answers the
eternal production question - *reuse, improve, generate, replace, or merge* -
deterministically, from measured quality and rule-based similarity alone.
The studio never regenerates what it can already reuse.

> **Immutability statement** (also in `asset_models.py`): the Asset Engine
> never modifies the knowledge base and never proposes knowledge edits (that
> is the Learning Engine's observer-only job). It reads completed pipeline
> runs through the shared collector and indexes what the pipeline produced.

## Principles

| Principle | Guarantee |
| --- | --- |
| No LLM | every search, similarity, and decision is pure arithmetic over indexed fields |
| No embeddings | rule-based matching: word-level Jaccard over phrase fields, exact match over enum fields |
| No randomness | identical artifacts fingerprint identically (content-addressed) |
| No timestamps | history and reuse events are ordered by caller-supplied sequence numbers |
| Reuse policy | measured quality > `REUSE_QUALITY_THRESHOLD` (75) wins; otherwise generate |
| No duplicated logic | the facade is the single lookup path; the shared Phase 11 collector is the single ingest path |
| Typed + documented + tested | pydantic models end to end; `tests/test_asset_engine.py` (45 tests) |

## The asset record

Every generated artifact is indexed as one `AssetRecord`:

```
AssetRecord
  ├─ identity:     asset_id (type + content-hash prefix), asset_type, fingerprint (sha256)
  ├─ creation:     creation_history (created -> improved -> reused -> merged, by sequence)
  ├─ semantics:    source_topic, educational_category, engineering_category,
  │                objects, materials, processes, camera, lighting
  ├─ production:   model_used, workflow_version
  ├─ measured:     quality_score (winner QA), retention_prediction, optimization_count
  ├─ computed:     reuse_score (0.7 x quality + 0.3 x saturated usage)
  ├─ tags:         visual_tags, semantic_tags (deterministic labels, sorted)
  ├─ usage:        usage_count, topics_using (recorded by the reuse engine)
  └─ genealogy:    status (active/obsolete/merged), version, chain_id,
                   parent_asset_id, superseded_by
```

Fingerprints are content hashes: the image's `image_sha256` for images, the
canonical `json.dumps(..., sort_keys=True)` of workflows and reports, the
prompt bytes for prompt packs. Registering the same content twice returns the
same asset id with a `merged` history event - the store is content-addressed.

## Architecture

```
                    Production stack (EducationalDirector -> ... -> RenderLoop)
                                      │  (one FilmRun, Phase 11 collector)
                                      ▼
        examples/_collector.py  ──►  AssetEngine (facade)
                                      │
        ┌──────────┬──────────┬───────┼──────────┬───────────┬────────────┐
        ▼          ▼          ▼       ▼          ▼           ▼            ▼
   asset_registry  index  search  matcher   selector     versioning  dependencies
        │                 (similarity is the scoring core)
        ▼
   asset_reuse (reuse engine: events, usage, topics, reuse score)
        │
        ▼
   asset_reports (five deterministic JSON exports)
```

### Modules

| Module | Responsibility |
| --- | --- |
| `asset_models.py` | `AssetRecord`, `AssetQuery`, decisions, thresholds, weights, type synonyms (single source of truth) |
| `asset_registry.py` | the store: content-addressed `add`, `update` (immutable-by-replacement), history events, `record_reuse` |
| `asset_index.py` | read-only sorted buckets over the registry (type, tags, topics, categories, models) |
| `asset_search.py` | rule-based query parsing (`parse_query`) and ranked search over the index |
| `asset_similarity.py` | word-level Jaccard over phrase fields, exact match over enum fields; symmetric, bounded |
| `asset_matcher.py` | `best_match`, `ranked`, `nearest`, `content_twins`, `of_type` - the single lookup path |
| `asset_selector.py` | the five decisions: replace, merge, reuse, improve, generate (in that priority) |
| `asset_versioning.py` | chain keys, versions, parents, supersession (gap >= `REPLACE_QUALITY_GAP`), lineage |
| `asset_quality.py` | per-bucket quality aggregates (type / model / topic / engineering category) |
| `asset_dependencies.py` | validated dependency edges, transitive closure, roots, cycle detection |
| `asset_reuse.py` | the reuse policy, `ReuseEvent`s, usage counters, reuse ratio, most-used ranking |
| `asset_reports.py` | the five byte-identical JSON exports |
| `asset_engine.py` | the facade: ingest, search, select, request, consumer contracts, exports |

## The decision pipeline

One candidate request (e.g. a scene the Render Loop is about to shoot):

```
  request(query, consumer, topic, candidate_key)
    ├─ parse_query(text) ─────────────► AssetQuery (type, topic, category, terms)
    ├─ select(query) ─────────────────► SelectionDecision (with evidence + rationale)
    └─ reuse.apply(decision) ─────────► ReuseEvent + usage/topics/reuse_score updates
```

Priority of decisions:

| # | Decision | Trigger |
| --- | --- | --- |
| 1 | `REPLACE` | the candidate's `existing_asset_id` has a chain version that beats it by >= `REPLACE_QUALITY_GAP` (2.0 QA) |
| 2 | `MERGE` | the best match has a near-identical twin (similarity >= `MERGE_SIMILARITY` = 0.95) |
| 3 | `REUSE` | best match similarity >= `REUSE_SIMILARITY` (0.85) and quality >= `REUSE_QUALITY_THRESHOLD` (75) |
| 4 | `IMPROVE` | similarity >= `IMPROVE_SIMILARITY` (0.60) but quality below the bar - regenerate |
| 5 | `GENERATE` | nothing clears the bar - the studio generates new |

Reuse policy (the mission's rule): **quality above the threshold wins**.
A weak asset is never reused; it is improved or replaced.

### Similarity (rule-based, no embeddings)

Each of the ten semantic fields has a fixed weight (`SIMILARITY_WEIGHTS`,
sum = 1.0). Phrase fields (objects like `"planetary gear"`) are split into
words and compared by Jaccard; enum/string fields (camera, lighting, model,
engineering category) match exactly; topics match by shared words. The score
is symmetric, bounded to [0, 1], and a pure function of the two records.
`similarity_to_query` renormalizes by the weights of the fields the query
actually constrains.

### Versioning and lineage

Every record belongs to a chain keyed by its semantic identity (type, topic,
objects, materials, processes). The first record is version 1; each later
record becomes the next version, points at its parent, and - when it beats
the chain's best by at least `REPLACE_QUALITY_GAP` - supersedes it: the old
record is marked `obsolete` with `superseded_by` set. `lineage` walks
parents oldest-first; `newest_active` finds the current best of a chain.

## Consumer contracts (integration without modification)

The facade exposes the lookup decisions the rest of the studio consumes.
No runtime module was modified: the contracts are the *integration points*,
verified by `tests/test_asset_engine.py` and demonstrated in the worked
examples.

| Consumer | Contract |
| --- | --- |
| Workflow Builder | `workflow_lookup(topic, model)` -> best `workflow_json` asset, or None below the reuse bar |
| Render Loop | `select_for_render(topic, objects, materials, processes, camera, lighting)` -> (decision, asset); asset is None exactly when generating/improving |
| Render Optimizer | `optimizer_lookup(topic, workflow_asset_id)` -> best `optimization_history` asset |
| Publisher | `publisher_lookup(topic, asset_type)` -> best reusable asset of one type for a topic |
| All consumers | `request(...)` -> full pipeline (parse, decide, record); `search(...)` for review |
| All consumers | `register(...)` -> content-addressed ingest of new artifacts (the collector does this) |

The shared ingest path is `knowledge/asset_engine/examples/_collector.py`,
which reuses the Phase 11 `FilmRun` and indexes every artifact of a real run:
images, QA reports, optimization histories, workflow JSONs, prompt packs,
camera paths, transitions, and the visualization artifacts (cross-sections,
diagrams, animations). See `ASSET_ENGINE_COMPATIBILITY.md` for the contracts.

## Exports

`AssetEngine.export(output_dir)` writes five deterministic JSON files
(`sort_keys=True`, so the same studio always exports byte-identical files):

| File | Contents |
| --- | --- |
| `asset_database.json` | every record, one entry per asset |
| `asset_statistics.json` | counts and quality aggregates per bucket (type / model / topic / category) |
| `asset_report.json` | reuse events, reuse ratio, verdict (reusable candidates, most used) |
| `asset_lineage.json` | every version chain: versions, statuses, parents, supersession |
| `asset_dashboard.json` | one compact studio-wide overview |

## Worked examples

`python -m knowledge.asset_engine.examples.run_worked_examples` ingests six
real film runs (gyroid, planetary gear, injection molding; deterministic
seeds) through the production stack, indexes ~180 assets, answers the
studio's canonical search questions, demonstrates a REUSE round trip at
similarity 1.00, and exports the five reports - byte-identical on rerun.
