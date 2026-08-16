# PR1ME Studio — Incremental Implementation Plan v2 (LOCKED)

**Status:** LOCKED. One feature/module at a time. Every phase must compile and pass its
tests before the next phase starts. Commit after every completed feature.
**Alignment:** v2 — matches the workbench model of `UX_ARCHITECTURE.md` v2 and
`VISUAL_DESIGN_SYSTEM.md` v2. Backend contract unchanged.

**Gate per phase:** `npm run check` (svelte-check + tsc) → `npm run test` (Vitest) →
`cargo check` (Rust) → commit. Phase 2S6 additionally requires a full
`tauri build` on Windows.

---

## Prerequisites

1. Install Rust toolchain (stable) via `rustup` — **required before 2S1**; Tauri on
   Windows additionally needs the MSVC toolchain (Visual Studio Build Tools with
   "Desktop development with C++") and WebView2 runtime (preinstalled on Win11).
2. Node 24 + npm 11 already available.
3. Python 3.13 venv with `pr1me` installed (`pip install -e .`) — already present.
4. ffmpeg discoverable via `PR1ME_AUDIO_FFMPEG_BIN`/`PR1ME_RENDER_FFMPEG_BIN` or PATH.

---

## Phase 2S1 — Foundation (Workbench Shell, Theme, Bridge)

> After 2S1 passes build + tests: **STOP and wait for review.**

Features, in order:

1. **Initialize Tauri project** — `app/` workspace: `npm create tauri-app` scaffold
   (SvelteKit template), `tauri.conf.json` (identifier `labs.pr1me.studio`, product
   name `PR1ME Studio`, window 1440×900 min 960×600, `decorations: true`), capabilities
   allowlist (no shell in webview), deps: `@tauri-apps/api`, plugins `shell`, `fs`,
   `dialog`, `updater`, `process`. ESLint/Prettier/TS strict wired.
2. **Configure SvelteKit** — `adapter-static` SPA with **one route**, `ssr: false`,
   `prerender: false`, `base: ''`, tsconfig strict with `noUncheckedIndexedAccess`,
   alias `$lib`. `svelte-check` + Vitest (jsdom) wired.
3. **Theme tokens** — `src/lib/styles/tokens.css` exactly per Visual Design System v2
   (tokens + chrome sizes + motion), plus `base.css` and `utilities.css`.
4. **Layout system** — `Panel`, `PanelHeader`, `DockZone`, `PanelGroup`, `SplitView`,
   `DragHandle`, `EditorArea` on the 4 px grid; dock zones left/right/bottom with
   resize + collapse.
5. **Window shell** — `WindowShell` (`+layout.svelte`): TitleBar (production switcher
   stub, queue chip, health dots), WorkbenchBar (8 tabs + Generate/Connections/
   Preferences), ActivityBar (5 panel toggles), DockZones, EditorArea, StatusBar.
6. **Workbench host** — `+page.svelte` switches layout composition per workbench;
   `layout.store` presets (8 defaults); workbench switching animates per motion rules
   (300 ms composition, no route change).
7. **Command palette** — `Cmd+Shift+P`/`Cmd+K`/`Cmd+P`; fuzzy matcher over registered
   actions + workbenches (init); Esc/Enter/arrows; Kbd chips; palette motion per tokens.
8. **Global state** — `AppStore` root: `ui` (workbench, palette, toasts, modals),
   `settings` (`.env` model), `layout`, `editor` (tabs, selection, undo scaffolding);
   DI container `AppServices`.
9. **Rust CLI bridge** — commands `app_version`, `settings_load`, `settings_save`,
   `env_probe`, `layout_save`; typed `bridge.ts` facade + typed event subscription
   layer; `process.rs` spawn/supervise `pr1me.exe` with env injection and stdout
   capture; `Sidecar` unit tests with a fake `pr1me` script.
10. **Document model** — `editor.store`: open documents, tabs, dirty state, undo/redo
    scaffolding; first document type: empty `ScriptDocument` shell.

**Tests:** Vitest — palette fuzzy ranking, ui/workbench transitions, layout preset
application, bridge serialization, settings model parse; Rust — settings round-trip,
layout save, process spawn/kill with fake binary. `cargo check` green.

---

## Phase 2S2 — Library, Productions & Connections

1. **Library workbench**: production grid (cards), recent episodes strip, Welcome
   (first-run steps + empty states), template picker (default FDM photoreal ·
   educational · batch campaign).
2. **Production system**: `production_create`/`production_list`/`production_load`/
   `production_save` in Rust; `config/productions/<slug>/production.json` model
   (policy, episodes, approvals, layouts); episode records; adopt-existing-runs import.
3. **Connection Center** (`Cmd+Shift+D`): 7 connection cards per UX lock; inline config
   + masked secrets; Test action; `providers_health_all` ambient dots in title/status
   bars; auto-detect banners for local providers.
4. **Preferences modal** (`Cmd+,`): General (dirs read-only, log level, durations,
   critic toggles) + Publish defaults → `.env` via `settings_save`; searchable sections.
5. `providers_health` Rust probes per `BACKEND_ARCHITECTURE.md` §5.6 (Ollama
   `/api/tags`, ComfyUI `/system_stats`, Kokoro TCP, ffmpeg `-version`, DeepSeek/
   YouTube credential presence); parallel via tokio; 3 s timeout.
6. `productions.store` + `library.vm`/`connections.vm`; production switching re-scopes
   the window (explorer, script gallery, queue, inspector).

**Tests:** production model round-trip (atomic write, validation), template defaults,
provider probes with mocked HTTP/canned sockets, masked-secret rendering, ambient-dot
aggregation.

---

## Phase 2S3 — Script Workbench (Knowledge Base)

1. **Knowledge gallery** (visual-first): `KnowledgeCard` grid (category chip, difficulty
   badge, topic, keyword tags, scene count), search + category/difficulty filters,
   windowed virtualization; table mode as secondary toggle.
2. **Episode documents**: select rows → episodes in the current production; `ScriptDocument`
   tabs with narration editor (WordMeter/DurationMeter vs 20–35 s rule), title/meta
   fields, JSON groups; dirty state + `Cmd+S`.
3. **Knowledge editor** (full-screen document): 39 fields in 6 groups; JSON fields as
   schema-aware `JsonView` editors (13 scene fields, 9 shot fields, ≥5 titles, ≥3
   hashtags, ≥5 seo keywords); add/duplicate/delete row with confirm.
4. **Validation**: `csv_read`/`csv_write` (atomic, locked) + `csv_validate` invoking
   `validate_knowledge_csv.py` via the Python sidecar; validate-all flow with progress,
   per-row error/warning list, jump-to-row; save blocked on errors unless override.
5. `knowledge.store` (windowed) + `script.vm`; queue episode from gallery (`Cmd+Enter`
   → Render board).

**Tests:** CSV parse/write round-trip with 39-col fixture; validation report mapping;
narration meter math; edit buffer → save pipeline; search/filter/windowing logic.

---

## Phase 2S4 — Storyboard, Workflow & Render Board

1. **Generate bridge**: `generate_start`/`generate_regen`/`generate_stop`/
   `process_logs`; `CommandBuilder` assembling `pr1me run --knowledge-csv … --row …
   --run-dir <output>/runs/<prod-slug>/<episode-slug>` (+`--seed`, `--max-attempts`,
   `--publish`) with env from settings store; watcher wiring: `fs_watch` → `fs:change`
   → events tail → `run:stage`/`run:progress`/`run:candidate`/`run:completed`/
   `run:failed`.
2. **Render board**: BoardColumns (queued/running/done) of `EpisodeCard`s (stage ring,
   progress rail, ETA chip); drag to reorder; running card expands with live stage rail
   + streaming thumbnails; pause/cancel/retry; honest queue positions (1 process);
   failure card with code + Fix/Retry.
3. **Storyboard workbench**: `SceneBoard` canvas (zoom/pan/fit), `SceneCard`s with
   `CandidateStrip` (from `run_history`/`images`), approve star + pre-approved QA
   winner, regenerate (`generate_regen --seed <next>`), camera/lighting/composition
   pictogram pickers in Inspector (product-owned SVG presets, preview-only), locked
   scene order (lock glyph), live stage rail.
4. **Workflow workbench**: `PromptChain` (15 ChainNodes with status/cache badges,
   stage contracts in Inspector via `run_manifest`/artifacts) and `GraphCanvas`
   (`WorkflowNode`s from `BackendWorkflow` fields, zoom/pan/fit/minimap, rationale in
   Inspector); `1`/`2` toggle, per-scene selector S1–S5+THUMB.
5. `runs.store` + `storyboard.vm`/`workflow.vm`/`render.vm`.

**Tests:** CommandBuilder arg assembly (golden strings); batch sequencing and queue
position math; watcher→store propagation with fixture events.json; seed-bump regen
spawn args; graph node derivation from fixture workflow JSON; candidate strip mapping.

---

## Phase 2S5 — Edit, Deliver, Assets & Insights

1. **Edit workbench**: Timeline (Video/Audio/Subtitles/Overlays tracks, scene clips
   with thumbnails, ruler, markers `M`, in/out range, playhead), Player (transport,
   timecode, volume; scrubs local `video/short.mp4`; plan-preview before render),
   clip→scene links.
2. **Deliver workbench**: target cards (YouTube; Instagram locked), thumbnail picker
   (candidates from `thumbnail/` + assets), metadata review (JsonView of
   `publish_manifest.json`), dry-run publish (`Cmd+Shift+Enter`) vs real (`Cmd+Enter`);
   publish state tracked in the episode record.
3. **Asset Browser** (dockable panel): grid/filmstrip/tree modes, run-media/assets/
   config tabs, drop targets (scene reference, thumbnail picker), lightbox, reveal in
   OS, live badge on new artifacts.
4. **Insights workbench**: Analytics tab (KPI row, success/QA charts from Production OS
   exports + run reports, filters, drill-down to runs) and Learning tab (proposal cards
   with explicit actions: retry → queue, open row in Script editor, adopt into policy —
   product-owned only).
5. **Multi-monitor**: `window_detach` floating panel windows + re-dock; layout
   persistence per workbench per production.

**Tests:** timeline clip math (deterministic durations), playhead/scrub logic, publish
payload mapping, proposal action wiring, floating window lifecycle (Rust), KPI
aggregation from fixture exports.

---

## Phase 2S6 — Update & Packaging

1. Auto-update: `tauri-plugin-updater` + `updater.rs` + Preferences→About "Check for
   updates"; signed update JSON from static endpoint/GitHub releases; boot check
   (30 s delayed, silent).
2. Sidecar packaging: PyInstaller onefile `pr1me.exe` (+ `validate_knowledge_csv`
   bundled as CLI subcommand of the same exe), ffmpeg discovery + optional bundled
   ffmpeg; resources dir mounted at runtime.
3. Installer: NSIS via `tauri build --bundles nsis`, single-file EXE, Start Menu +
   desktop shortcuts, per-user install, license page.
4. First-run experience: Welcome → create production → health check (LLM, ffmpeg,
   Kokoro) → Library shows first episodes; "Generate" gated on LLM+ffmpeg health with
   inline Fix actions.
5. Release gates: `tauri build` green, installer smoke-tested on clean Win11,
   update flow verified against staging endpoint.

---

## Verification & Definition of Done (every phase)

- `npm run check` clean (no TS/svelte errors).
- `npm run test` green (unit + Rust `cargo test`).
- No backend file modified (guard: `git diff --stat src/ runtime/ knowledge/` empty
  except bug-fix permissions).
- Committed with one descriptive message per feature.
- Visual QA against locked wireframes + tokens (screenshot pass).

## Explicitly out of scope (2S1..2S6)

- Light theme, i18n, macOS/Linux packaging (Windows-first), Instagram publishing
  (backend has no support), editing backend CSVs other than the two KB files, new
  CLI commands, any change to the deterministic runtime, scene reordering at the
  pipeline level (order is script-locked; reorder = script edit + re-run).