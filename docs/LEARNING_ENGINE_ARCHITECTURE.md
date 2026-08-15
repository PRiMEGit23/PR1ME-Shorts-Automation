# PR1ME Brain: The Learning Engine (Phase 11)

The Learning Engine is the self-improving, **observer-only** brain of PR1ME.
It reads the deterministic record of completed pipeline runs and produces
reviewable improvement proposals with supporting evidence. It never edits the
knowledge base: every improvement is a proposal awaiting review.

> **Immutability statement** (also in `learning_rules.py`): the Learning
> Engine never modifies source knowledge; every improvement is a reviewable
> proposal with supporting evidence.

## Principles

| Principle | Guarantee |
| --- | --- |
| No LLM | every statistic, pattern, and proposal is pure arithmetic over observations |
| No randomness | `LearningEngine().learn(history)` is a pure function; the same history always yields the same report, byte for byte |
| No timestamps | trends are ordered by the caller-supplied `run_index`, so identical inputs reproduce identical outputs |
| Immutable knowledge | proposals carry `KnowledgeDiff`s; applying them is a human (or future review) decision, never the engine's |
| No duplicated logic | the engine reuses `group_rows` everywhere and reads shot→axis from `quality_predictor.axis_for_shot` |
| Typed + documented + tested | pydantic models end to end; `tests/test_learning_engine.py` (44 tests) |

## Input: `PipelineHistory`

```
PipelineHistory (version 11.0.0)
  └─ projects: tuple[ProjectRecord, ...]        (≥1, unique run_index)
       ├─ run_id, job_id, topic, seed, status, published
       ├─ total_duration_ms
       └─ scenes: tuple[SceneObservation, ...]  (consecutive S1..Sn)
            ├─ cinematic facts: shot_type, camera (distance/angle/lens/framing),
            │   lighting (direction/style), transition, visualization_type
            ├─ backend facts: image_model, video_model, render_profile,
            │   quality_target, predicted_qa
            ├─ measured facts: qa_score, educational_score, retention_prediction,
            │   thumbnail_priority, attempts, failed_attempts, model_switches,
            │   prompt_mutations, optimization_actions, render_duration_ms,
            │   vram_mb, negative_tokens, passed
```

Every `SceneObservation` is exactly what the pipeline produced: the
`predicted_qa` comes from the Model Director's predictor, the `qa_score` from
the winner's QA report, the cinematic facts from the storyboard. Validation
(`ProjectRecord` / `PipelineHistory` validators) rejects mismatched run ids,
non-consecutive scene ids, and duplicate run indexes.

## The learning pipeline (inside one `learn` call)

```
PipelineHistory
  │
  ├─ quality_statistics      overall_stats, group_rows, 6 QA leaderboards
  ├─ render_statistics       render_leaderboard (video model), retry/switch/mutation stats
  ├─ prompt_statistics       prompt_leaderboard (negative-token signatures), mutation summary
  ├─ curriculum_statistics   topic_leaderboard, retention_leaderboard, educational_stats
  ├─ success_analyzer        success_profiles (7 dimensions, per group)
  ├─ failure_analyzer        failure_profiles (7 dimensions, per group), failed_runs
  ├─ pattern_detector        winner-vs-rest patterns per (metric, dimension)
  ├─ improvement_generator   proposals (6 kinds) from patterns + calibration + failures
  ├─ knowledge_diff          the before/after KnowledgeDiff of every proposal
  └─ report_generator        the four deterministic JSON exports
```

### Patterns (winner vs the rest)

For every configured `(metric, dimension)` pair (`PATTERN_DIMENSIONS`), the
detector splits the history by that dimension and compares each group with the
aggregate of all other groups. A group becomes a pattern only when it clears
all gates — deterministically:

- `MIN_GROUP_SAMPLES` (3) scenes in the group **and** in the rest
- `MIN_DELTA_QA` (2.0) / `MIN_DELTA_RETENTION` (1.0) / `MIN_DELTA_ATTEMPTS` (0.4)
- confidence = `0.5 + sample_bonus + delta_bonus`, capped at 0.95
  (sample_bonus: 0.05 per sample above the minimum, capped at 0.25;
  delta_bonus: `|delta| / scale` capped at 0.15, scales: QA 40, attempts 8,
  retention 20)

Evidence is cited as exact `run_id:scene_id` references (capped at
`MAX_EVIDENCE_SCENES`). Patterns are sorted by `-confidence, -delta,
pattern_id` and capped at `MAX_PATTERNS`.

### Proposals (six kinds, one `Proposal` union)

| Kind | Trigger | Target (diff) |
| --- | --- | --- |
| `knowledge` | calibration: measured vs predicted QA gap ≥ 2.0 per (model, shot) | `model_registry` axis value, half-gap attenuated (`CALIBRATION_ATTENUATION` = 0.5) |
| `knowledge` | topic group wins a QA pattern | `assets/knowledge_base.csv` benchmark |
| `model` | image/video model wins a pattern | `model_registry` capability benchmark |
| `director` | shot/lens/light/transition/visualization/camera/framing wins | `director_rules` preferred value |
| `compiler` | negative-token signature wins | `compiler_negatives` tokens |
| `workflow` | render profile wins | `workflow_selector` profile |
| `optimization` | ≥ `MIN_FAILED_FOR_OPTIMIZER` (3) failed scenes | `optimization_rules` switch bar / fallback chain |

Every proposal carries: `title`, `summary`, `reason`, `confidence`,
`evidence` (exact `run_id:scene_id` refs), `affected_modules`,
`predicted_improvement`, and a `KnowledgeDiff` (before/after/why). Proposals
are deduplicated by `(kind, title)`, sorted by `-confidence, kind, title`, and
capped at `MAX_PROPOSALS` (12).

Calibration is deliberately attenuated: a proposal moves the axis value only
half-way toward the observation, so small samples never overcorrect, and a
gap under `MIN_CALIBRATION_DELTA_QA` never fires at all.

## The eight leaderboards

| Board | Key | Grouped by |
| --- | --- | --- |
| `model` | image_model | image model |
| `workflow` | render_profile | render profile |
| `prompt` | negative_tokens | winning negative-token signature (`+`-joined, `(empty)` fallback) |
| `qa` | scene_id | scene position (S1..S5) |
| `render` | video_model | video model (plus attempts/duration/VRAM means) |
| `topic` | topic | topic (plus retention/educational/thumbnail means) |
| `visual_strategy` | shot_type | shot type |
| `engineering_visualization` | visualization_type | visualization (`(none)` fallback) |

Each row: key, count, mean/min/max QA, pass rate — sorted by `-mean, key`.

## Exports (four JSON reports)

`LearningEngine().export(report, history, output_dir)` writes:

| File | Contents |
| --- | --- |
| `learning_report.json` | the full report: overall, profiles, patterns, proposals, diffs, leaderboards, summary |
| `knowledge_proposals.json` | every proposal with its diff, for human review |
| `performance_dashboard.json` | the eight leaderboards + overall health |
| `trend_report.json` | per-run trends (mean QA, pass rate, attempts, duration) in `run_index` order, plus a first-vs-last window summary (`TREND_WINDOW` = 5) |

All payloads are plain JSON-serializable dicts, written with `sort_keys=True`
and a fixed indent — identical inputs produce byte-identical files
(verified by tests).

## The data collector (`examples/_collector.py`)

The worked examples collect *real* observations through the production stack
— the same components the fifteen-stage pipeline binds:

```
EducationalDirector ──> AIDirector ──> ModelDirector
                              │              │
                              └─────> StoryboardBuilder ──> RenderLoop
                                                        (SimulatedRenderer,
                                                         directive = model plan)
```

One film run (`collect_film`) returns a `ProjectRecord`; `collect_history`
returns the combined `PipelineHistory`; `run_worked_examples` learns from it
and exports the four reports into `knowledge/learning_engine/examples/output/`.

## Module map

```
knowledge/learning_engine/
├── __init__.py               public API (models, engine, learn/export, stats)
├── learning_models.py        every schema + LEARNING_ENGINE_VERSION (11.0.0)
├── learning_rules.py         every threshold, dimension map, cap, confidence
│                             formula constant, suggestion text, immutability
│                             statement (the single source of truth for numbers)
├── quality_statistics.py     group_rows (the shared grouping helper), overall,
│                             QA leaderboards
├── render_statistics.py      render/retry/switch/mutation statistics
├── prompt_statistics.py      prompt leaderboard, mutation summary
├── curriculum_statistics.py  topic/retention leaderboards, educational stats
├── success_analyzer.py       success profiles
├── failure_analyzer.py       failure profiles, failed runs
├── pattern_detector.py       winner-vs-rest patterns (linear, deterministic)
├── improvement_generator.py  the six proposal kinds + calibration
├── knowledge_diff.py         KnowledgeDiff of every proposal
├── report_generator.py       the four JSON exports (byte-identical)
├── learning_engine.py        LearningEngine (learn/export orchestration)
└── examples/
    ├── _collector.py         real pipeline-stack runs -> ProjectRecords
    └── run_worked_examples.py  learn + export for the three films
```

## Verification

- `tests/test_learning_engine.py`: 44 tests — input contract, thresholds,
  patterns, all proposal kinds, calibration, diffs, eight leaderboards,
  determinism (report + exported bytes), immutability, historical replay,
  trends, 1000-scene performance (< 5 s), and the real collector.
- Full suite: 533 passed. `ruff check knowledge tests` clean. `mypy` clean on
  the learning engine (the 16 pre-existing errors in untouched modules
  remain the baseline).
