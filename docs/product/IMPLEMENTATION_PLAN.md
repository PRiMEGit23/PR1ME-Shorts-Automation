# PR1ME Studio — Incremental Implementation Plan (LOCKED)

**Status:** LOCKED. One feature/module at a time. Every phase must compile and pass its
tests before the next phase starts. Commit after every completed feature.

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

## Phase 2S1 — Foundation (Shell, Theme, Bridge)

> After 2S1 passes build + tests: **STOP and wait for review.**

Features, in order:

1. **Initialize Tauri project** — `app/` workspace: `npm create tauri-app` scaffold
   (SvelteKit template), `tauri.conf.json` (identifier `labs.pr1me.studio`, product
   name `PR1ME Studio`, window 1280×800 min 960×600, `decorations: true`), capabilities
   allowlist (no shell in webview), deps: `@tauri-apps/api`, plugins `shell`, `fs`,
   `dialog`, `updater`, `process`. ESLint/Prettier/TS strict wired.
2. **Configure SvelteKit** — `adapter-static` SPA, `ssr: false`, `prerender: false`,
   `base: ''`, tsconfig strict with `noUncheckedIndexedAccess`, alias `$lib`.
   `svelte-check` + Vitest (jsdom) + Playwright (optional, shell smoke) wired.
3. **Theme tokens** — `src/lib/styles/tokens.css` exactly per Visual Design System,
   plus `base.css` (reset, scrollbars, focus ring) and `utilities.css`.
4. **Layout system** — `AppGrid`, `Panel`, `PanelGroup`, `SplitPane`, `StatusBar`
   primitives on tokens.
5. **Window shell** — `WindowShell` (`+layout.svelte`): Sidebar, Dock, titlebar slot;
   empty-state route pages.
6. **Sidebar** — 8 items per UX lock; expand/collapse, active route highlight,
   badges (queue counts), keyboard nav (`Ctrl+1..8`).
7. **Dock panels** — GenerateButton (disabled stub), RunStatusChip, ProviderHealthDot
   (aggregate stub), SettingsTrigger.
8. **Command palette** — `Ctrl+K`/`Ctrl+P`; fuzzy search over routes + static actions
   (init); Esc/Enter handling; keyboard navigation; palette motion per tokens.
9. **Global state** — `AppStore` root + `ui` slice (route, palette, toasts, modals) +
   `settings` slice with default `.env` model; DI container `AppServices`.
10. **Rust CLI bridge** — commands `app_version`, `settings_load`, `settings_save`,
    `env_probe`; typed `bridge.ts` facade + typed event subscription layer;
    `process.rs` spawn/supervise `pr1me.exe` with env injection and stdout capture
    (used by later phases); `Sidecar` unit tests with a fake `pr1me` script.

**Tests:** Vitest — palette fuzzy ranking, ui slice transitions, bridge serialization,
settings model parse; Rust — settings round-trip, process spawn/kill with fake binary.
`cargo check` green.

---

## Phase 2S2 — Settings & Providers

1. Settings page shell: left nav (General | Providers | Knowledge | Publish | About).
2. General: dirs (read-only), log level, durations, critic toggles — persisted via
   `settings_save` → `.env`.
3. Provider cards ×7 per lock (Ollama, DeepSeek, ComfyUI, Kokoro, ffmpeg, YouTube,
   Instagram-disabled): config fields with masked secrets, "Test connection" →
   `providers_health`; per-card `HealthState` chip.
4. `providers_health` Rust implementation: probes per `BACKEND_ARCHITECTURE.md` §5.6
   (Ollama `/api/tags`, ComfyUI `/system_stats`, Kokoro TCP, ffmpeg `-version`,
   DeepSeek/YouTube credential presence); parallel via tokio; 3 s timeout.
5. Publish: visibility, category, tags, made-for-kids defaults → `.env`.
6. About: versions + "Check for updates" stub (wired in 2S6).
7. `providers.store` + `settings.vm`/`settings.service`; dirty-state guard.

**Tests:** provider probes with mocked HTTP (Vitest+msw over the bridge mock; Rust
probe fn with canned sockets), settings round-trip, masked rendering.

---

## Phase 2S3 — CSV Knowledge Base Manager

1. `csv_read`/`csv_write` (atomic, locked) + `csv_validate` invoking
   `validate_knowledge_csv.py` via the Python sidecar (subprocess, parse JSON exit).
2. Knowledge page: DataTable (virtualized), search (topic/category/keywords), filters
   (category × difficulty × invalid-only), pagination, column sorting.
3. Row editor drawer: 39 fields in 6 groups; JSON fields as `JsonView` editors with
   schema-aware validation (13 scene fields, 9 shot fields, ≥5 titles, ≥3 hashtags,
   ≥5 seo keywords); word-count and duration meters against 20–35 s rule.
4. Validate-all flow: progress bar → report list (error/warning per row + field),
   jump-to-row; save blocked on errors unless "save anyway" override.
5. Add row / delete row (confirm modal) / duplicate row.
6. `knowledge.store` pagination + `knowledge.vm`.

**Tests:** CSV parse/write round-trip with 39-col fixture; validation report mapping;
edit buffer → save pipeline; pagination/search logic.

---

## Phase 2S4 — Generate, Queue, Projects

1. `generate_start`/`generate_stop`/`generate_resume`/`process_logs` in Rust bridge;
   `CommandBuilder` assembling `pr1me run --knowledge-csv … --row … --run-dir …`
   (+`--seed`, `--max-attempts`, `--publish`) with env from settings store.
2. Generate page per wireframe: row scope (search + multi-select), project picker,
   seed/max-attempts, publish toggle, ETA estimate (runtime ticks × row count), batch
   start; concurrent-safe (max 1 active process; rest queued).
3. Queue page: snapshot from `queue.json` exports (or live batch ledger), status
   counts, pause/resume/retry/clear actions, ETA column (remaining ticks / worker
   count), per-job actions menu.
4. Projects: create (name + rows + settings), list cards with progress, open drawer
   listing runs → Workflow Viewer link, resume project (`--resume` re-spawn).
5. Watcher wiring: `fs_watch` on run dir → `fs:change` → events tail → `run:stage`/
   `run:progress`/`run:completed`/`run:failed`; RunStatusChip live.

**Tests:** CommandBuilder arg assembly (golden strings), batch sequencing, queue ETA
math, watcher→store propagation with fixture events.json.

---

## Phase 2S5 — Workflow Viewer, Dashboard, History, Assets

1. Workflow Viewer (`/runs/[runId]`): tabs Storyboard / Prompt Chain / ComfyUI /
   QA & History; reads `manifest.json`, `reports/execution_report.json`,
   `workflow/*.json`, `history/**/history.json`; timeline rail S1..S5+THUMB; JSON
   contract views; per-scene attempts + 8 QA bars + prompt/workflow evolution lists.
2. Production Dashboard: `export_dashboard`/queue exports; KPI row (total runs,
   success %, completed, ETA, mean QA, throughput), status-count bars, running-jobs
   list with stage progress, history table, success donut + mean-QA gauge; tick
   simulation bounded (max 2×3600 ticks) for live preview.
3. Render History page: runs × scenes table (attempts, winner QA, verdict) →
   Workflow Viewer links; search/filter.
4. Asset Browser: `fs_tree` + thumbnail grid (video/audio/image cards), lightbox,
   "open in system viewer"; watches for new runs.
5. `runs.service` run scanner + `assets.store`/`history.vm`/`workflow.vm`.

**Tests:** report→view mapping, QA score aggregation, tree/thumbnail listing with
fixture runs dir, dashboard KPI math from fixture exports.

---

## Phase 2S6 — Update & Packaging

1. Auto-update: `tauri-plugin-updater` + `updater.rs` + About "Check for updates";
   signed update JSON served from a static endpoint/GitHub releases; version checks
   on boot (30 s delayed, silent).
2. Sidecar packaging: PyInstaller onefile `pr1me.exe` (+ `validate_knowledge_csv`
   bundled as CLI subcommand of the same exe), ffmpeg discovery + optional bundled
   ffmpeg; resources dir mounted at runtime.
3. Installer: NSIS via `tauri build --bundles nsis`, single-file EXE, Start Menu +
   desktop shortcuts, per-user install, license page.
4. First-run experience: empty-state dashboard, provider setup banner, path to
   "Generate" gated on LLM+ffmpeg health.
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
  CLI commands, any change to the deterministic runtime.