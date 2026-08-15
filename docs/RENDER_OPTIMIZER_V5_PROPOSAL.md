# Render Optimizer (Phase 5) Proposal

Status: **delivered** (knowledge phase, no runtime wiring)

The Render Optimizer closes the QA feedback loop. Image QA rejects an image;
this stage prescribes exactly what to change - storyboard camera, lighting,
composition, engineering visualization, workflow profile, and prompt phrases -
and projects the scores after the fixes. Everything is deterministic: the
same rejection always produces the same plan.

## Inputs

| Input | Where it comes from |
| --- | --- |
| `EducationalPlan` | Educational Director (Phase 3) |
| `VisualStoryboard` | Visual Intelligence (Phase 2) |
| `CompiledPrompt` | Prompt Compiler (Phase 1) |
| `ImageQualityReport` | Image QA (Phase 4) |

## Output

`OptimizedRenderPlan` - frozen pydantic schema (`OPTIMIZER_VERSION = "1.0.0"`):

- `optimization_actions` - one per fired rule; each names the `QACheck` it
  fixes, the `OptimizationActionKind` (visualization / camera / lighting /
  composition / prompt / workflow / consistency), an instruction, an
  expected gain, the target report score, and the rationale.
- `prompt_mutations` - exact phrase edits against the SDXL compiler's
  templates: `"{distance} shot"`, `"{angle} angle"`, `"{lens} lens"`,
  `"{framing} framing"`, `"{direction} lighting"`, `"{style} style"`,
  `"{rule} composition"`, plus appends (engineering visualization tokens,
  negative-prompt avoidance tokens, palette enforcement). `apply()` is
  total: a REPLACE whose target is missing falls back to an append.
- `workflow_changes` - which ComfyUI profile to switch to (from
  `RenderProfileKey`: macro, diagram, CAD, blueprint, exploded, cutaway,
  transparent, stress, thermal, comparison, hero).
- `camera_changes` / `lighting_changes` / `composition_changes` -
  typed field changes for the storyboard scene.
- `visualization_changes` - `EngineeringVisualizationType` to add or
  replace, with the tokens for the prompt.
- `expected_score_improvement` - the eight projected scores (weighted
  exactly like QA), the delta, and `predicted_pass`
  (overall >= 75, no sub-score < 50, no critical issue left).

## Rule engine

`optimization_rules.py` is pure data: one `OptimizationRule` per QA check
(thirteen), each with deterministic `ActionTemplate`s. A rule fires when
the check has an issue of at least `MIN_TRIGGER_SEVERITY` (major) - critical
issues always fire - or when the score it targets is below
`OPTIMIZATION_FLOOR` (70). Expected gains are conservative (max
`MAX_GAIN_PER_ROUND` = 40 per score per round) so projections stay honest.

Examples:

| Check | First action | Gain |
| --- | --- | --- |
| engineering accuracy | increase engineering visualization (cutaway/exploded) | +12 |
| material correctness | correct material tokens in the prompt | +12 |
| camera suitability | align camera with the planned shot | +12 |
| primary subject visibility | increase subject scale, tighter framing | +12 |
| composition quality | reframe per the planned rule | +12 |
| visual clutter | simplify background | +12 |
| educational effectiveness | switch to the planned teaching visualization | +12 |
| thumbnail strength | stronger hero composition and focal point | +12 |
| scene consistency | enforce material/color palette | +15 |

## Engine loop

`OptimizationEngine` runs up to `MAX_ROUNDS = 3` passes. Each round collects
only actions not already granted (dedupe by check + instruction), simulates
the projected scores, and stops early once `predicted_pass`. In practice one
round suffices for the worked examples; the loop is a safety valve that is
still deterministic.

## Workflow selector

`select_workflow_profile()` maps `EngineeringVisualizationType` (wins) then
`ShotType` to a `RenderProfileKey`, with `hero` as the default so every
scene has a profile. Profiles are static `RenderProfile` data (sampler,
steps, CFG, resolution, negative tokens, LoRA hints, node notes) that the
Phase 1 workflow builder can consume - nothing executes ComfyUI here.

## Consistency guarantees

- `SCORE_WEIGHTS` mirrors Image QA's `_WEIGHTS`; a test asserts they stay in
  lockstep.
- `predicted_pass` re-uses QA's `PASS_THRESHOLD` / `FAIL_FLOOR`.
- Plans are frozen, `extra="forbid"`, JSON round-trippable.
- Existing phases are untouched: 302 pre-existing tests still pass.

## Architecture

```
                  Knowledge Base (CSV)
                         |
                  Knowledge Director
                         |
                  Educational Director ---------> EducationalPlan
                         |
                  Visual Intelligence -----------> VisualStoryboard
                         |
                  Storyboard (scene specs)
                         |
                  Prompt Compiler --------------> CompiledPrompt
                         |
                  Workflow Builder
                         |
                  ComfyUI render
                         |
                  Vision pipeline --------------> GeneratedImageMetadata
                         |
                  Image QA (13 critics) --------> ImageQualityReport (accept / reject)
                         | reject
                         v
                  +-----------------------------+
                  | Render Optimizer  <----------+---- EducationalPlan
                  |   rules + engine             |---- VisualStoryboard
                  |   + prompt mutator           |---- CompiledPrompt
                  |   + workflow selector        |---- ImageQualityReport
                  +-----------------------------+
                         |
                         v
                  OptimizedRenderPlan
                   (actions, mutations, workflow,
                    camera, lighting, composition,
                    visualization, projected scores)
                         |
                         +----------------------> back into storyboard + compiler
```

## Deliverables

1. Optimization schema (`optimization_models.py`)
2. Optimization engine (`optimization_engine.py`)
3. Rule engine (`optimization_rules.py`)
4. Prompt mutator (`prompt_mutator.py`)
5. Workflow selector (`workflow_selector.py`)
6. Render profiles (`render_profiles.py`)
7. Worked examples (`examples/gyroid.py` clean pass, `examples/planetary_gear.py`
   full repair, `examples/injection_molding.py` targeted repair)
8. Unit tests (`tests/test_render_optimizer.py`, 61 tests)
9. Architecture diagram (above)

## Verification

- 363 tests pass (302 pre-existing + 61 new).
- `ruff check` clean across `knowledge`, `tests`, and both CSV scripts.
- Examples: gyroid -> 0 actions / predicted pass unchanged; planetary S2 ->
  17 actions, predicted 94.5 (+17.8) pass; injection S2 -> 8 actions targeted
  at educational + clutter, predicted 92.3 (+11.4) pass.