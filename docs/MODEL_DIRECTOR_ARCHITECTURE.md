# Model Director (Phase 10) — Universal Multi-Model Generation Engine

PR1ME stops being bound to a single image generator. A deterministic
Model Director sits between the AI Director and the Prompt Compiler: for
every scene it picks the best image model **and** the best video model
from the registry, then compiles a complete backend profile (sampler,
scheduler, CFG, steps, resolution, aspect ratio, VAE, LoRAs, ControlNet /
IPAdapter / depth / segmentation, upscaler, refiner, animation backend)
into a `SceneModelPlan`. Backend-specific workflow code lives only in the
backend adapters (`runtime/backends/`); the same brief renders the same
film on any supported model family by changing only the compiled profile.

Like every other knowledge module, the Model Director is **not an LLM**:
no randomness, no runtime guessing, no model-specific strings outside the
adapters and the knowledge tables.

```
AI Director → DirectorOutput (the creative brief)
    ↓
Model Director (NEW) → ModelOutput: per-scene SceneModelPlan
    ↓
Prompt Compiler → CompiledPrompt
    ↓
Workflow Builder → adapt_backend(model plan) → BackendWorkflow
    ↓
Render Loop → render → QA → … on repeated failure, deterministic
              fallback strategy may switch the image model
```

## The contract

**Input** — `DirectorOutput` (the AI Director's creative brief).

**Output** — `ModelOutput` (`knowledge/model_director/model_profiles.py`):

- `version` (`MODEL_DIRECTOR_VERSION = "10.0.0"`), `topic`, `scene_count`,
  `summary` (one deterministic line: models, predicted QA / retry range)
- one `SceneModelPlan` per scene carrying the compiled `ModelProfile`:
  - image model + video model + animation backend
  - sampler / scheduler / CFG / steps / resolution / aspect ratio / VAE
  - LoRAs, ControlNet, IPAdapter, depth strategy, segmentation strategy
  - upscaler, refiner, `quality_target` (fast / balanced / premium)
  - `render_profile` (the genre, chosen by the render optimizer) and
    negative tokens (from the render profile)
  - predicted QA score, success probability, retry count, VRAM, time
  - `rationale` — the deterministic reasons for the choice

**Guarantees** — identical brief → identical `ModelOutput`; every plan is
compatibility-checked before it leaves the director (a plan with an
unsupported parameter is a hard error, not a silent fallback); every field
is JSON-serializable for checkpoints / fingerprints / resume.

## Module responsibilities

| Module | Owns |
| --- | --- |
| `model_registry.py` | The single source of truth for every model's capability record (`ModelSpec`): kind, capability axes (photoreal / diagram / macro detail / engineering / adherence / motion), VRAM, speed, reliability, steps range, and the exact supported parameter sets. Future models join through `ModelRegistry.register()` — nothing else changes |
| `backend_rules.py` | Per-family default backend parameters (CFG, sampler, scheduler, VAE, resolution, aspect ratio) and the `QualityTarget` tiers (fast / balanced / premium) |
| `compatibility.py` | `check_model`: the guardrail that verifies a proposed parameter set against the registry before anything reaches an adapter |
| `render_profile_selector.py` | Genre selection — reuses `knowledge.render_optimizer.select_workflow_profile` (no duplicated rules), quality target per scene, target settings (steps multiplier / upscaler / refiner per tier) |
| `quality_predictor.py` | Predicted QA = weighted capability average (scene axis + universal adherence) scaled by reliability; video quality, success probability, retry count |
| `performance_predictor.py` | Predicted VRAM (scaled by resolution area) and time (steps × per-step cost × area factor) |
| `sampler_selector.py` / `scheduler_selector.py` | Sampler + scheduler + VAE per model and profile, clamped into the supported sets |
| `lora_selector.py` | The LoRA set per model family (SDXL family uses the render profile's LoRAs) |
| `controlnet_selector.py` | ControlNet per shot strategy (depth / canny / lineart), IPAdapter for hero scenes, depth + segmentation strategies |
| `fallback_strategy.py` | The deterministic switch rule: `SWITCH_AFTER_ATTEMPTS = 2` consecutive failures and fallback predicted QA ≥ current + `MIN_IMPROVEMENT = 3.0` |
| `model_selector.py` | `ModelDirector.direct` orchestration only; `replan_for_model` — the "same brief, new backend" recompile used by the render loop |
| `model_profiles.py` | The frozen schemas (`ModelProfile`, `SceneModelPlan`, `ModelOutput`) |

## How a scene is compiled

1. **Genre** — `select_render_profile(shot_type, visualization_type)`
   reuses the render optimizer's workflow profile (the knowledge base
   owns genres; no rule is duplicated).
2. **Image model** — every image model is scored
   `expected_qa(shot) × (1 + 0.04 × (importance − 3))`; candidates are
   filtered by the VRAM budget when one is set; the preferred model breaks
   exact ties, registry order breaks the rest. A clearly better model is
   never overruled by the default.
3. **Video model** — the video model with the best predicted motion
   quality wins.
4. **Quality target** — hero / thumbnail scenes and importance ≥ 4 →
   `premium`; visual budget ≤ 4 → `fast`; otherwise `balanced`.
5. **Backend parameters** — samplers, schedulers, VAE, CFG, steps,
   resolution and aspect ratio come from the model's registry record +
   the family's backend rules + the target tier (the SDXL family keeps the
   render profile's CFG / sampler / LoRAs so the render optimizer stays
   in charge of its own family).
6. **Conditioning** — ControlNet follows the shot strategy
   (inspection shots → depth, comparison shots → canny, diagram shots →
   lineart), clamped into the model's supported set; IPAdapter activates
   for hero scenes (models that support it); depth / segmentation follow
   the per-model defaults.
7. **Verification** — `check_model` must return compatible, then the
   predictions (QA, success probability, retries, VRAM, time) are
   computed and the `SceneModelPlan` is sealed.

## Predictions

- **QA**: `(adherence × 1.0 + scene_axis × 0.6) / 1.6`, scaled by
  `0.85 + 0.15 × reliability`. The scene axis is keyed by shot type:
  macro shots lean on `macro_detail`, hero shots on `photoreal`,
  engineering shots (cross-section, cutaway, exploded, CAD, isometric,
  orthographic) on `engineering`, diagram shots (blueprint, annotated
  diagram, wireframe, process / manufacturing sequence) on `diagram`,
  comparison splits on engineering at 0.4.
- **VRAM**: `base_vram × (0.75 + 0.25 × area / 1011712)`; a VRAM budget
  shrinks the resolution until it fits (or picks the smallest).
- **Time**: `steps × time_per_step × (0.6 + 0.4 × area / 1011712)`.
- **Success / retries**: tiered from the predicted QA and reliability.

## Deterministic model switching

The render loop (`runtime/render_loop.py`, directed mode) feeds QA
failures back to the optimizer. After `SWITCH_AFTER_ATTEMPTS` consecutive
QA failures it consults `fallback_strategy`:

```
current model failed QA ≥ 2 times in a row
AND next_fallback(current) predicts QA ≥ current + 3.0
        → replan_for_model(current_directive, fallback)
        → record a MODEL_SWITCHED attempt (never consumes render budget)
        → re-render with the recompiled backend workflow
```

The fallback chain is deterministic: the preferred model first, then
registry order. The switch is recorded as a `model_switched` attempt
(excluded from the render budget and `attempts_used`), and the pipeline
metrics surface `model_switches` and the per-scene image models. The
legacy (undirected) loop path never switches — Phase 6 behavior is
unchanged.

## The backend adapters (`runtime/backends/`)

`BackendWorkflow` is a strict superset of the legacy Phase-6 workflow
shape (`workflow_version`, `profile`, `sampler`, `steps`, `cfg`,
`resolution`, `loras`, `negative_tokens`, `positive_prompt`,
`negative_prompt`, `nodes`), extended with `backend`, `scheduler`,
`aspect_ratio`, `vae`, `controlnet`, `ip_adapter`, `depth_strategy`,
`segmentation_strategy`, `upscaler`, `refiner`, `animation_backend`,
`quality_target` — so render requests, fingerprints, and the renderer
protocol needed no changes.

- `ADAPTER_BY_FAMILY` dispatches `flux → FluxAdapter`, `sdxl → SDXLAdapter`,
  `qwen → QwenAdapter`, `gpt_image → GPTImageAdapter`, `wan → WANAdapter`,
  `ltx → LTXAdapter`, `cogvideo → CogVideoAdapter`,
  `animatediff → AnimateDiffAdapter`; `GenericAdapter` serves HiDream and
  future registry models.
- `adapt_backend(prompt, plan)` is the single entry point; no other
  runtime module carries backend-specific strings.

## The pipeline (fifteen stages)

`knowledge_load → educational_director → ai_director → visual_intelligence
→ model_director → prompt_compiler → workflow_builder → render_loop →
voice → subtitles → video_assembly → video_render → thumbnail → metadata →
publisher`. The `model_director` stage persists a `ModelOutput` artifact;
the `workflow_builder` and `render_loop` stages consume the per-scene
plans; the report surfaces the compiled image models and any switches.
