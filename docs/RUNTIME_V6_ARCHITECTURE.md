# Runtime (Phase 6) -- Closed-Loop Generation Engine

Status: **delivered**

Phase 6 converts the architecture into an autonomous generation engine.
Every knowledge subsystem stays untouched: Knowledge Base, Educational
Director, Visual Intelligence, Storyboard, Prompt Compiler, Image QA, and
Render Optimizer logic are not modified. The runtime layer only wires them
into a deterministic, self-improving render loop:

```
Knowledge
   |
   v
Educational Director
   |
   v
Visual Intelligence  (StoryboardBuilder adapter)
   |
   v
Storyboard
   |
   v
Prompt Compiler
   |
   v
Workflow Builder  -------------------+
   |                                  |
   v                                  |
ComfyUI Render (Renderer protocol)    |
   |                                  |
   v                                  |
Image QA                              |
   |                                  |
   |  pass -> winner, stop            |
   |                                  |
   v  fail                            |
Render Optimizer                      |
   |   (previous prompt + workflow    |
   |    + QA report)                  |
   v                                  |
Workflow Builder (regenerate) --------+
   |                                  |
   v                                  |
ComfyUI Render                        |
   |                                  |
   v                                  |
Image QA -------- repeat until PASS or max attempts
```

The loop never calls an LLM and never repeats an identical render. Given
the same Knowledge Base row and the same random seed, the same optimization
sequence is reproduced byte for byte.

## 1. Module map

| Module | Responsibility |
| --- | --- |
| `runtime/models.py` | Pydantic contracts: `RenderRequest`, `RenderResult`, `RenderAttempt`, `SessionConfig`, `RenderSessionResult`; the content fingerprint (`fingerprint_of`) and the on-disk layout helpers (`topic_slug`, `attempt_dir`). |
| `runtime/renderer.py` | `Renderer` protocol (any deterministic renderer: live ComfyUI in production, `SimulatedRenderer` in tests) plus `tiny_png`, a stdlib-only deterministic PNG generator. |
| `runtime/cache.py` | Content-addressed `RenderCache`: fingerprint -> `RenderResult`, in memory and/or on disk. A fingerprint already rendered is never rendered again. |
| `runtime/retry_manager.py` | The retry budget (configurable, default 3) and the duplicate-render guard (`SKIPPED_DUPLICATE`). |
| `runtime/workflow_builder.py` | `WorkflowBuilder.build` (profile + compiled prompt -> workflow JSON) and `WorkflowBuilder.regenerate` (optimizer plan + previous workflow -> regenerated workflow; unchanged when nothing is prescribed). |
| `runtime/storyboard_builder.py` | Deterministic `EducationalPlan` -> `VisualStoryboard` adapter (five-scene directed arc), mirroring the knowledge example stack. |
| `runtime/render_loop.py` | One scene's closed loop: render -> QA -> optimize -> re-render, until PASS or the budget runs out. Saves every attempt's artifacts. |
| `runtime/render_session.py` | Session manager: Knowledge Base row -> plan -> storyboard -> per-scene loops (`run`, `run_all`), persists `history.json`. |
| `runtime/history.py` | `RenderHistory`: every attempt plus the four trajectories (prompt evolution, workflow evolution, QA scores, optimization actions) and the final winner. |
| `runtime/replay.py` | Deterministic replay: rebuild a session result from saved history without re-rendering; `verify_replay_identical` asserts byte-identical reproduction. |
| `runtime/examples/` | Worked examples: the canonical rows run end to end with artifacts on disk (see section 9). |

## 2. Data contracts (`runtime/models.py`)

- `RenderRequest` - one deterministic render: attempt index, scene id,
  prompt, negative prompt, workflow JSON, workflow profile, seed.
- `RenderResult` - observed `GeneratedImageMetadata` (the vision reading)
  plus the image bytes.
- `RenderAttempt` - one saved attempt: inputs, status
  (`rendered`/`passed`/`failed`/`skipped_duplicate`), content fingerprint,
  image sha256, image path, QA report, optimization report, rationale.
- `SessionConfig` - `max_attempts` (default 3, 1..10), `model_key`
  (default `sdxl`), `output_root`, `save_artifacts`.
- `RenderSessionResult` - the complete session: topic, scene id, seed,
  `passed`, `winner`, all attempts; `history` builds the `RenderHistory`.

The content fingerprint is the sha256 over the canonical JSON of
(prompt, negative prompt, workflow, seed). Two requests with the same
fingerprint are the identical render: same bytes, same QA outcome.
Fingerprints are checked against the cache and the executed set before
any render, so an identical render never happens.

## 3. The render loop (`runtime/render_loop.py`)

```
compile prompt for the scene (Prompt Compiler)
pick the initial workflow profile (Workflow Builder)
while the retry budget allows:
    fingerprint = sha256(prompt, negative, workflow, seed)
    if fingerprint already executed: record SKIPPED_DUPLICATE, stop
    result = cache.get(fingerprint) or renderer.render(request) + cache.put
    report = ImageCritic.assess(QAContext(plan, storyboard, scene,
                                          metadata, compiled_prompt))
    if pass: record PASSED winner, save artifacts, stop
    plan = OptimizationEngine.optimize(report, scene, compiled_prompt)
    record FAILED attempt (with plan), save artifacts
    if nothing left to change (no prompt mutation and no workflow
       regeneration): stop
    apply the plan's prompt mutations
    regenerate the workflow from the plan and the previous workflow
    loop
```

Guarantees:

- **Configurable retry budget**, default 3, enforced by `RetryManager`
  before any render happens.
- **Never repeats an identical render** - fingerprint dedup across the
  cache and the executed set; a plan that changes nothing stops the loop
  instead of wasting a render.
- **Render Optimizer receives the previous prompt, the previous workflow
  and the QA report** - the loop carries all three; the optimizer gets the
  report and the compiled prompt (from which its `prompt_mutations` are
  derived), and the previous workflow is folded back in through
  `WorkflowBuilder.regenerate(plan, previous_workflow)`.
- **No LLM calls** anywhere in the loop; only deterministic optimization.
- **Every attempt is saved**: `attempt_01`, `attempt_02`, `attempt_03`, ...
  each with the render prompt, workflow JSON, QA report, optimization
  report (on failures) and the rendered image.

## 4. Determinism and replay

Determinism is structural, not incidental:

- Every stage is a pure function of its inputs; nothing reads clocks or
  randomness, nothing calls a model.
- `SimulatedRenderer` derives image quality from the seed and cures
  defects only when the optimizer's prescriptions actually land in the
  prompt - so the loop closes for real in tests, identically every run.
- Two sessions with the same row + seed + config produce byte-identical
  results (`model_dump(mode="json")`), asserted by the test suite.
- `replay()` rebuilds a session result from saved history JSON (model,
  file, raw text, or dict) without rendering; `verify_replay_identical`
  detects any tampering or divergence.

## 5. Cache (`runtime/cache.py`)

Content-addressed: `<root>/<fingerprint>/metadata.json`, `image.png`,
`fingerprint.json`. Memory-only when no root is given. Reused across
sessions: re-running a row+seed hits the cache and the renderer is not
called again (asserted in the tests).

## 6. History (`runtime/history.py`)

`RenderHistory` tracks, per session:

- **Prompt evolution** - every attempt's prompt and negative prompt.
- **Workflow evolution** - every attempt's workflow profile and JSON.
- **QA scores** - the eight report scores per attempt plus the verdict.
- **Optimization actions** - every fired action (kind, check, instruction,
  expected gain, target score).
- **Final winner** - the last passed attempt, if any.

Persisted as indented JSON (`history.json`) next to the attempt
directories; loadable via `RenderHistory.from_file` / `from_json`.

## 7. Artifact layout

```
output/runtime/<topic_slug>/<scene_id>/
    history.json
    attempt_01/
        prompt.txt              # render prompt
        prompt_negative.txt     # negative prompt
        workflow.json           # workflow JSON
        qa_report.json          # QA report
        optimization_report.json  # optimization report (failures)
        image.png               # rendered image
        attempt.json            # full attempt record
    attempt_02/
        ...
```

## 8. Session manager (`runtime/render_session.py`)

`RenderSession.run(row, scene_id, *, seed, engineering_domain, modality,
config)` runs one scene autonomously; `run_all` covers every storyboard
scene. The director and storyboard builder run once per row, the loop once
per scene, artifacts and history persist when `save_artifacts` is on.

## 9. Worked examples

`python -m runtime.examples.run_worked_examples` runs four canonical
scenarios with artifacts on disk:

| Example | Row | Seed | Result |
| --- | --- | --- | --- |
| `gyroid` | Infill Pattern Comparisons (FDM) | 29 | QA passes on attempt_01 |
| `planetary_gear` | Planetary Gear Sets (Mechanisms) | 42 | attempt_01 fails, optimizer repairs, attempt_02 passes |
| `injection_molding` | Injection Molding (Injection Molding) | 42 | attempt_01 fails, attempt_02 passes |
| `budget_exhaustion` | Planetary Gear Sets (Mechanisms) | 3 | a stuck renderer burns attempt_01..attempt_03, no winner, all artifacts saved |

## 10. Testing

`tests/test_runtime.py` (50 tests) and `tests/test_worked_examples.py`
(6 tests) cover fingerprints, schemas, the deterministic renderer defect
model, cache round-trips, retry budget and duplicate guard, workflow
build/regenerate, storyboard parity with the knowledge stack, the full
loop (pass-first-try, full repair, budget exhaustion, catastrophic-failure
caps, duplicate skip, artifact persistence, cache reuse), session
determinism, replay from every input type, tamper detection, history
evolution, and the worked examples. Together with the pre-existing suites
the full set stays green: 419 tests, no regressions.
