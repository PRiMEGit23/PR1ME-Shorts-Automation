# Knowledge Base V2 — Visual Architecture Proposal

**Status:** Proposal only. No source files, batch files, or the CSV were modified.
**Scope:** Redesign of the visual section only. Script, SEO, metadata, and taxonomy columns are untouched.
**Target:** A model-agnostic visual specification consumed by a separate Prompt Compiler subsystem (SDXL, FLUX, Qwen Image, GPT Image, HiDream, future models).

---

## 1. Problems Found

Measured against the current `assets/knowledge_base.csv` (400 rows, 2,000 scene shots, 400 thumbnails).

### P1. Prompts are stored, not specified
`image_prompt_pack_json` holds finished natural-language prompts. **100% of the 2,000 scene prompts begin with one of four photographic prefixes** (`"photograph of"`, `"studio photograph of"`, `"macro photograph of"`, `"diagram-style shot"`). The knowledge base is therefore already bound to photographic SDXL output: a FLUX or GPT Image adapter inherits SDXL sentence patterns, camera-language quirks, and modality assumptions that were never semantically declared.

### P2. Boilerplate pollution (compiler-level tokens baked into data)
Occurrences across the CSV:

| phrase | count |
|---|---|
| `studio key` | 1,396 |
| `diagram-style` | 1,554 |
| `clean engineering visualization` | 906 |
| `engineering lab` | 1,028 |
| `ultra sharp` | 795 |
| `high detail` | 652 |
| `dark workshop` | 631 |
| `fade` / `cut` | 535 / 3,860 |
| `cinematic` | 433 |
| `modern engineering lab` | 251 |

These are style tokens, not semantics. They are repeated verbatim thousands of times, inflate the artifact (~5.6 MB), and make a style change impossible without touching 400 curated topics.

### P3. No visual hierarchy
Scenes carry `objects` as bare noun lists (`["printed cubes", "0.12 mm sample", "0.3 mm sample"]`). There is no Primary/Secondary/Background/Focus structure. The `foreground` field in `scene_plan_json` is auto-generated as `"Subject: <objects[0]>"` — a fake field that adds nothing. SDXL prompt packs with three co-equal nouns routinely collapse into composites or drop one object entirely.

### P4. Camera semantics are implicit prose
- `camera` is a full sentence ("macro side-by-side of parts printed at 0.12, 0.2, and 0.3 mm"), not data. A compiler cannot reason about distance/angle/framing; it can only pass text through.
- `lens_for()` keyword mapping is lossy: **1,066 of 2,000 shots (53%) fall back to the default `35mm f/2`**; only **1** shot ever lands on `50mm f/1.8` despite "orbit"/"turntable" shots being common. The word `macro` alone does not trigger the macro lens unless "close-up" also appears.

### P5. Category defaults are unused prose
`camera_language`, `lighting_style`, `color_palette`, `composition_style`, `render_style`, `environment`, `motion_plan`, `animation_notes` each have only **~12 distinct values across 400 rows** (one prose blob per category) and are mostly never consumed downstream. `render_notes` bakes target-specific text into the KB (`"vertical 9:16 at 1080x1920, high detail, physically accurate materials, no text in image"`).

### P6. Model-bound negatives
`negative_prompt` is the identical global string in **100% of rows**; `thumbnail_negative_prompt` is a second hand-written SDXL-style list. The KB should store *what must not exist* semantically; each model's negative syntax belongs to the compiler.

### P7. Triple duplication
Subject/lighting/composition content appears in `scene_plan_json`, `visual_spec_json`, and `image_prompt_pack_json`. Thumbnail content appears in `thumbnail_visual_spec`, `thumbnail_prompt`, and `thumbnail_negative_prompt`. `visual_spec_json` is built from **scene 1 only** (subject = `scenes[0].objects[0]`, camera from scene 0) while pretending to describe the whole row.

### P8. Rendering-target text baked at build time
`thumbnail_prompt` is pre-assembled with `THUMBNAIL_SUFFIX` (`"ultra sharp, high detail, strong subject contrast, bold readable composition, professional YouTube thumbnail style, vertical 9:16"`) by `build_knowledge_csv.py`. Swapping image models requires a rebuild and rewrites of curated data.

### P9. No consistency mechanism
There is no identity anchor across scenes: the same nozzle, part, or bench is described differently in every scene. There are no consistency tags, color anchors, or reference subjects, so character/object consistency (already weak in single-image models) is unmanaged across the 5-shot video timeline.

### P10. Missing semantics the compiler needs
No scale reference, no depth-of-field intent, no per-scene motion vector, no transition hints beyond `cut`/`fade`, no scene importance, no thumbnail-candidate flag, no surface finish or manufacturing-detail fields (engineering accuracy currently lives inside prose prompts where it is unvalidated).

### P11. Engineering accuracy is unenforced
Because manufacturing facts are embedded in prose, the validator cannot check them. "Extruding molten PLA" vs "pouring liquid plastic" are both expressible; nothing prevents AI-fantasy terminology from shipping.

---

## 2. Missing Fields

Per-scene, the current data has none of these as structured fields:

- Primary Subject, Secondary Subjects, Subject Hierarchy (roles + focus object)
- Action (what physically happens), Engineering Goal, Teaching Goal (partially present as prose `goal`/`teaching_point` — keep, make formal)
- Visual Focus, Camera Distance, Camera Angle, Lens, Framing, Composition
- Foreground / Midground / Background, Environment
- Materials, Surface Finish, Manufacturing Details, Visible Geometry
- Lighting Direction, Lighting Style, Color Palette, Mood
- Motion (type/path/speed/loop), Depth of Field, Scale Reference
- Objects to Avoid (semantic excludes), Negative Elements
- Consistency Tags, Branding Tags
- Transition Hint, Scene Importance, Thumbnail Candidate
- Modality (photoreal / diagram / macro-inspection / cross-section / schematic / exploded-view / split-compare) — the single most important missing discriminator
- Text-slot contract for thumbnails (string, position, max chars, contrast)

Missing at row level: a stable world/identity anchor (`world_id`) so the 12 category prose blobs become one compiled World Profile instead of 400 duplicated prose cells.

---

## 3. Redundant Fields

Remove or demote to derived (regenerated by the compiler):

| field | verdict | replacement |
|---|---|---|
| `image_prompt_pack_json.positive_prompt` | remove | compiler output (derived artifact) |
| `image_prompt_pack_json.negative_prompt` | remove | compiler output |
| scene `prompt` (curated) | remove | `visual` spec |
| scene `shot` | remove | discrete camera fields |
| scene `lighting` / `background` (one-word prose) | remove | structured lighting + depth |
| scene `objects` | remove | subject hierarchy |
| `scene_plan_json.foreground` | remove | real depth plan |
| `visual_spec_json` | remove | `visual_architecture_json` |
| `thumbnail_prompt` + `thumbnail_negative_prompt` | remove | compiled from thumbnail spec |
| `negative_prompt` (row) | remove | semantic `exclude` + compiler model negatives |
| `camera_language`, `motion_plan`, `animation_notes`, `render_notes`, `style_tokens` | remove | World Profile (compiler-side) |
| `lighting_style`, `color_palette`, `composition_style`, `render_style`, `environment`, `materials` (row) | keep, but as structured JSON with enum values | World Profile + per-row override |

Keep untouched: `topic`, taxonomy, `core_question`, `learning_objective`, `engineering_summary`, `real_world_application`, `common_misconceptions`, `teaching_strategy`, `script`, `text_overlay`, all SEO columns, `references_json`, `fact_check_notes`, `scene_count`, `scene_plan_json` (trimmed), `duration`.

---

## 4. New Field Structure

New column set (visual section only):

```
visual_world_id              text           -> world profile reference, e.g. "pr1me_lab_v1"
visual_architecture_json     JSON           -> full row spec: world overrides, scenes[], thumbnail
scene_plan_json              JSON (V2)      -> timeline fields only: scene_id, goal, teaching_point,
                                               duration, transition_hint, importance, thumbnail_candidate,
                                               text_overlay_ref
```

The old columns remain only as a *compatibility view* during migration (§7), produced by the compiler, never curated.

**Guiding rule:** the KB stores `WHAT exists` (entities, geometry, materials, manufacturing, hierarchy, actions) and `HOW the story is shot` (camera, composition, lighting, motion). It stores **nothing** about rendering quality, resolution, realism, or model syntax. Those live in the Prompt Compiler.

---

## 5. Example Row Conversion

Source row: **Layer Height** (row 1 of the current CSV), scene S1 + thumbnail.

### 5.1 Today (abridged, actual data)

`scene_plan_json[0]`:
```json
{
  "scene_id": "S1",
  "goal": "Hook: three layer heights",
  "teaching_point": "Layer height controls visible surface ridges",
  "camera": "macro side-by-side of parts printed at 0.12, 0.2, and 0.3 mm",
  "lens": "100mm f/2.8 macro",
  "composition": "Centered subject, rule of thirds for screen elements, generous negative space for overlays",
  "foreground": "Subject: printed cubes",
  "background": "dark bench blur",
  "lighting": "raking side light",
  "motion": "slow pan across the three surfaces",
  "objects": ["printed cubes", "0.12 mm sample", "0.3 mm sample"],
  "transition": "cut",
  "duration": 5.0
}
```

`image_prompt_pack_json[0].positive_prompt` (actual):
```
macro photograph of three 3D printed cubes with different layer heights showing smooth to ridged surfaces, raking side light, dark bench, macro side-by-side of parts printed at 0.12, 0.2, and 0.3 mm, raking side light, Centered subject, rule of thirds for screen elements, generous negative space for overlays, clean technical render, modern engineering lab, precise machined surfaces, subtle depth of field
```

Note the artifacts: duplicated "raking side light", the composition default pasted into a macro shot, category style tokens, and no hierarchy.

### 5.2 V2 (proposed)

`scene_plan_json` (timeline only):
```json
{
  "scene_id": "S1",
  "goal": "Hook: three layer heights",
  "teaching_point": "Layer height controls visible surface ridges",
  "duration": 5.0,
  "transition_hint": { "type": "cut", "direction": "in" },
  "importance": 4,
  "thumbnail_candidate": false,
  "text_overlay_ref": 0
}
```

`visual_architecture_json.scenes[0]` (the semantic spec):
```json
{
  "scene_id": "S1",
  "modality": "photoreal",
  "primary_subject": {
    "entity": "three FDM-printed PLA calibration cubes",
    "description": "side-by-side cubes printed at 0.12, 0.20, and 0.30 mm layer height",
    "state": "freshly printed, unwashed, on the build plate",
    "materials": ["PLA"],
    "surface_finish": ["smooth at 0.12 mm", "visible ridges at 0.30 mm"],
    "manufacturing_details": ["FDM extrusion", "0.4 mm brass nozzle", "layer lines parallel to the build plate"],
    "visible_geometry": ["square cross-section", "flat top surface", "step ridges on the 0.30 mm cube"]
  },
  "secondary_subjects": [],
  "background": { "environment": "workbench", "depth": "shallow", "detail": "dark bench blur" },
  "focus_object": "the 0.20 mm cube",
  "action": "none",
  "camera": { "distance": "macro", "angle": "slightly_low", "lens": "100mm macro", "framing": "tight", "height": "table" },
  "composition": { "rule": "rule_of_thirds", "emphasis": "surface texture", "negative_space": "overlay_top", "note": "three cubes in a row, surfaces facing the lens" },
  "depth": { "foreground": null, "midground": "cubes", "background": "bench blur", "dof": "shallow" },
  "lighting": { "direction": "side", "style": "raking", "practical_sources": ["bench lamp"], "key_color": "neutral" },
  "palette": { "base": "dark slate", "accent": "natural PLA tones", "note": "cube colors must read as real filament" },
  "mood": "clinical",
  "motion": { "type": "pan", "path": "left to right across the surfaces", "speed": "slow", "loop": false },
  "scale_reference": { "entity": "US quarter coin", "size": "25 mm", "placement": "behind the cubes" },
  "exclude": ["people", "hands", "text", "logos", "glossy reflections on the cubes"],
  "consistency_tags": ["layer_height_cubes", "pr1me_lab_bench"],
  "branding_tags": ["pr1me_orange_overlay_zone"]
}
```

### 5.3 Thumbnail

`visual_architecture_json.thumbnail` (abridged):
```json
{
  "modality": "photoreal",
  "primary_subject": {
    "entity": "three FDM-printed PLA calibration cubes",
    "description": "smooth to heavily ridged across 0.12 / 0.20 / 0.30 mm layer heights",
    "state": "dry, on a dark bench"
  },
  "background": { "environment": "workbench", "depth": "shallow" },
  "focus_object": "the ridged 0.30 mm cube",
  "composition": { "rule": "center_row", "emphasis": "surface contrast", "note": "bold readable from 60% zoom" },
  "text_slot": { "string": "LAYER HEIGHT", "position": "upper_third", "max_chars": 28, "contrast": "high" },
  "scale_reference": { "entity": "ruler", "placement": "bottom edge" },
  "camera": { "distance": "macro", "angle": "slightly_low", "lens": "100mm macro", "framing": "tight" },
  "lighting": { "direction": "side", "style": "raking" },
  "palette": { "base": "dark slate", "accent": "natural PLA tones" },
  "mood": "comparative",
  "motion": "static",
  "exclude": ["people", "hands", "watermarks"],
  "consistency_tags": ["layer_height_cubes"]
}
```

The SDXL prompt `"macro photograph of three 3D printed cubes ..., ultra sharp, high detail, strong subject contrast, professional YouTube thumbnail style, vertical 9:16"` is no longer stored anywhere — it is what the compiler emits for SDXL and a different sentence for GPT Image.

---

## 6. Migration Strategy

**Phase 0 — Freeze and tag.** Tag the current artifact `knowledge_base_v1.0.0`; commit the CSV as-is. The pipeline keeps running on V1 during the whole migration (no production freeze).

**Phase 1 — Vocabulary + compiler prototype.** Implement `knowledge/visual_architecture.py` (enums, dataclasses, JSON schema, validator). Implement a prototype Prompt Compiler that consumes **V1 data** (scene plan + prompt pack) and emits model prompts through templates. This proves the compiler pipeline before the data changes, and gives an A/B baseline: current CSV vs compiled-from-V1.

**Phase 2 — Structural scaffolding.** Extend `build_knowledge_csv.py` to emit `visual_world_id` + `visual_architecture_json` alongside the existing columns (dual-write). The V2 field starts as an **auto-conversion** of V1 (lossy, marked `derived: true`), so the CSV is never without a valid V2 spec.

**Phase 3 — Curated refinement per batch.** Convert batch files topic-by-topic: replace each scene's `shot`/`motion`/`lighting`/`background`/`objects`/`prompt` with a structured `visual` dict. 50 batches × 8 topics; each converted batch goes through the existing QA gate extended with V2 validation. Auto-converted rows are replaced by curated ones (`derived: false`).

**Phase 4 — Cutover.** When ≥95% of rows are `derived: false`, flip the compiler default to V2 input. Delete V1 prompt columns from the contract (schema v2.0.0) after the compatibility view has been green for one release cycle.

Estimated effort: Phases 1–2 one developer-week; Phase 3 parallelizable (50 small PRs); Phase 4 one day.

---

## 7. Backward Compatibility Plan

1. **Dual-write:** during Phases 2–3 the CSV carries both old and new visual columns. Any consumer (ComfyUI stage, thumbnail stage) is untouched.
2. **Compatibility view generator:** `build_compat_view.py` regenerates the V1 columns (`image_prompt_pack_json`, `thumbnail_prompt`, `thumbnail_negative_prompt`, `negative_prompt`) **from V2 via the compiler** — deterministic, so the V1 columns become derived artifacts instead of curated data. Consumers can migrate at their own pace.
3. **Validator dual mode:** `validate_knowledge_csv.py` accepts `SCHEMA_VERSION` env: `v1` (legacy checks), `v2` (new checks), `both` (default during migration). Header versioning via a `schema_version` row-level column.
4. **Semantic versioning:** the CSV gains `schema_version`; batch files gain a `VISUAL_ARCH_VERSION` constant. The compiler pins the minimum arch version it can consume.
5. **Rollback:** because batches remain the source of truth and the CSV is a derived artifact, reverting to v1 is `git revert` of the build/compiler code, not a data migration.

---

## 8. Prompt Compiler Interface

The compiler is a **deterministic, non-LLM** subsystem. Same spec in → same prompt out.

```
Input:
  VisualArchitecture   (from visual_architecture_json, resolved against world profile)
  WorldProfile         (per visual_world_id: environment, palette, lighting base, branding tags)
  ModelProfile         (per model family: syntax rules, token caps, negative support, guidance)
  TemplateBundle       (per model family: modality templates, camera/lighting phrase tables)

Output (per scene + thumbnail):
  { "prompt": str,
    "negative_prompt": str | null,
    "metadata": { "model": "sdxl", "compiler_version": "1.4.0",
                  "source": { "topic": "...", "scene_id": "S1", "world_id": "..." },
                  "guidance": float, "steps": int, "size": [1080, 1920] } }

Contract:
  - deterministic: pure functions over (spec, profile, bundle), no RNG, no LLM
  - versioned: compiler_version in every output; template bundles are code, not data
  - fail closed: unknown enum value -> structured error, never a guessed prompt
  - traceability: every prompt records its spec source (row, scene, field)
```

Example ModelProfile deltas:

| model | positive style | negatives | token cap | guidance |
|---|---|---|---|---|
| SDXL | photography prefix, quality tokens | full negative list | ~75 tokens | 7.0 |
| FLUX.1-dev | dense natural sentence, no quality spam | ignored / guidance-distilled | ~120 tokens | 3.5 |
| GPT Image | structured paragraph + constraints | folded into positive | ~400 chars | n/a |
| Qwen Image | prompt list style | per-item negatives | ~200 tokens | n/a |
| HiDream | SDXL-compatible | list | ~75 tokens | 7.0 |

Quality/rendering tokens (`8k`, `ultra detailed`, `photorealistic`, `masterpiece`, `cinematic`, resolution, aspect) exist **only** in ModelProfiles and TemplateBundles.

---

## 9. VisualArchitecture Schema

Formal contract (JSON Schema outline; implemented as dataclasses in `knowledge/visual_architecture.py`).

```
visual_architecture_json:
  version: "2.0"                                  # arch schema version
  world_id: string                                # -> WorldProfile lookup
  modality: enum                                  # photoreal | diagram | macro_inspection |
                                                  # cross_section | schematic | exploded_view |
                                                  # split_compare
  scenes: [ Scene, ... ]                          # 4-6, matches scene_count
  thumbnail: Thumbnail

Scene:
  scene_id: "S1"
  modality: enum                                  # overrides row default
  primary_subject: Subject                        # required
  secondary_subjects: [ Subject ]                 # 0-3
  subject_hierarchy: { primary: string, secondary: [string], background: string,
                       focus_object: string }     # explicit, validated non-empty
  action: string                                  # what physically happens ("extruder deposits
                                                  # molten PLA through 0.4 mm brass nozzle")
  engineering_goal: string                        # from curated "goal"
  teaching_goal: string                           # from curated "teaching_point"
  visual_focus: string                            # what the eye lands on
  camera: { distance: enum(macro|close|medium|wide|establishing),
            angle: enum(eye|slightly_low|low|high|overhead|dutch),
            lens: enum(24mm|35mm|50mm|85mm|100mm_macro),
            framing: enum(tight|medium|loose|subject_center|subject_left|subject_right|rule_of_thirds),
            height: enum(table|eye|overhead) }
  composition: { rule: enum, emphasis: string, negative_space: enum(none|overlay_top|
                 overlay_left|overlay_bottom), note: string }
  depth: { foreground: string|null, midground: string, background: string,
           dof: enum(shallow|medium|deep|full) }
  environment: string                             # resolves against world profile if absent
  materials: [string]                             # enum against material registry
  surface_finish: [string]                        # enum (smooth, machined, anodised, ridged, matte...)
  manufacturing_details: [string]                 # free-form, term-validated (see §Accuracy)
  visible_geometry: [string]                      # what geometry must be legible
  lighting: { direction: enum(key|side|rim|back|practical|overhead),
              style: enum(studio|raking|task|softbox|hard_key|high_bay|glow),
              practical_sources: [string], key_color: string }
  color_palette: { base: string, accent: string, note: string }
  mood: string                                    # small vocabulary in world profile
  motion: { type: enum(static|pan|push_in|orbit|zoom|tilt|track|turntable|sweep),
            path: string, speed: enum(slow|medium|fast), loop: bool }
  depth_of_field: enum                            # duplicate-free: use depth.dof only
  scale_reference: { entity: string, size: string, placement: string } | null
  objects_to_avoid: [string]                      # semantic, human-readable
  negative_elements: [string]                     # same as objects_to_avoid (alias, single source)
  consistency_tags: [string]                      # identity anchors across scenes
  branding_tags: [string]                         # channel-level anchors
  transition_hint: { type: enum(cut|fade|wipe|dissolve|none), direction: string|null }
  scene_importance: int(1-5)
  thumbnail_candidate: bool

Subject:
  entity: string                                  # what it is
  description: string                             # specific, geometric
  state: string                                   # condition/phase during this scene
  materials: [string]
  surface_finish: [string]
  manufacturing_details: [string]
  visible_geometry: [string]

Thumbnail:
  modality: enum
  primary_subject: Subject
  secondary_subjects: [Subject]
  background: { environment: string, depth: enum }
  focus_object: string
  composition: { rule: enum, emphasis: string, note: string }
  text_slot: { string: string, position: enum(upper_third|center|lower_third),
               max_chars: int, contrast: enum(high|medium) }
  camera / lighting / color_palette / mood / motion("static")
  exclude: [string]
  consistency_tags: [string]
```

Validation rules (validator additions):
- every enum value must exist in the vocabulary registry
- `subject_hierarchy` names must reference defined subjects
- every `manufacturing_details` term passes the per-modality term registry (see §Accuracy)
- `thumbnail_candidate` allowed on at most 2 scenes per row
- scene `modality` must be compatible with row modality unless explicitly overridden
- `exclude`/`negative_elements` deduplicated, non-empty only when semantically required

### Engineering-accuracy mechanism
`knowledge/engineering_terms.py` maps modality → allowed verbs/nouns, e.g.:

- FDM: `extruding`, `depositing`, `consolidating`, `layer`, `nozzle`, `filament`, `stepper` — forbidden: `pouring liquid`, `melting puddle`, `glowing plasma`
- Resin: `curing`, `masking`, `UV`, `build plate` — forbidden: `baking`, `hardening in air`
- CNC: `milling`, `turning`, `tool engagement`, `chip`, `spindle` — forbidden: `carving by hand`
- Diagrams: `dimension lines`, `cutaway`, `section plane`, `vector arrows` — forbidden: `photographic shadows`, `glow`

The compiler is forbidden from inventing manufacturing terms; the validator rejects unknown or forbidden terms at build time. This is the concrete guarantee that V2 "reflects real engineering rather than AI fantasy".

---

## 10. WorkflowBuilder Schema

`workflowbuilder` consumes (row, VisualArchitecture, compiled prompts) and emits the per-video shot timeline that the ComfyUI/assembly stages execute.

```
workflow_json:
  workflow_id: string
  video_id: string
  canvas: { width: 1080, height: 1920, fps: 30 }
  shots: [ Shot, ... ]            # one per scene, ordered

Shot:
  shot_id: "shot_001"
  scene_id: "S1"
  image_spec_ref: "scenes[0]"     # pointer into visual_architecture_json
  prompt_ref: { model: "sdxl", compiled_by: "1.4.0" }
  duration_seconds: 5.0
  motion: { technique: enum(static|pan|push_in|orbit|turntable|tilt|track|zoom),
            vector: [dx, dy] | null, speed: enum, loop: bool,
            keyframes: [ {t: 0.0, zoom: 1.0, x: 0.0}, {t: 1.0, ...} ] }
  transition_in: { type: enum(cut|fade|wipe|dissolve), duration: 0.0 }
  transition_out: { type: enum, duration: 0.0 }
  overlay_slots: [ { kind: enum(text|callout|arrow|badge),
                     content_ref: "text_overlay[1]",
                     zone: enum(upper_third|center|lower_third),
                     timing: "0.5-4.5" } ]
  importance: int(1-5)            # drives edit pacing and render priority
  consistency_refs: [string]      # -> IPAdapter/ControlNet reference chaining
  thumbnail_candidate: bool       # if true, this shot's first frame is the cover candidate
```

Builder rules:
- `thumbnail_candidate` shots are rendered at higher steps/CFG with the thumbnail spec
- `consistency_refs` shared across shots form one reference chain (shot 1 image conditions shots 2–5)
- `transition_hint` from the arch spec maps to transition_in/out defaults
- `overlay_slots` derive from `text_overlay` + `negative_space`/`text_slot` contracts so text never covers the focus object

---

## 11. ComfyUI Mapping

The ComfyUI stage receives compiled prompts + WorkflowBuilder output and assembles graphs.

| Spec element | ComfyUI graph element |
|---|---|
| model family | `CheckpointLoaderSimple` (sdxl / sd3 / flux) |
| compiled positive | `CLIPTextEncode` (positive) |
| compiled negative | `CLIPTextEncode` (negative); FLUX → empty/ignored |
| modality | template-selected LoRA stack: photoreal → product-photo LoRA; diagram/schematic → technical-illustration LoRA; exploded_view → CAD LoRA |
| consistency_tags | `IPAdapterApply` chained from shot-1 latent/VAE-encoded image (reference chain) |
| composition.rule / framing | optional `ControlNet` (depth or lineart from a primitive placeholder) to lock layout |
| lighting direction | model-profile tokens + optional lighting LoRA |
| color_palette | prompt tokens + `ColorMatch`/grading node if palette deviates from world profile |
| scale_reference | extra subject token + optional measurement overlay node (post) |
| motion | shot-1 frame as first frame of `AnimateDiff` / video model (SVD/FLUX video); keyframes from workflow motion |
| transition_hint | `VideoCombine` cut/fade between shot clips |
| thumbnail_candidate | dedicated KSampler pass: higher steps/CFG, thumbnail spec, first-frame export |
| exclude / negative_elements | merged into negative prompt (SDXL family) |
| canvas | `EmptyLatentImage` 1080x1920 |

Determinism: seeds derived from `(topic, scene_id, compiler_version)` so re-renders are reproducible.

---

## 12. Future FLUX Mapping

- **Prompt form:** FLUX.1-dev is guidance-distilled; long comma lists and quality spam hurt it. The compiler's FLUX profile emits one dense natural-language paragraph (subject → hierarchy → action → geometry → materials → lighting → mood), 60–120 tokens, no `8k`/`masterpiece` tokens.
- **Negatives:** FLUX.1-dev ignores classic negatives; the compiler folds `exclude`/`negative_elements` into the positive as explicit prohibitions ("without people, hands, or text").
- **Parameters:** `cfg` ~3.5 for dev (or `guidance` distilling), `steps` 28–50; FLUX.1-schnell → 4–8 steps.
- **Consistency:** FLUX Kontext / Redux for image-conditioned generation replaces the IPAdapter chain from the SDXL path.
- **Video:** FLUX video models consume the same shot-1 frame + `motion` keyframes from the WorkflowBuilder; no KB change.
- **Cutover cost:** zero data changes — only a new `ModelProfile` + `TemplateBundle` (a few hundred lines of compiler code) and a ComfyUI graph template.

---

## 13. Future GPT Image Mapping

- **Prompt form:** GPT Image (API/chat) takes conversational text. The compiler's GPT profile emits a structured paragraph per shot: "A macro photograph of three FDM-printed PLA calibration cubes at 0.12, 0.20, and 0.30 mm layer heights, smooth to ridged surfaces, lit by a raking bench lamp on a dark workbench..." followed by a fixed constraints sentence built from `exclude`.
- **No negatives parameter:** prohibitions are compiled into the positive; `negative_elements` map 1:1 to "without X" clauses.
- **Aspect/quality:** `aspect_ratio: "9:16"`; quality tier from `ModelProfile`, not the KB.
- **Consistency:** reference images (from `consistency_tags` chain) passed as `reference_images` — the KB only provides the tags and the shot-1 artifact.
- **Reproducibility:** seed/output_options per request derived from `(topic, scene_id)`.

---

## 14. Estimated Image Quality Improvements

| dimension | today | V2 expected | mechanism |
|---|---|---|---|
| subject consistency across 5 shots | unmanaged | high | shared `consistency_tags` + shot-1 reference chain |
| hierarchy adherence | ~50% (3 co-equal nouns collapse) | ~90% | explicit primary/secondary/focus + composition rule |
| engineering accuracy | unvalidated prose | validated by term registry | `manufacturing_details` + modality term gates |
| prompt entropy / repetition | 100% share 4 prefixes; 53% share default lens | per-scene camera semantics | discrete camera fields, no fallback prose |
| negative quality | 1 global negative, all rows | semantic excludes + model-native negatives | compiler-owned negatives |
| style retuning cost | edit 400 topics | edit 1 ModelProfile | quality tokens removed from KB |
| thumbnail distinctiveness | suffix appended to all | 400 unique structured covers | `text_slot` + emphasis per topic |
| CSV size | 5.6 MB | ~6.5–7.5 MB (net +20-30% for one-time migration; drops after V1 columns retire) | structured JSON replaces 3 duplicated prose copies |

Golden-set acceptance test (proposed): ~20 topics across all 12 categories, before/after, scored on (a) object presence, (b) hierarchy, (c) engineering correctness, (d) cross-shot consistency. Target: acceptance 60% → ≥85%, consistency similarity +0.1–0.2.

---

## 15. Risks

| risk | impact | mitigation |
|---|---|---|
| Vocabulary drift (enum creep) | schema churn | registry lives in code; adding an enum = code review + bump `version` |
| Lossy auto-conversion (Phase 2) | degraded specs shipped as "V2" | `derived: true` flag blocks compiler consumption until curated |
| Compiler bugs = pipeline-wide regression | silent quality drop | golden-set snapshot tests on compiled output per model profile; compiler is pure/deterministic |
| CSV bloat | slower artifact | acceptable (+30%); retire V1 columns at cutover |
| Legacy consumers of V1 columns | breakage | compatibility view regenerated by compiler; dual-write through Phase 3 |
| Engineering-accuracy regression | fantasy visuals | modality term registry enforced by validator at build time, not at prompt time |
| Consistency-tag collisions across topics | identity bleed | tags scoped per topic (`<topic_key>_<entity>`), world tags namespaced `pr1me_*` |
| Losing art direction | flat generic look | mood/palette per scene override allowed; world profile preserves channel identity |
| Migration stalls (400 topics) | dual-write forever | batch-wise PRs, 8 topics each; automated V1→V2 scaffolding keeps progress measurable |

---

## 16. Final Architecture Diagram

```
                       knowledge/                       (source of truth, curated)
  taxonomy.py  category_defaults.py  batches/topics_0NN.py  engineering_terms.py
        \            |                     |                       /
         \           |       build_knowledge_csv.py (v2)         /
          \          |            |      \                       /
           +---------+------------+-------+---------------------+
                                    |
                                    v
                  assets/knowledge_base.csv  (v2, frozen artifact)
        visual_world_id | visual_architecture_json | scene_plan_json | (script/SEO unchanged)
                                    |
                  +-----------------+-------------------+
                  |                                     |
        validate_knowledge_csv.py v2            build_compat_view.py (legacy V1 columns,
        (enums, term registry, hierarchy)        regenerated, for old consumers)
                  |
                  v
          PROMPT COMPILER  (deterministic, versioned)
        VisualArchitecture + WorldProfile + ModelProfile + TemplateBundle
                  |
     +------------+------------+------------+------------+------------+
     |            |            |            |            |            |
   SDXL        FLUX        Qwen Image   GPT Image    HiDream     future
   (ComfyUI)  (ComfyUI/API) (API)       (API)        (API)       (profiles)
     |            |            |            |            |
     +------------+------------+------------+------------+
                  |
                  v
         WORKFLOW BUILDER  (per-video shot timeline, keyframes, overlays,
                            consistency chains, thumbnail candidate)
                  |
     +------------+------------+
     |                         |
  ComfyUI stage           Thumbnail stage
  (KSampler, ControlNet,  (candidate frame, text_slot)
   IPAdapter, AnimateDiff)
                  |
                  v
        Voice -> Audio -> Motion Graphics -> Assembly -> Render -> Publish

  Legend:  [curated data]  [derived artifacts]  [compiler-owned]  [model-owned]
```

---

## Appendix: Concrete next steps (no CSV changes yet)

1. Approve this proposal; freeze `knowledge_base_v1.0.0` tag.
2. Add `knowledge/visual_architecture.py` (vocab + schema + validator) and `knowledge/engineering_terms.py`.
3. Build the Prompt Compiler prototype consuming V1 (proves the pipeline, enables A/B).
4. Extend `build_knowledge_csv.py` to dual-write V2 fields (auto-converted, `derived: true`).
5. Convert batches one by one (50 PRs); extend the QA gate.
6. Cutover at ≥95% curated; retire V1 columns at schema v2.0.0.