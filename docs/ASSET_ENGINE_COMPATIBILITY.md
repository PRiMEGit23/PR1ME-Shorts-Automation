# Asset Engine - Compatibility Statement (Phase 12)

How the Asset Engine fits the existing PR1ME Studio without breaking it.
Every existing test keeps passing (578 in the full suite); the knowledge
base stays immutable; the Learning Engine stays observer-only.

## What changed in this phase

| File | Change |
| --- | --- |
| `knowledge/asset_engine/` | **new** - 14 modules (models, registry, index, search, similarity, matcher, selector, versioning, quality, dependencies, reuse, reports, facade, `__init__`) |
| `knowledge/asset_engine/examples/` | **new** - `_collector.py` (ingest) and `run_worked_examples.py` (demo) |
| `tests/test_asset_engine.py` | **new** - 45 tests |
| `docs/ASSET_ENGINE_ARCHITECTURE.md` | **new** - this phase's architecture |
| `knowledge/learning_engine/examples/_collector.py` | **additive only** - `FilmRun` dataclass and `collect_film_run()` added; `collect_film()` now delegates to it. Phase 11's 44 tests still pass unchanged. |
| `knowledge/learning_engine/quality_predictor.py` | (Phase 11 session) additive `axis_for_shot` helper; no signature changed |

Nothing else was modified: the runtime, the directors, the compiler, the
render optimizer, the knowledge base, and the Learning Engine are untouched.

## Invariants preserved

| Invariant | Where it holds |
| --- | --- |
| Knowledge base immutable | the Asset Engine never reads or edits `knowledge_base.csv`; the Learning Engine never edits it either (observer-only) |
| Learning Engine proposal-only | proposals still end in `KnowledgeDiff`s awaiting review; the Asset Engine does not propose knowledge changes |
| Determinism | no timestamps, no randomness: identical artifacts produce identical fingerprints, ids, scores, decisions, and exports |
| All existing APIs intact | `collect_film` still returns `ProjectRecord`; all Phase 11 signatures unchanged |
| No duplicated lookup logic | the facade's `select` / `best_match` / `search` are the only lookup paths |

## Consumer contracts (integration points)

The consumers are **not** modified in this phase; the facade exposes the
decision methods they will call, and the contracts are documented in
`ASSET_ENGINE_ARCHITECTURE.md` and exercised in `tests/test_asset_engine.py`:

- **Workflow Builder** -> `workflow_lookup(topic, model)`
- **Render Loop** -> `select_for_render(...)` (decision + asset; None when generating)
- **Render Optimizer** -> `optimizer_lookup(topic, workflow_asset_id)`
- **Publisher** -> `publisher_lookup(topic, asset_type)`
- **Any producer** -> `register(...)` (content-addressed ingest) and `request(...)`
  (parse -> decide -> record)

## Determinism guarantees (what the tests pin)

- The same ingest order + seeds always yield the same asset ids, chains,
  reuse events, and report bytes (`test_exports_are_byte_identical_on_rerun`).
- Two studios built from the same specs export byte-identical reports
  (`test_exports_are_stable_across_engines`).
- The six canonical search questions resolve deterministically
  (`test_mission_queries_find_the_right_assets`).
- All five decisions - replace, merge, reuse, improve, generate - are
  individually pinned (`test_selector_*`).

## Performance

- Search and selection over a 1000-asset studio complete well under one
  second (`test_thousand_asset_studio_searches_within_budget`).
- The index is rebuilt lazily (once per batch ingest), so registration
  stays linear; queries are sorted bucket scans.

## Known pre-existing mypy baseline

`mypy` on the repo reports 16 pre-existing errors in untouched files
(`composition_planner.py`, `prompt_mutator.py`, `sdxl.py`, `optimizer.py`);
all `knowledge/asset_engine/` code is mypy-clean. Ruff is clean across
`knowledge/` and `tests/`.
