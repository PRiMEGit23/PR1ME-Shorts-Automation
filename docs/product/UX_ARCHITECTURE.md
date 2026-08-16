# PR1ME Studio — UX Architecture (LOCKED)

**Status:** LOCKED. Naming, layout, and navigation in this document are fixed and must
be implemented exactly.

---

## 1. Information Architecture

```
PR1ME Studio
├── Dashboard            (default route)
├── Generate
├── Queue
├── Projects
├── Knowledge Base
├── Assets
├── History
├── Workflow Viewer      (route /runs/[runId], opened from History/Projects)
└── Settings
```

---

## 2. Window Shell

- Titlebar (native decorations on; custom drag region only for the dock).
- Left **Sidebar** (64px, icon rail, collapsible to 200px labeled rail).
- Bottom **Dock** (48px): global actions — **Generate** (primary button),
  run status chip, provider health dot, Settings gear.
- **Command Palette** (`Ctrl+K` / `Ctrl+P`): fuzzy search over all actions, routes,
  recent runs, KB rows. `Esc` closes; `Enter` executes.
- Global keyboard shortcuts: `Ctrl+K` palette, `Ctrl+1..9` routes,
  `Ctrl+Shift+G` generate, `Ctrl+,` settings.
- Toasts bottom-right above dock; modals centered; all overlay on a dimmed scrim.

### 2.1 Sidebar rail order (locked)

1. Dashboard
2. Generate
3. Queue
4. Projects
5. Knowledge Base
6. Assets
7. History
8. Settings

---

## 3. Component Hierarchy

```
WindowShell
├── Sidebar
│   ├── SidebarItem (icon, label, active, badge)
│   └── SidebarFooter (health dot, version)
├── Dock
│   ├── GenerateButton        (primary CTA)
│   ├── RunStatusChip         (idle | running n | failed n)
│   ├── ProviderHealthDot     (aggregate of providers)
│   └── SettingsTrigger
├── CommandPalette
│   ├── PaletteInput
│   ├── PaletteResults (PaletteResultItem: icon, title, keywords, kbd)
│   └── PaletteFooter (hint bar)
└── Slot (route page)
    ├── PageHeader (title, subtitle, actions)
    ├── ... page-specific layout ...
    └── StatusBar (optional context strip)

Shared primitives: Button, IconButton, Input, Select, Checkbox, Toggle, Slider,
Badge, Tag, Tooltip, Kbd, Spinner, ProgressBar, Modal, Drawer, Toast, EmptyState,
Skeleton, DataTable, SearchInput, FilterBar, Pagination, JsonView, Sparkline,
BarChart, Donut, Gauge, Timeline, VideoPlayer, ImageCard, ImageStrip
```

---

## 4. Navigation Flow

```
boot → Dashboard
Dashboard → Generate / Queue / Projects / Knowledge Base / Assets / History / Settings
Generate → (success) → Queue (job appears) → Workflow Viewer (on click)
Queue → Workflow Viewer / Projects
Projects → Workflow Viewer (run click) / Generate (re-run)
History → Workflow Viewer (manifest click)
Workflow Viewer → Assets (image click) / History (QA click)
Settings → (save) → back to previous route
Any route → Command Palette → jump to route/action
```

---

## 5. Page Wireframes (ASCII, locked)

### 5.1 Window Shell

```
┌────────────────────────────────────────────────────────────────┐
│ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ (native titlebar) ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ │
│ ┌────┐ ┌────────────────────────────────────────────────────┐  │
│ │ ⬛ │ │  PageHeader  [title]              [action buttons]  │  │
│ │ ⬛ │ │ ┌──────────────────────────────────────────────────┐ │  │
│ │ ⬛ │ │ │                                                  │ │  │
│ │ ⬛ │ │ │              page content (scroll)               │ │  │
│ │ ⬛ │ │ │                                                  │ │  │
│ │ ⬛ │ │ └──────────────────────────────────────────────────┘ │  │
│ │ ⬛ │ └────────────────────────────────────────────────────┘  │
│ │ ⬛ │                                                          │
│ └────┘ ┌──────────────────────────────────────────────────────┐ │
│        │ [ ● Generate ] [ 3 running ] [ ●●● providers ok ] [⚙]│ │  Dock
│        └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 5.2 Dashboard

```
PageHeader: Production Dashboard            [Refresh]
┌──────────────────────────┬─────────────────────────────────────────┐
│ KPI row                  │                                         │
│  Total Runs    Success%  │  Queue:        [bars by status]         │
│  [ 128 ]       [ 87% ]   │  pending running paused retry failed    │
│  Completed    ETA        │                                         │
│  [ 112 ]       [ 1h 12m ]│  Running jobs:                         │
│  Mean QA      Throughput │  • topic …         stage 7/15  ▓▓▓▓░░  │
│  [ 92.4 ]      [ 14/day ]│  • topic …         stage 3/15  ▓▓░░░░  │
├──────────────────────────┼─────────────────────────────────────────┤
│ Success rate (donut)     │  History (recent 20, table):            │
│  ✓ 87% / ✗ 8% / ⟳ 5%    │  run | topic | status | dur | QA | ⚡  │
│  Mean QA (gauge)         │  …                                      │
└──────────────────────────┴─────────────────────────────────────────┘
```

### 5.3 Generate

```
PageHeader: Generate                        [Generate Batch ▸]
┌──────────────────────────────────────────────────────────────────┐
│ Scope                                                             │
│ [Knowledge Base rows: ▼ selected 24 of 400 ]  [Queue: ▼ Selected │
│                                                      rows only ] │
│ Search rows  [____________]  Category [All ▾]  Difficulty [All ▾]│
│ ☐ topic A            B  Slicer & Print Settings                  │
│ ☐ topic B            I  Materials & Filament                     │
│ ☐ …            (paginated 25)                                    │
│ Project      [New Project… ▾]   Seed [ 42 ]  Max attempts [ 3 ]  │
│ Publish      [ ] Upload to YouTube after render (dry-run default)│
│ ─────────────────────────────────────────────────────────────────│
│  Preview: 24 rows × 15 stages ≈ 3h 12m est.    [Generate ▸]      │
└──────────────────────────────────────────────────────────────────┘
```

### 5.4 Queue (Batch Queue Manager)

```
PageHeader: Queue                          [Pause all] [Resume all] [Clear]
Filters: [status ▾] [type ▾] [project ▾]  Search [______]
┌──────────────────────────────────────────────────────────────────┐
│ pending 12 | running 2 | paused 1 | retry 0 | completed 89 | …   │
│ Position │ Topic │ Type │ Status │ Priority │ ETA │ Actions      │
│ 1        │ …     │ video│ running│ High     │ 4m  │ ■ ⏸ ⟳ ⋯      │
│ 2        │ …     │ image│ pending│ High     │ 8m  │ ⏸ ⋯           │
│ …                                                               │
└──────────────────────────────────────────────────────────────────┘
ETA header: completion = f(remaining runtime ticks / workers)
```

### 5.5 Projects

```
PageHeader: Projects                     [New Project]
┌──────────────────────────────────────────────────────────────────┐
│ Card grid (2-col):                                               │
│ ┌───────────────────┐  ┌───────────────────┐                     │
│ │ name              │  │ name              │                     │
│ │ 12 runs · 1 live  │  │ 5 runs · done     │                     │
│ │ progress ▓▓▓▓▓░░░ │  │ progress ▓▓▓▓▓▓▓▓  │                     │
│ │ [Open] [Resume]   │  │ [Open]            │                     │
│ └───────────────────┘  └───────────────────┘                     │
└──────────────────────────────────────────────────────────────────┘
Project detail (drawer): runs list → Workflow Viewer
```

### 5.6 Knowledge Base (CSV Manager)

```
PageHeader: Knowledge Base      [Validate] [Add Row] [Save Changes]
Search [________________]  Category [▾]  Difficulty [▾]  Invalid only ☐
Rows: 400 · validation: 0 errors · 3 warnings       Export ▾
┌──────────────────────────────────────────────────────────────────┐
│ ☐ topic | diff | category | words | scenes | validity            │
│ ☐ …    | B    | Slicer   | 78    | 5      | ✓  ✓  ✓              │
└──────────────────────────────────────────────────────────────────┘
Row editor (right drawer):
  topic [______________________]  difficulty [B ▾]  category [▾]
  subcategory [____]  viewer_level [B ▾]
  keywords [tag input]  search_intent [____________________]
  script [textarea 20–35s check ⓘ]  scene_count [5]
  scene_plan_json [JsonView ⇱ tabs: scene 1..5]   (13 fields each)
  image_prompt_pack_json [JsonView]  thumbnail [preview card]
  … (all 39 fields, grouped: Content | Script | Visual | Thumbnail
                          | Metadata | QA)
  [Cancel] [Save] (Save triggers validate; errors block save)
```

### 5.7 Assets

```
PageHeader: Assets                          [Open folder]
┌──────────────┬──────────────────────────────────────────────────┐
│ Tree         │  Grid (thumbnails, 6-col):                        │
│ ▾ output     │  ┌────┐ ┌────┐ ┌────┐ …                           │
│   ▾ runs     │  │img │ │img │ │img │                             │
│     ▸ 2026…  │  └────┘ └────┘ └────┘   name / path / size        │
│   ▸ assets   │  Click → preview lightbox (image/video/audio)     │
│ ▸ config     │                                                   │
└──────────────┴──────────────────────────────────────────────────┘
```

### 5.8 History

```
PageHeader: Render History   [filter: run ▾] [search topic]
┌──────────────────────────────────────────────────────────────────┐
│ Run | Topic | Scene | Attempts | Winner QA | Verdict | link      │
│ r-… | gyroid| S2   | 3        | 94.2     | PASS   | [view ▸]    │
└──────────────────────────────────────────────────────────────────┘
Click → Workflow Viewer (QA tab shows 8 score bars + evolution list)
```

### 5.9 Workflow Viewer (`/runs/[runId]`)

```
PageHeader: Run r-… · topic            [Open folder] [Re-run ⟳]
Tabs: [Storyboard] [Prompt Chain] [ComfyUI Workflow] [QA & History]
Storyboard tab:
┌──────────────────────────────────────────────────────────────────┐
│ Timeline rail: S1 ▸ S2 ▸ S3 ▸ S4 ▸ S5 ▸ THUMB  (stage states)    │
│ ┌────────────┐  Scene card:                                     │
│ │  S2 image  │  camera: slow push-in   lighting: studio rim     │
│ │  (thumb)   │  composition: rule-of-thirds   mood: technical   │
│ └────────────┘  transition: crossfade   duration: 6.2s          │
└──────────────────────────────────────────────────────────────────┘
Prompt Chain tab: 15-stage rail ▸ expanded stage → JSON contract
ComfyUI tab: workflow JSON (JsonView) + nodes list + profile chip
QA & History: per-scene attempts timeline, 8 score bars, evolution
```

### 5.10 Settings

```
PageHeader: Settings                         [Save] [Restore defaults]
Nav (left, sticky): General | Providers | Knowledge | Publish | About
General:  repo dirs (read-only), log level, durations, critic toggles
Providers (cards, one per provider):
  [Ollama]      base url, model, key(opt)        health: ● ok
  [DeepSeek]    api key (masked), base url, model health: ● error
  [ComfyUI]     base url, workflow file          health: ● ok
  [Kokoro]      base url, voice, sample rate     health: ● unknown
  [ffmpeg]      binary path (auto-detect)        health: ● ok
  [YouTube]     client id, secret, tokens (masked)  health: ● ok
  [Instagram]   coming soon (disabled)
Knowledge:  knowledge_base.csv path, topics.csv path, validate on save
Publish:    default visibility, category, tags, made-for-kids
About:      version, pr1me version, check for updates [button]
```

---

## 6. Interaction & Motion Rules (locked)

- Primary CTA **Generate** always visible in the Dock; disabled while a batch is running
  with tooltip "Batch in progress".
- Status transitions animate (color + icon morph), never layout jump: keep rows at
  fixed height, use 200 ms ease for state changes.
- Skeleton loaders on first paint of every list; empty states carry a primary action.
- Palette opens in 120 ms scale+fade; list virtualization for > 200 rows.
- All destructive actions confirm in a modal ("Cancel run", "Delete row").
- Keyboard-first: every list supports arrow navigation + Enter; focus ring visible.
- Tooltips appear on hover (120 ms) for icon-only controls.
- Long operations (spawn, health check) show inline progress, never blocking modals.