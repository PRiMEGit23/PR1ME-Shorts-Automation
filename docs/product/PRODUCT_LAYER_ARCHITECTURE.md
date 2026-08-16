# PR1ME Studio — Product Layer Architecture (LOCKED)

**Status:** LOCKED. Governs everything under `app/`.
**Alignment:** v2 — matches the workbench model of `UX_ARCHITECTURE.md` v2 and the design
system of `VISUAL_DESIGN_SYSTEM.md` v2. Backend contract unchanged (`BACKEND_ARCHITECTURE.md`).

---

## 1. Product Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Desktop shell | **Tauri 2** (Rust host, WebView2 on Windows) | ~10 MB installer vs Electron ~150 MB; native updater + sidecar process mgmt; Rust owns the CLI bridge |
| Frontend | **SvelteKit 2 + Svelte 5 (runes) + TypeScript (strict)** | Smallest bundle, runes give fine-grained reactivity for high-frequency artifact updates |
| UI language | **MVVM** (View → ViewModel → Service → Rust bridge → CLI) | ViewModels are plain TS classes, unit-testable without DOM or Tauri |
| State | **Single AppStore, slice-per-domain**, typed, serializable | One source of truth; renderer subscribes via runes |
| IPC | Typed `invoke<Cmd>` request/response + Tauri **events** for streams (progress, fs changes) | No polling; UI stays live |
| Backend access | Only `pr1me.exe` subprocess + JSON artifacts + `.env` writes | Backend untouched; contract in `BACKEND_ARCHITECTURE.md` |
| Packaging | PyInstaller `pr1me.exe` sidecar + NSIS installer + updater JSON | Single executable, auto-update |
| Tests | Vitest for ViewModels/Services (bridge mocked); Rust `cargo test` for commands; Playwright smoke for shell | Type-safe, regression-safe |

---

## 2. Technology Stack (exact versions at 2S1)

- Tauri 2.x (`tauri = "2"`, `tauri-plugin-shell`, `tauri-plugin-fs`, `tauri-plugin-updater`,
  `tauri-plugin-process`, `tauri-plugin-dialog`), Rust edition 2021, `rust-version 1.77+`.
- `@tauri-apps/api` v2, `@tauri-apps/plugin-*` v2.
- SvelteKit 2.x, Svelte 5.x, Vite 6, `@sveltejs/adapter-static` (SPA mode; no SSR).
- TypeScript `strict: true`, `noUncheckedIndexedAccess: true`.
- CSS: hand-written custom properties (Visual Design System) + `postcss` only for
  autoprefixing. No CSS framework — the design system is bespoke.
- Lint/format: ESLint 9 flat config + Prettier.

---

## 3. Folder Structure (exact, do not rename)

```
app/
├── package.json
├── svelte.config.js
├── vite.config.ts
├── tsconfig.json
├── eslint.config.js
├── prettier.config.js
├── index.html                      (SPA entry, Vite)
├── static/
│   └── brand/                      (app icon, logo mark)
├── src/
│   ├── app.html                    (SvelteKit template)
│   ├── app.d.ts
│   ├── main.ts                     (bootstrap: stores → bridge → shell)
│   └── routes/                     (SPA root only — workbenches are NOT routes;
│                                   workbench = layout composition, one +layout)
│       ├── +layout.svelte          (WindowShell: title bar, workbench bar,
│       │                            activity bar, dock zones, status bar, palette)
│       └── +page.svelte            (active workbench host; workbench switch swaps
│                                    composition, not URL)
│   ├── lib/
│   │   ├── core/
│   │   │   ├── di.ts               (AppServices container)
│   │   │   ├── bridge.ts           (typed IPC facade)
│   │   │   ├── events.ts           (typed Tauri event subscriptions)
│   │   │   ├── config.ts           (app config, .env model)
│   │   │   └── id.ts               (uuid/slug helpers)
│   │   ├── models/                 (mirror of backend JSON contracts)
│   │   │   ├── run.ts              (RunManifest, StageReport, ExecutionReport)
│   │   │   ├── events.ts           (PipelineEvent)
│   │   │   ├── workflow.ts         (BackendWorkflow)
│   │   │   ├── history.ts          (RenderHistory, RenderAttempt, QA)
│   │   │   ├── queue.ts            (QueueSnapshot, JobView)
│   │   │   ├── dashboard.ts        (DashboardView)
│   │   │   ├── projects.ts         (ProjectView)
│   │   │   ├── knowledge.ts        (KnowledgeRow, ValidationReport)
│   │   │   ├── providers.ts        (ProviderConfig union, HealthStatus)
│   │   │   └── settings.ts         (SettingsModel)
│   │   ├── services/
│   │   │   ├── settings.service.ts     (load/save .env via bridge)
│   │   │   ├── providers.service.ts    (health checks, Connection Center)
│   │   │   ├── runs.service.ts         (list/watch runs, artifacts)
│   │   │   ├── generate.service.ts     (spawn pr1me run, monitor, seed-bump regen)
│   │   │   ├── queue.service.ts        (render board, production os exports)
│   │   │   ├── knowledge.service.ts    (CSV read/write/validate)
│   │   │   ├── assets.service.ts       (file tree, thumbnails)
│   │   │   ├── productions.service.ts  (production/episode records, approvals)
│   │   │   ├── layout.service.ts       (workbench presets, dock state, floating windows)
│   │   │   └── insights.service.ts     (learning/analytics exports)
│   │   ├── stores/
│   │   │   ├── app.store.ts        (root store, slice wiring)
│   │   │   ├── settings.store.ts
│   │   │   ├── providers.store.ts
│   │   │   ├── knowledge.store.ts
│   │   │   ├── queue.store.ts
│   │   │   ├── runs.store.ts
│   │   │   ├── assets.store.ts
│   │   │   ├── productions.store.ts
│   │   │   ├── dashboard.store.ts
│   │   │   ├── insights.store.ts
│   │   │   ├── editor.store.ts     (open documents, tabs, undo stacks, selection)
│   │   │   ├── layout.store.ts     (docking, splits, floating windows)
│   │   │   └── ui.store.ts         (workbench, palette, toasts, modals, connections)
│   │   ├── viewmodels/
│   │   │   ├── library.vm.ts
│   │   │   ├── script.vm.ts
│   │   │   ├── storyboard.vm.ts
│   │   │   ├── workflow.vm.ts
│   │   │   ├── render.vm.ts
│   │   │   ├── edit.vm.ts
│   │   │   ├── deliver.vm.ts
│   │   │   ├── insights.vm.ts
│   │   │   └── connections.vm.ts
│   │   └── components/
│   │       ├── shell/              (WindowShell, TitleBar, WorkbenchBar, ActivityBar,
│   │       │                        DockZone, EditorArea, EditorTabs, StatusBar,
│   │       │                        CommandPalette, FloatingWindow)
│   │       ├── layout/             (Panel, PanelHeader, PanelGroup, SplitView,
│   │       │                        DockPanel, DragHandle, EmptyState)
│   │       ├── primitives/         (per Visual Design System §25.1)
│   │       ├── data/               (DataGrid, VirtualList, TreeView, SearchField,
│   │       │                        FilterChips, JsonView)
│   │       ├── charts/             (Sparkline, BarChart, Donut, Gauge, Heatmap)
│   │       ├── media/              (Player, TransportBar, Timecode, ImageStrip,
│   │       │                        CandidateStrip, AudioWave)
│   │       ├── domain/             (per workbench: ProductionCard, KnowledgeCard,
│   │       │                        SceneCard, ChainNode, WorkflowNode, BoardColumn,
│   │       │                        EpisodeCard, TimelineClip, ConnectionCard,
│   │       │                        ProposalCard, StageRing, StageRail, StagePipeline)
│   │       └── pictograms/         (CameraPicker, LightingPicker, CompositionPicker)
│   └── styles/
│       ├── tokens.css              (Visual Design System tokens)
│       ├── base.css                (reset, scrollbars, focus rings)
│       └── utilities.css           (layout helpers)
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── capabilities/default.json
│   ├── icons/
│   ├── build.rs
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs                  (run() → builder → invoke_handler)
│   │   ├── commands/
│   │   │   ├── mod.rs
│   │   │   ├── settings.rs         (.env read/write)
│   │   │   ├── providers.rs        (health probes, Connection Center)
│   │   │   ├── process.rs          (spawn/kill sidecar, stream stdout)
│   │   │   ├── fs.rs               (read dir, watch dir, read file, thumbnails)
│   │   │   ├── csv.rs              (read/write/validate CSV via sidecar)
│   │   │   ├── productions.rs      (production/episode records, approvals)
│   │   │   ├── layout.rs           (workbench presets, dock state, floating windows)
│   │   │   └── app.rs              (version, platform, updater state)
│   │   ├── bridge/
│   │   │   ├── mod.rs
│   │   │   ├── cli.rs              (CommandBuilder for pr1me.exe)
│   │   │   ├── watcher.rs          (Notify-based fs watcher → events)
│   │   │   └── sidecar.rs          (process supervision, kill on drop)
│   │   └── updater.rs
├── tests/
│   ├── unit/                       (Vitest: viewmodels + services, bridge mocked)
│   └── e2e/                        (Playwright shell smoke)
└── scripts/
    ├── package-sidecar.mjs         (PyInstaller pr1me.exe → resources/)
    ├── build-installer.mjs         (tauri build --bundles nsis)
    └── dev.mjs                     (concurrent: vite + tauri dev)
```

---

## 4. Architecture Layers & Data Flow

```
┌────────────────────────────────────────────────────────────┐
│ View (Svelte components)          — renders stores, emits  │
│                                    intents (no logic)      │
├────────────────────────────────────────────────────────────┤
│ ViewModel (plain TS classes)      — orchestrates one workbench │
│                                    (formatting, validation,    │
│                                    command sequencing)         │
├────────────────────────────────────────────────────────────┤
│ Store slices (rune-based)         — single source of truth │
├────────────────────────────────────────────────────────────┤
│ Services                         — the ONLY layer that     │
│                                    calls the bridge        │
├────────────────────────────────────────────────────────────┤
│ Bridge (typed IPC facade)        — invoke<T> + events      │
├────────────────────────────────────────────────────────────┤
│ Rust host commands + sidecar     — process, fs, csv, env,  │
│                                    watcher, updater        │
├────────────────────────────────────────────────────────────┤
│ pr1me.exe (CLI) + JSON artifacts + .env                    │
└────────────────────────────────────────────────────────────┘
```

Rules:
- Views never import services; they call `vm.action(...)` or read store slices.
- ViewModels never touch Tauri APIs; they call services.
- Services never manipulate store state directly; they return results, stores apply them
  (via service-owned store mutators in the same module when the slice is exclusive).
- Every store slice is plain JSON-serializable so devtools can snapshot/debug.
- No component renders a raw backend shape; models are mapped to view models
  (`RunView`, `JobView`, `KnowledgeRowView`, ...) once, at the store boundary.

---

## 5. AppStore Slice Contract

| Slice | Holds | Sources |
|---|---|---|
| `settings` | `.env` map, repo dirs, durations, thresholds | settings.service |
| `providers` | per-provider config + `HealthState` (`unknown\|checking\|ok\|error`, message, latency) | providers.service |
| `knowledge` | rows (lazy, windowed), search query, edit buffer, validation report | knowledge.service |
| `queue` | render board: queued/running/done episodes, stage states, ETA, filters | queue.service + bridge events |
| `dashboard` | Production OS exports (report/dashboard/queue/projects/workers/resources), tick | queue.service |
| `runs` | known runs, per-run: manifest, execution report, events tail, stage states, live flag | runs.service + bridge events |
| `assets` | directory tree, selected path, thumbnails | assets.service |
| `productions` | current production, episode records, approvals, policy, templates | productions.service + runs.service |
| `insights` | learning proposals, analytics data, filters | insights.service |
| `editor` | open documents (script/storyboard/workflow/deliver), tabs, undo stacks, selection | services via stores |
| `layout` | workbench presets, dock zone contents, splits, floating windows, panel visibility | layout.service |
| `ui` | active workbench, palette, toasts, modals, connections center, theme | — |

---

## 6. IPC Contract (Rust commands)

All commands are async, return `Result<T, String>` (error string is a `code: message`
pair). Events are emitted with namespaced payloads.

| Command | Request | Response | Purpose |
|---|---|---|---|
| `app_version` | — | `{version, platform, arch, pr1me_version}` | About/update |
| `settings_load` | — | `SettingsModel` (parsed `.env` + dirs) | Boot |
| `settings_save` | `SettingsModel` (full) | `{ok}` | Persist `.env` |
| `providers_health` | `{provider: ProviderId}` | `HealthState` | Connection cards |
| `providers_health_all` | — | `HealthState[]` | Ambient dots |
| `env_probe` | `{name}` | `{value: string\|null}` | Test provider env |
| `fs_tree` | `{path, maxDepth, includeHidden}` | `FsEntry[]` | Asset browser |
| `fs_read_text` | `{path}` | `{content}` | JSON/CSV preview |
| `fs_watch` | `{paths}` | — (subscription) | Emits `fs:change` |
| `csv_read` | `{path, offset, limit}` | `{header, rows, total}` | KB manager |
| `csv_write` | `{path, header, rows}` | `{ok}` | KB save (atomic) |
| `csv_validate` | `{path}` | `ValidationReport` | Runs `validate_knowledge_csv.py` |
| `generate_start` | `{episodes: {index, topic, slug}[], production, seed?, maxAttempts?, publish?}` | `{runIds}` | Spawn `pr1me run` per episode |
| `generate_regen` | `{runId, scene?}` | `{ok}` | Re-run `--resume --seed <next>` (scene regen) |
| `generate_stop` | `{runId}` | `{ok}` | Kill process |
| `process_logs` | `{runId, tail}` | `{lines}` | Log tail (Terminal dock) |
| `run_list` | — | `RunSummary[]` | Explorer/Render board |
| `run_manifest` | `{runId}` | `RunManifest` | Storyboard/Workflow |
| `run_report` | `{runId}` | `ExecutionReport` | Stage states, QA, history |
| `run_events` | `{runId}` | `PipelineEvent[]` | Live stage rail |
| `run_history` | `{runId, sceneId}` | `RenderHistory` | Candidate strips |
| `workflow_read` | `{runId, sceneId}` | `BackendWorkflow` | Workflow graph |
| `image_open` | `{path}` | `{ok}` | Open in system viewer |
| `export_dashboard` | `{ticks?}` | `DashboardView` | Production OS exports |
| `production_list` | — | `ProductionSummary[]` | Library |
| `production_create` | `{name, template?, policy}` | `{production}` | Library |
| `production_load` | `{productionId}` | `ProductionModel` | Scopes the window |
| `production_save` | `ProductionModel` (full) | `{ok}` | Approvals/policy/episodes (product-owned, atomic) |
| `layout_save` | `{workbench, LayoutState}` | `{ok}` | Persist dock composition |
| `window_detach` | `{panelId}` | `{windowLabel}` | Floating panel window (multi-monitor) |
| `updater_check` | — | `UpdateInfo\|null` | Auto-update |

### Event payloads (Rust → UI)

| Event | Payload | Emitted |
|---|---|---|
| `run:started` | `{runId, processId, topic, episodeSlug}` | process spawn |
| `run:stage` | `{runId, stageId, status, offsetMs}` | events.json tail detect |
| `run:progress` | `{runId, stageId, attempt?, detail?}` | resource_sample/cache events |
| `run:candidate` | `{runId, sceneId, attemptId, imagePath}` | new history/attempt artifact |
| `run:completed` | `{runId, status, runDir, report}` | process exit 0 + manifest |
| `run:failed` | `{runId, error}` | process exit != 0 |
| `run:logline` | `{runId, line}` | stdout capture |
| `fs:change` | `{path, kind}` | watcher (debounced 200 ms) |
| `generate:queued` | `{runId, position}` | batch start |
| `updater:status` | `{state, version?, progress?}` | updater lifecycle |

---

## 7. Window & Layout Model

- One main window (title bar, workbench bar, activity bar, dock zones, editor area, status
  bar). **Floating windows** (Tauri multi-window) host detached panels for multi-monitor use;
  `window_detach` creates them, drag-back re-docks.
- Workbench = layout composition. `layout.store` holds per-workbench presets (zone contents,
  sizes, splits, panel visibility); `layout_save` persists to
  `config/ui-layout.json` (product-owned).
- Workbench switching is a state change, never a route change; the SPA has exactly one route.

---

## 8. Generation Flow (queue → live board)

1. Episodes are queued from anywhere (Script gallery, palette, Library, drag onto Render
   board). `render.vm` owns the board: queued → running → done.
2. `generate_start` → Rust spawns `pr1me run` (1 concurrent process, product-enforced)
   per episode with env from settings store, `--run-dir <output>/runs/<prod-slug>/<episode-slug>`
   and `--row <topic>`.
3. Watcher on the run dir emits `fs:change`; Rust tails `events.json` and re-emits
   `run:stage`/`run:progress`/`run:candidate`. The board's stage ring + rail advance; new
   thumbnails stream into candidate strips.
4. Exit 0: `run:completed`; store links the run to the episode, updates Explorer/Assets.
5. Exit != 0: `run:failed`; card turns error with code + Fix (Connections) and Retry
   (`--resume`).
6. **Regenerate (scene or episode)**: `generate_regen` re-spawns `--resume --seed <n+1>`.
   Upstream stage fingerprints are unchanged → cache hits; only `render_loop` re-runs.
   Deterministic, backend-untouched. Approval/candidate state is product-owned
   (`production.json`).

---

## 9. Concurrency & Limits

- One `pr1me` process at a time (product-enforced); the board shows honest queue positions.
- One fs watcher per run dir; debounced 200 ms; `events.json` tail poll 500 ms only while
  alive.
- CSV write is atomic (tmp + rename), exclusive lock via Rust mutex.
- All paths canonicalized; UI never receives paths outside
  `repo_root/output`, `repo_root/assets`, `repo_root/config`, `.env`, and
  `config/productions/**`.

---

## 10. Security

- Webview has no `shell` capability; all process execution goes through the Rust
  `process` module with a fixed allowlist (`pr1me.exe`, `validate_knowledge_csv.py`,
  `ffmpeg`).
- Secrets (DeepSeek key, YouTube tokens) are written to `.env` only, never to the store,
  never logged; UI shows masked values.
- IPC inputs validated in Rust (path traversal, size limits).
- Updater signatures via `tauri-plugin-updater` with public key embedded.