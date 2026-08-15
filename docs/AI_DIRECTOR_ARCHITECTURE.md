# AI Director (Phase 8) — Autonomous Decision Layer

The pipeline has evolved from a prompt pipeline into an autonomous AI
Director that makes intelligent creative decisions **before a single prompt
is generated**. The director is **not an LLM**: it is a deterministic
decision engine that consumes the EducationalPlan (the teaching intent) and
emits a complete creative brief (`DirectorOutput`) that every downstream
module consumes instead of using fixed heuristics.

```
Knowledge
   ↓
Educational Director          → EducationalPlan (what to teach)
   ↓
AI Director  (NEW)            → DirectorOutput  (how to film it)
   ↓
Visual Intelligence           → VisualStoryboard (verbatim translation)
   ↓
Storyboard / Prompt Compiler / Workflow Builder / Render Optimizer
```

## The contract

**Input** — `EducationalPlan` (frozen, knowledge-layer schema). The director
never touches the CSV row, the renderer, or any model.

**Output** — `DirectorOutput` (`knowledge/ai_director/director_models.py`):

- `scene_count` (4-6) and one `SceneDirective` per scene carrying:
  - importance (1-5), visual / animation / motion budgets (1-10)
  - camera intensity, lighting priority, diagram priority,
    engineering emphasis, comparison emphasis (1-10)
  - emotion (1-10) and pacing (1-10)
  - predicted retention score (0-100) and expected attention (0-100)
  - reveal order (when the scene's information becomes visible)
  - concrete `CameraPlan` / `LightingPlan` / `CompositionPlan` / `Motion` /
    `Mood` / `Transition`
  - structural roles: `is_hero`, `is_thumbnail`, `is_recap`
- `hero_scene_id`, `thumbnail_scene_id`, `recap_scene_id`
- `emotion_arc`, `pacing_profile`, `reveal_plan`
- `predicted_retention`, `predicted_attention`
- `summary` — a deterministic one-line description of the directing choices

**Guarantees** — identical plan → identical `DirectorOutput`. All models are
frozen with `extra="forbid"`; the output is JSON-serializable
(`model_dump(mode="json")`) so it flows through pipeline checkpoints,
fingerprints, and resume unchanged. `DirectorOutput` validators enforce the
arc invariants (consecutive `S1..Sn`, exactly one hero / thumbnail / recap,
recap is the final scene, hero and thumbnail are never the recap, the
thumbnail scene is the single rank-1 candidate).

## Module responsibilities

| Module | Decides |
| --- | --- |
| `scene_prioritizer.py` | Arc size (merge 4 / canonical 5 / split 6), each scene's goal, shot, and base importance; **where macro shots are required** (scale comparison / failure analysis force a macro reveal unless the method already shoots at inspection level) |
| `visual_budget.py` | Visual / animation / motion budgets, diagram priority, engineering emphasis and overlays |
| `emotion_curve.py` | Emotional intensity per scene + the arc shape label |
| `reveal_planner.py` | When each scene's information is revealed (sequential vs staggered) |
| `pacing_planner.py` | Information density per scene + the pacing profile label |
| `transition_planner.py` | The cut grammar between scenes (cut / fade / dissolve / wipe) |
| `hero_scene_selector.py` | The showpiece scene |
| `thumbnail_strategy.py` | The scene that stops the scroll + per-scene thumbnail priority |
| `comparison_strategy.py` | Comparison emphasis per scene (incl. merged arcs) |
| `attention_model.py` | Predicted per-scene attention (peak-normalized to 100) and retention, plus film-level predictions |
| `director_engine.py` | `AIDirector.direct(plan)` — orchestration only, no rules |
| `director_rules.py` | **The single source of truth** for every rule table and mapping (incl. `visualization_for`, the one place overlay tokens are written) |

No decision is duplicated: `director_rules` owns every constant and mapping,
each planner module owns exactly one decision, and the engine only assembles
the `DirectorOutput`.

## Key decisions and how they are made

All formulas below are pure functions; the code in `director_rules.py` is
the canonical reference.

- **Merge / keep / split.** ≤4 knowledge-flow steps with no comparison
  burden → 4 scenes (the comparison beat merges into the process scene).
  ≥6 steps with a sequence-heavy strategy (process timeline, manufacturing
  sequence, material transformation, simulation, mechanical breakdown) → 6
  scenes (an evidence beat earns its own scene). Otherwise the canonical
  five-scene arc: hook, reveal, process, compare, recap.
- **Importance.** Hook and recap start at 4, mid scenes at 3; the hero
  scene is bumped to 5.
- **Hero.** Highest `importance×2 + emotion` among non-recap scenes; reveal
  strategies add a +2 payoff bonus so the withheld reveal can become the
  hero (e.g. planetary gear → hero S2). Ties go to the earlier scene.
- **Thumbnail.** `importance×10 + emotion×3 + motion + diagram potential +
  hero bonus`, recap excluded by rule (a summary frame is weak at 12px
  tall). The pick is the max score; ties go earlier.
- **Reveal.** Default sequential (`reveal_order = scene_index`). Reveal
  strategies (layer-by-layer, hidden geometry, progressive disclosure, myth
  busting, question/answer, cause-to-effect) swap the reveal scene with the
  comparison beat → "staggered reveal": the viewer sees the context before
  the payoff.
- **Emotion.** Per cognitive beat (hook 8, reveal 9, failure 8, ...) with a
  +1 payoff boost for myth-busting / failure-analysis arcs. The arc label
  comes from the peak's position (hook-peak / build-to-peak /
  climax-close / steady).
- **Pacing.** Per-goal density (hook 8, compare 7, summarize 4, ...),
  advanced topics breathe slower (the cognitive-overload guard), and a
  comparison-driven compare beat gains +1. Profiles: fast-open-slow-close,
  accelerating, steady.
- **Macro shots.** A strategy whose teaching vehicle is close inspection
  (scale comparison, failure analysis) forces the reveal beat into a
  `MACRO` shot - unless the chosen method already shoots at inspection
  level (macro / extreme macro / microscope) - and the rationale records
  `macro inspection required`. The decision lives in
  `scene_prioritizer._apply_macro_inspection`; `MACRO_REQUIRED_STRATEGIES`
  in `director_rules` is its single source.
- **Transitions.** Opening cut; **fade** into the emotional peak
  (emotion ≥ 9); **dissolve** to the comparison (emphasis ≥ 7); **wipe** to
  the fast beat (pacing ≥ 7); otherwise a continuity cut.
- **Prediction.** `retention = 20 + importance×9 + emotion×4 +
  (10 − |pacing−5|)×1.5 + (visual_budget−5)×0.5` (0-100). Attention is a
  weighted raw score (importance, emotion, pacing, reveal order, hero,
  thumbnail, motion) peak-normalized so the strongest scene scores 100.

## The QA envelope

The simulated vision pipeline (runtime/renderer.py) cures camera defects
only when the compiled prompt contains **"100mm macro lens" twice** and
lighting defects only for **key-lighting** phrases. The director's mapping
therefore keeps `Lens.MACRO_100` and `LightDirection.KEY` constant while
every other cinematic dimension (distance, angle, framing, composition,
lighting style within studio/hard-key, motion, mood, transitions) varies as
a pure function of the budgets. The envelope is enforced by
`test_camera_and_lighting_stay_in_the_qa_envelope` over all 400 curated
rows and by the render-level test
`test_director_driven_storyboard_passes_qa_across_seeds`.

## Downstream consumption (no duplicated logic)

| Module | Consumes the director via | What changes |
| --- | --- | --- |
| Visual Intelligence / Storyboard | `StoryboardBuilder.build(..., director=DirectorOutput)` | Scene importance, shot, camera, lighting, composition, motion, mood, transition, thumbnail priority — copied verbatim from the directive; zero heuristics in the builder |
| Prompt Compiler | the storyboard it compiles (compiler is unchanged) | `visual_goal`, `shot_type`, engineering-visualization tokens, camera/lighting/composition phrases now carry director decisions; the compiler remains pure phrase assembly |
| Workflow Builder | the scene's shot type / visualization via `select_workflow_profile` (unchanged API) | Profiles follow the director-chosen shots and overlays |
| Render Optimizer | the storyboard it mutates (unchanged API) | Creative budgets are enforced *before* generation; the optimizer only fixes correctness against QA |

The `director=None` legacy path of `StoryboardBuilder` is byte-identical to
pre-Phase-8 behavior (asserted by the existing knowledge-stack identity
test), and the canonical shot-for-method table moved into
`director_rules.shot_for_method` so the runtime no longer carries its own
copy.

## Pipeline integration

A new stage `ai_director` sits between `educational_director` and
`visual_intelligence` (fourteen stages in `runtime/pipeline.py:STAGE_ORDER`).
Its output is JSON-dumped into stage outputs, checkpointed, and
fingerprinted like every other stage; `visual_intelligence` fingerprints
now include the director output, so changing the brief invalidates the
storyboard checkpoint.

## Determinism, constraints

- No LLM, no randomness, no clocks anywhere in the director.
- Knowledge stays declarative: `knowledge/` gains only the additive
  `ai_director` package; no completed architecture was modified except the
  runtime storyboard adapter (additive parameter) and pipeline wiring.
- All 433 pre-existing tests continue passing (458 total after Phase 8).

## Worked examples

```
python -m knowledge.ai_director.examples.gyroid
python -m knowledge.ai_director.examples.planetary_gear
python -m knowledge.ai_director.examples.injection_molding
python -m knowledge.ai_director.examples.run_worked_examples
```

| Example | Director's decisions |
| --- | --- |
| Gyroid infill (comparison) | 5 scenes; hero + thumbnail S1 (hook); sequential reveal; fade → dissolve into the comparison |
| Planetary gear (hidden geometry) | 5 scenes; **hero S2** (the reveal); **staggered reveal** (context before payoff) |
| Injection molding (manufacturing sequence) | **6-scene split** (evidence beat); engineering emphasis on the reveal and process beats |

## Validation & performance

- `test_director_validates_every_curated_row` — all 400 rows of
  `assets/knowledge_base.csv` produce schema-valid, role-consistent output.
- `test_director_is_deterministic_over_the_whole_knowledge_base` — double
  directing reproduces identical briefs.
- `test_macro_shot_required_for_inspection_strategies` (and siblings) —
  macro forcing, the already-inspection-level exemption, and the rule-sourced
  visualization tokens are each pinned by a dedicated test.
- `test_directing_the_whole_knowledge_base_is_fast` — 400 rows (Educational
  Director + AI Director) complete in well under the 5-second budget.
