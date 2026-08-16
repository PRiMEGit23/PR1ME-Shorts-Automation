# PR1ME Studio — Backend Architecture (LOCKED)

**Status:** LOCKED. This document is the sole source of truth for the backend surface the
product layer may bind to. The backend itself is STABLE and COMPLETE.

**Hard rules (never violated by the product layer):**

1. No refactoring of backend architecture.
2. No new engines/directors/managers.
3. No API renaming.
4. No CLI compatibility breaks.
5. No pipeline logic changes.
6. The deterministic runtime is only touched to fix bugs.
7. The product layer communicates with the backend ONLY through the existing CLI
   (`pr1me` console script) and the JSON artifacts it produces. No Python code of the
   product layer imports backend internals at runtime — with the single exception of the
   CSV validator (`validate_knowledge_csv.py` / `knowledge.schema`), which the
   Knowledge Base Manager invokes as an isolated process, not as an import.

---

## 1. Process Model

| Concern | Decision |
|---|---|
| Engine process | The `pr1me` console script (`pr1me.cli.main:entrypoint`), bundled as a single `pr1me.exe` sidecar in production packaging. |
| Invocation style | Spawned as a child process by the Rust host. Never run through a shell. |
| Config surface | Environment variables (`PR1ME_*`) passed explicitly per spawn, plus a persistent `.env` written by the Settings page. |
| Output surface | Deterministic JSON artifacts on disk under `output/runs/<run_id>/<topic_slug>/`. The UI binds to artifact files, not to stdout. |
| Stdout/stderr | Captured by Rust and forwarded to the UI event log; never parsed for state. |
| Exit codes | `0` = ok, `1` = pipeline failed, `2` = usage error. |

---

## 2. CLI Contract (the ONLY API)

Global flags (`pr1me --help`): `--version`, `--log-level LEVEL`, `--json-logs`,
`--no-json-logs`.

Single subcommand: `pr1me run`.

### 2.1 `pr1me run` — production (deterministic) mode

Activated when any of these flags is present: `--knowledge-csv`, `--row`, `--row-index`,
`--run-dir`, `--resume`, `--seed`, `--max-attempts`, `--publish`.

| Flag | Meaning | Product-layer usage |
|---|---|---|
| `--knowledge-csv PATH` | Knowledge Base CSV (default `assets/knowledge_base.csv`) | Generate + Batch actions |
| `--row TOPIC` | exact topic of the row to run | Generate (single row) |
| `--row-index N` | 0-based row index | Batch (row range) |
| `--run-dir PATH` | output dir for this run (default `output/runs/<run-id>/<topic>`) | Project Manager (fixed per project) |
| `--resume` | skip stages whose checkpoint matches and artifacts are intact | Re-run / resume project |
| `--seed N` | deterministic render seed (default 42) | Advanced project settings |
| `--max-attempts N` | per-scene render retry budget (default 3) | Advanced project settings |
| `--publish` | actually upload to YouTube (default: dry-run manifest only) | Publish toggle |

Environment overrides honored by the CLI (all prefixed `PR1ME_`): `PROVIDER`,
`DEEPSEEK_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `VOICE_BASE_URL`, `VOICE`,
`AUDIO_FFMPEG_BIN`, `RENDER_FFMPEG_BIN`, `YOUTUBE_ACCESS_TOKEN`,
`YOUTUBE_REFRESH_TOKEN`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`,
`PROMPTS_DIR`, `ASSETS_DIR`, `WORK_DIR`, `LOG_LEVEL`, `LOG_JSON`.

### 2.2 `pr1me run` — classic mode

Flags `--csv`, `--output`, `--directive`, `--category`, `--dry-run`. Reserved for
compatibility and the n8n workflow; the desktop app never invokes classic mode.

---

## 3. Pipeline (deterministic, 15 stages)

`STAGE_ORDER` (fixed, do not reorder):

```
knowledge_load, educational_director, ai_director, visual_intelligence, model_director,
prompt_compiler, workflow_builder, render_loop, voice, subtitles, video_assembly,
video_render, thumbnail, metadata, publisher
```

`ProductionPipeline` constructor keywords: `row`, `settings`, `run_dir`, `seed`,
`max_attempts`, `model_key` (default `sdxl`), `engineering_domain`, `modality`,
`publish`, `renderer`, `voice_provider`, `video_renderer_provider`, `youtube_provider`.

`PipelineResult`: `run_id, job_id, topic, status ("complete"|"failed"), run_dir,
manifest, report, error`.

---

## 4. Run Directory Layout (UI binds to these files)

```
output/runs/<run_id>/<topic_slug>/
├── manifest.json                    pipeline summary
├── pipeline_context.json            run directives + dir map
├── events.json                      typed event timeline (progress)
├── publish_manifest.json            publisher output (dry-run default)
├── reports/execution_report.json    full ExecutionReport (history + QA)
├── checkpoints/<stage_id>.json      resume state per stage
├── artifacts/<stage_id>/output.<version>.json
├── images/<scene_id>.png            approved winner images (S1..S5)
├── audio/narration.<fmt>            TTS WAV
├── subtitles/narration.srt
├── video/short.mp4
├── thumbnail/thumbnail.png
├── workflow/<scene_id>.json         per-scene BackendWorkflow (S1..S5)
└── history/<topic_slug>/<scene_id>/
    ├── history.json                 replayable RenderHistory
    └── attempt_NN/{prompt.txt, prompt_negative.txt, workflow.json,
                    qa_report.json, optimization_report.json,
                    image.png, attempt.json}
```

### 4.1 `manifest.json`

Keys: `version, run_id, job_id, topic, status, finished_at, run_dir, error,
stages[] {stage_id, status, cache_hit, duration_ms}, final_artifacts, report`.

`final_artifacts` keys: `video, thumbnail, metadata, audio, subtitles, images,
workflows, publish_manifest`.

### 4.2 `reports/execution_report.json`

Keys: `version, run_id, job_id, topic, status, total_duration_ms,
stages[] {stage_id, name, version, status, duration_ms, cache_hit, fingerprint,
memory_peak_mb, gpu_time_ms, metrics, artifacts[]}, final_artifacts`.
Stage status ∈ `completed|skipped|failed`.

### 4.3 `events.json`

Keys: `version, run_id, events[] {event_type, offset_ms, stage_id, payload}`.
Event types: `pipeline_started, pipeline_completed, pipeline_failed, stage_started,
stage_completed, stage_failed, stage_skipped, checkpoint_saved, resource_sample,
cache_hit`.

### 4.4 `history/<topic_slug>/<scene_id>/history.json` (RenderHistory)

Keys: `topic, scene_id, seed, max_attempts, attempts[] {attempt_id, index, status,
scene_id, prompt, negative_prompt, workflow, workflow_profile, seed, fingerprint,
image_sha256, image_model, image_path, qa_report, optimization_report, rationale}`.
Attempt status ∈ `rendered|passed|failed|skipped_duplicate|model_switched`.
Helpers available for evolution/QA visualization: `prompt_evolution()`,
`workflow_evolution()`, `qa_scores()`, `optimization_actions()`.

### 4.5 `workflow/<scene_id>.json` (BackendWorkflow)

Keys: `workflow_version, backend, profile, sampler, scheduler, steps, cfg, resolution,
aspect_ratio, vae, loras, negative_tokens, positive_prompt, negative_prompt, controlnet,
ip_adapter, depth_strategy, segmentation_strategy, upscaler, refiner,
animation_backend, quality_target, nodes`.

---

## 5. Provider Configuration Surface

The Settings page writes these environment variables into `.env` (production packaging)
or passes them per-spawn (dev). Values below are defaults the backend already uses.

### 5.1 LLM

| Provider | Env vars | Defaults | Notes |
|---|---|---|---|
| Ollama | `PR1ME_OLLAMA_BASE_URL`, `PR1ME_OLLAMA_MODEL`, `PR1ME_OLLAMA_API_KEY` (opt) | `http://127.0.0.1:11434/v1`, `qwen2.5:7b` | Health: `GET {base}/api/tags` |
| DeepSeek | `PR1ME_DEEPSEEK_API_KEY`, `PR1ME_DEEPSEEK_BASE_URL`, `PR1ME_DEEPSEEK_MODEL` | `https://api.deepseek.com`, `deepseek-chat` | Missing key ⇒ provider not configured |

Provider selection in `pr1me run`: DeepSeek iff `PR1ME_DEEPSEEK_API_KEY` (or legacy
`DEEPSEEK_API_KEY`) is set; else Ollama. The Settings page must therefore make the LLM
choice explicit in `.env` (`PR1ME_PROVIDER`) and surface a "default engine" toggle.

### 5.2 ComfyUI

| Env vars | Defaults |
|---|---|
| `PR1ME_COMFYUI_BASE_URL`, `PR1ME_COMFYUI_WORKFLOW`, `PR1ME_COMFYUI_TIMEOUT_SECONDS`, `PR1ME_COMFYUI_POLL_INTERVAL`, `PR1ME_COMFYUI_MAX_RETRIES` | `http://127.0.0.1:8188`, `<repo>/workflows/comfyui.json`, 60, 0.5, 3 |

### 5.3 Voice (Kokoro)

| Env vars | Defaults |
|---|---|
| `PR1ME_VOICE_BASE_URL`, `PR1ME_VOICE_VOICE`, `PR1ME_VOICE_SAMPLE_RATE`, `PR1ME_VOICE_PATH`, `PR1ME_VOICE_TIMEOUT_SECONDS`, `PR1ME_VOICE_MAX_RETRIES` | `http://127.0.0.1:8890`, `af_heart`, `22050`, `/v1/tts` |

### 5.4 Audio / Video (ffmpeg)

| Env vars | Defaults |
|---|---|
| `PR1ME_AUDIO_FFMPEG_BIN`, `PR1ME_AUDIO_TARGET_LUFS`, `PR1ME_AUDIO_SAMPLE_RATE` | `ffmpeg`, `-14`, `48000` |
| `PR1ME_RENDER_FFMPEG_BIN`, `PR1ME_RENDER_TIMEOUT_SECONDS` | `ffmpeg` (libx264, CRF 20, aac 192k) |

### 5.5 YouTube

| Env vars | Defaults |
|---|---|
| `PR1ME_YOUTUBE_ACCESS_TOKEN`, `PR1ME_YOUTUBE_REFRESH_TOKEN`, `PR1ME_YOUTUBE_CLIENT_ID`, `PR1ME_YOUTUBE_CLIENT_SECRET`, `PR1ME_YOUTUBE_BASE_URL`, `PR1ME_YOUTUBE_TOKEN_URI` | `https://www.googleapis.com`, `https://oauth2.googleapis.com/token` |

OAuth is env-token based (no client-secrets JSON). Dry-run is the default; `--publish`
enables real upload. Instagram: **no backend support exists** — the Settings page shows
the Instagram card in a "planned" state and disables it.

### 5.6 Health checks (bridge commands)

The Rust CLI bridge exposes `provider_health(provider)` which spawns
`pr1me`/provider probes:
- Ollama: `GET {base}/api/tags`
- DeepSeek: key presence + `GET {base}` reachability
- ComfyUI: `GET {base}/system_stats`
- Kokoro: `GET {base}/health` (fallback: TCP connect to `127.0.0.1:8890`)
- ffmpeg: binary existence + `-version` exit 0
- YouTube: token/refresh credentials presence (not network)

---

## 6. Production OS Exports (Dashboard binds to these)

The deterministic factory exports six JSON files via `ProductionManager.export(dir)`:

| File | Keys (subset used by UI) |
|---|---|
| `production_report.json` | `project_count, job_count, completed_jobs, failed_jobs, mean_qa, throughput_per_day, batch_counts, success_rate` |
| `dashboard.json` | `version, tick, project_count, job_count, completed, failed, mean_qa, throughput_per_day, batch_counts` |
| `queue.json` | `version, total_jobs, status_counts {pending,running,paused,retry,completed,cancelled,failed}, jobs[] {job_id, project_id, topic, job_type, worker_type, status, priority, deadline_tick, estimated_runtime_ticks, start_tick, end_tick, retries}` |
| `projects.json` | `version, projects[] {project_id, topic, batch_kind, priority, deadline_tick, schedule_tick, knowledge_row_key, disk_budget_mb, job_ids, stats, published}` |
| `worker_statistics.json` | `version, workers[] {worker_type, busy_ticks, idle_ticks, ...}` |
| `resource_statistics.json` | `version, limits, history[], peak {gpu_units, vram_mb, ram_mb, cpu_units, disk_mb}` |

Job types (8): `storyboard, render_image, voice, render_video, metadata, asset_index,
publish, learning`. Job statuses (7): `pending, running, paused, retry, completed,
cancelled, failed`.

**Note:** the Production OS is a deterministic tick simulation. The desktop Dashboard
displays its exports verbatim (bounded simulation `--max-ticks` for preview); real
per-run progress comes from live `events.json` of actual `pr1me run` processes.

---

## 7. Knowledge Base CSV Schemas

### 7.1 `assets/knowledge_base.csv` — 39 columns (exact order, do not reorder)

```
topic, difficulty, category, subcategory, keywords, search_intent, viewer_level,
core_question, learning_objective, engineering_summary, real_world_application,
common_misconceptions, teaching_strategy, script, scene_count, scene_plan_json,
visual_spec_json, thumbnail_visual_spec, thumbnail_prompt, thumbnail_negative_prompt,
image_prompt_pack_json, negative_prompt, camera_language, lighting_style, color_palette,
composition_style, render_style, materials, environment, motion_plan, animation_notes,
text_overlay, title, title_variations_json, description, hashtags, seo_keywords_json,
references_json, fact_check_notes
```

JSON-typed columns (must parse): `keywords, common_misconceptions, scene_plan_json,
visual_spec_json, thumbnail_visual_spec, image_prompt_pack_json, materials, text_overlay,
title_variations_json, hashtags, seo_keywords_json, references_json, fact_check_notes`.

`viewer_level` ∈ `B|I|A`. Difficulty ∈ `B|I|A` (Beginner/Intermediate/Advanced).

### 7.2 Validation rules (from `validate_knowledge_csv.py`)

1. Exact 39-column header; no empty cells; no duplicate topics.
2. All JSON columns parse.
3. Script narration 20–35 s at 2.8 words/s.
4. `scene_count` == `len(scene_plan_json)`; ≥ 4 scenes; each scene has 13 fields
   (`scene_id, goal, teaching_point, camera, lens, composition, foreground, background,
   lighting, motion, objects, transition, duration`).
5. Scene durations sum 18–40 s; drift ≤ 30% vs narration.
6. `image_prompt_pack_json` length == scene_count; each shot has 9 fields.
7. `title_variations_json` ≥ 5; `hashtags` ≥ 3; `seo_keywords_json` ≥ 5;
   `fact_check_notes` and `references_json` non-empty.
8. Thumbnail spec: 10 fields; `thumbnail_prompt` ≥ 40 words; `thumbnail_negative_prompt`
   ≥ 10; `description` ≥ 60 chars.

### 7.3 `assets/topics.csv` — 6 columns

`topic, difficulty, category, subcategory, keywords, search_intent`
(keywords `;`-joined).

### 7.4 Taxonomy

12 categories (slug → display): `slicer` Slicer & Print Settings, `materials` Materials
& Filament, `hardware` Printer Hardware, `troubleshooting` Calibration & Troubleshooting,
`design` Design for 3D Printing, `finishing` Post-Processing & Finishing,
`industrial_am` Advanced & Industrial AM, `mechanical` Mechanical Engineering,
`physics` Physics of Engineering, `manufacturing` Manufacturing Processes,
`electronics` Electronics & Motors, `tools` Tools, Measurement & Practice.

---

## 8. Error Taxonomy (mapped to UI error banners)

| Code family | UI treatment |
|---|---|
| `config_error` | Settings page badge + "Fix configuration" action |
| `provider_not_configured` | Provider card warning |
| `ollama_provider_error`, `deepseek_provider_error` | Provider card error |
| `comfyui_*` (5 codes) | ComfyUI card error |
| `voice_*`, `audio_*`, `video_render_*` | Run failure banner |
| `youtube_auth_error`, `youtube_upload_error` | Publish failure banner |
| `contract_violation`, `model_validation_error` | Run failure banner (determinism note) |
| `job_aborted` | Queue item "aborted" |

---

## 9. Versions

- `pr1me` package: `1.0.0` (`src/pr1me/version.py`).
- Pipeline: `7.0.0`. Runtime: `1.0.0`. Report: `1.0.0`. Production OS: `PRODUCTION_OS_VERSION`.

---

## 10. Directory Truth (backend-owned, read-only for product)

| Path | Owner |
|---|---|
| `src/pr1me/**` | Backend (installed package) |
| `knowledge/**` | Backend knowledge layer |
| `runtime/**` | Deterministic runtime (bug-fix only) |
| `prompts/**`, `assets/*.csv`, `workflows/comfyui.json`, `config/**` | Backend data (product may READ; Knowledge Base Manager may WRITE only `assets/knowledge_base.csv` and `assets/topics.csv`) |
| `output/**` | Backend artifacts (product reads) |
| `app/**` | **Product layer — this document governs it** |