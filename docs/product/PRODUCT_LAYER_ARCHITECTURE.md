# PR1ME Studio — Product Layer Architecture (LOCKED)

**Status:** LOCKED. Governs everything under `app/`.

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
│   ├── routes/
│   │   ├── +layout.svelte          (WindowShell: sidebar + dock + palette)
│   │   ├── +page.svelte            (Dashboard)
│   │   ├── generate/+page.svelte
│   │   ├── queue/+page.svelte      (Batch Queue Manager)
│   │   ├── projects/+page.svelte   (Project Manager)
│   │   ├── knowledge/+page.svelte  (CSV Knowledge Base Manager)
│   │   ├── assets/+page.svelte     (Asset Browser)
│   │   ├── history/+page.svelte    (Render History)
│   │   ├── runs/[runId]/+page.svelte      (Workflow Viewer)
│   │   └── settings/+page.svelte   (Settings + Providers)
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
│   │   │   ├── providers.service.ts    (health checks)
│   │   │   ├── runs.service.ts         (list/watch runs, artifacts)
│   │   │   ├── generate.service.ts     (spawn pr1me run, monitor)
│   │   │   ├── queue.service.ts        (production os exports)
│   │   │   ├── knowledge.service.ts    (CSV read/write/validate)
│   │   │   ├── assets.service.ts       (file tree, thumbnails)
│   │   │   └── projects.service.ts     (project CRUD)
│   │   ├── stores/
│   │   │   ├── app.store.ts        (root store, slice wiring)
│   │   │   ├── settings.store.ts
│   │   │   ├── providers.store.ts
│   │   │   ├── knowledge.store.ts
│   │   │   ├── queue.store.ts
│   │   │   ├── runs.store.ts
│   │   │   ├── assets.store.ts
│   │   │   ├── projects.store.ts
│   │   │   ├── dashboard.store.ts
│   │   │   └── ui.store.ts         (palette, toasts, navigation)
│   │   ├── viewmodels/
│   │   │   ├── dashboard.vm.ts
│   │   │   ├── generate.vm.ts
│   │   │   ├── queue.vm.ts
│   │   │   ├── projects.vm.ts
│   │   │   ├── knowledge.vm.ts
│   │   │   ├── assets.vm.ts
│   │   │   ├── history.vm.ts
│   │   │   ├── workflow.vm.ts
│   │   │   └── settings.vm.ts
│   │   └── components/
│   │       ├── shell/              (WindowShell, Sidebar, Dock, TitleBar, CommandPalette)
│   │       ├── layout/             (AppGrid, Panel, PanelGroup, SplitPane, StatusBar)
│   │       ├── primitives/         (Button, IconButton, Input, Select, Checkbox, Toggle,
│   │       │                        Slider, Badge, Tag, Tooltip, Kbd, Spinner, Progress,
│   │       │                        Modal, Drawer, Toast, EmptyState, Skeleton)
│   │       ├── data/               (DataTable, VirtualList, SearchInput, FilterBar,
│   │       │                        Pagination, CellBadge, JsonView)
│   │       ├── charts/             (Sparkline, BarChart, Donut, Gauge, Timeline)
│   │       ├── media/              (VideoPlayer, ImageStrip, ImageCard, AudioPlayer)
│   │       └── domain/             (GenerateButton, RunStatusBadge, StagePipeline,
│   │                               WorkflowGraph, ProviderCard, RowEditor, JobRow)
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
│   │   │   ├── providers.rs        (health probes)
│   │   │   ├── process.rs          (spawn/kill sidecar, stream stdout)
│   │   │   ├── fs.rs               (read dir, watch dir, read file, thumbnails)
│   │   │   ├── csv.rs              (read/write/validate CSV via sidecar)
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
│ ViewModel (plain TS classes)      — orchestrates one page  │
│                                    (formatting, validation,│
│                                    command sequencing)     │
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
| `knowledge` | rows (lazy, paginated), search query, edit buffer, validation report | knowledge.service |
| `queue` | queue snapshot, status counts, selected job, filters | queue.service |
| `dashboard` | exports (report/dashboard/queue/projects/workers/resources), tick | queue.service |
| `runs` | known runs, per-run: manifest, execution report, events tail, stage states, live flag | runs.service + bridge events |
| `assets` | directory tree, selected path, thumbnails | assets.service |
| `projects` | project list, per-project runs, create/resume actions | projects.service + runs.service |
| `ui` | active route, palette open, toasts, modals, sidebar/dock state, theme | — |

---

## 6. IPC Contract (Rust commands)

All commands are async, return `Result<T, String>` (error string is a `code: message`
pair). Events are emitted with namespaced payloads.

| Command | Request | Response | Purpose |
|---|---|---|---|
| `app_version` | — | `{version, platform, arch, pr1me_version}` | About/update |
| `settings_load` | — | `SettingsModel` (parsed `.env` + dirs) | Boot |
| `settings_save` | `SettingsModel` (full) | `{ok}` | Persist `.env` |
| `providers_health` | `{provider: ProviderId}` | `HealthState` | Provider card probes |
| `env_probe` | `{name}` | `{value: string\|null}` | Test provider env |
| `fs_tree` | `{path, maxDepth, includeHidden}` | `FsEntry[]` | Asset browser |
| `fs_read_text` | `{path}` | `{content}` | JSON/CSV preview |
| `fs_watch` | `{paths}` | — (subscription) | Emits `fs:change` |
| `csv_read` | `{path, offset, limit}` | `{header, rows, total}` | KB manager |
| `csv_write` | `{path, header, rows}` | `{ok}` | KB save (atomic) |
| `csv_validate` | `{path}` | `ValidationReport` | Runs `validate_knowledge_csv.py` |
| `generate_start` | `{rows: {index, topic}[], projectId?, seed?, maxAttempts?, publish?}` | `{runIds}` | Spawn `pr1me run` per row |
| `generate_stop` | `{runId}` | `{ok}` | Kill process |
| `generate_resume` | `{runId}` | `{ok}` | Re-spawn with `--resume` |
| `process_logs` | `{runId, tail}` | `{lines}` | Log tail viewer |
| `run_list` | — | `RunSummary[]` | Scan `output/runs/*` |
| `run_manifest` | `{runId}` | `RunManifest` | Workflow viewer |
| `run_report` | `{runId}` | `ExecutionReport` | History/QA |
| `run_events` | `{runId}` | `PipelineEvent[]` | Timeline |
| `run_history` | `{runId, sceneId}` | `RenderHistory` | Render history |
| `workflow_read` | `{runId, sceneId}` | `BackendWorkflow` | Workflow viewer |
| `image_open` | `{path}` | `{ok}` | Open in system viewer |
| `export_dashboard` | `{ticks?}` | `DashboardView` | Production OS exports |
| `project_create` | `{name, rows[], settings}` | `{projectId}` | Project manager |
| `project_list` | — | `ProjectView[]` | Project manager |
| `updater_check` | — | `UpdateInfo\|null` | Auto-update |

### Event payloads (Rust → UI)

| Event | Payload | Emitted |
|---|---|---|
| `run:started` | `{runId, processId, topic}` | process spawn |
| `run:stage` | `{runId, stageId, status, offsetMs}` | events.json tail detect |
| `run:progress` | `{runId, stageId, attempt?, detail?}` | resource_sample/cache events |
| `run:completed` | `{runId, status, runDir, report}` | process exit 0 + manifest |
| `run:failed` | `{runId, error}` | process exit != 0 |
| `fs:change` | `{path, kind}` | watcher (debounced) |
| `generate:queued` | `{runId, position}` | batch start |
| `updater:status` | `{state, version?, progress?}` | updater lifecycle |

---

## 7. Generation Flow (one-click Generate)

1. `GenerateViewModel` collects scope: rows selected in Knowledge store (or `--row`),
   project binding, `seed`, `max_attempts`, publish toggle.
2. `generate_start` → Rust spawns `pr1me run` per row with env from settings store
   (`PR1ME_*` merged over `.env`), `--run-dir <output>/runs/<runId>/<topic>`.
3. Watcher on `<runDir>` emits `fs:change`; Rust tails `events.json` and re-emits
   `run:stage`/`run:progress`. Store updates stage states; StagePipeline renders the 15
   stage rail.
4. On exit 0: Rust reads `manifest.json` + `reports/execution_report.json`, emits
   `run:completed`; store links run to project, refreshes history/assets.
5. Failure: exit 1 + `run:failed`; error banner from error code; Retry button
   (`generate_resume`).

---

## 8. Concurrency & Limits

- Batch generation runs sequentially per project (1 concurrent `pr1me` process);
  queue view shows planned runs with position.
- One fs watcher per run dir; debounced 200 ms.
- `events.json` tail poll 500 ms only while process alive.
- CSV write is atomic (tmp + rename), exclusive lock via Rust mutex.
- All paths are canonicalized; UI never receives paths outside
  `repo_root/output`, `repo_root/assets`, `repo_root/config`, `.env`.

---

## 9. Security

- Webview has no `shell` capability; all process execution goes through the Rust
  `process` module with a fixed allowlist (`pr1me.exe`, `validate_knowledge_csv.py`,
  `ffmpeg`).
- Secrets (DeepSeek key, YouTube tokens) are written to `.env` only, never to the store,
  never logged; UI shows masked values.
- IPC inputs validated in Rust (path traversal, size limits).
- Updater signatures via `tauri-plugin-updater` with public key embedded.