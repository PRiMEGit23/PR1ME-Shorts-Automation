# PR1ME Studio — UX Architecture v2 (LOCKED)

**Status:** LOCKED. Supersedes `UX_ARCHITECTURE.md` v1 (see `UX_REVIEW.md` for the critique).
Backend architecture remains FINAL (see `BACKEND_ARCHITECTURE.md`); this document governs only
the product layer.

---

## 1. The Concept: PR1ME is a Studio, not a Dashboard

PR1ME is a **production suite for AI Shorts** — an instrument, not a browser. It is organized as
**workbench modes** (DaVinci Resolve pages × Blender workspaces × Lightroom modules): the window
re-composes per mode around one creative task, project context persists across modes, and
everything visual is manipulable directly.

The artist's journey maps 1:1 to the workbenches:

```
Library → Script → Storyboard → Workflow → Render → Edit → Deliver → Insights
create    write/    plan &      inspect    run the   assemble  publish   learn
project   source    approve    prompts &  queue     timeline  & review  from results
          topics    scenes     graphs
```

---

## 2. Information Architecture (deliverable 3)

### 2.1 Workbenches (top-level modes — the ONLY top-level destinations)

| # | Workbench | Purpose | Mood |
|---|---|---|---|
| 1 | **Library** | Productions, recent episodes, welcome/onboarding, create production | Lightroom Library / Resolve Media |
| 2 | **Script** | Visual Knowledge Base browse, topic selection, narration/title/metadata editing | Lightroom Develop (text) |
| 3 | **Storyboard** | Live scene board: candidates, approve/regenerate, camera/lighting plan | Blender camera view / storyboard tool |
| 4 | **Workflow** | Prompt chain (15 stages) + ComfyUI graph canvas | Figma canvas / Resolve Fusion |
| 5 | **Render** | Render board: queued / running / done, live stage rails, ETA | Bambu Studio queue / Resolve Deliver |
| 6 | **Edit** | Timeline + player: scenes, audio, subtitles, overlays, markers | Resolve Cut page |
| 7 | **Deliver** | Publish targets, thumbnail pick, metadata review, publish | Resolve Deliver / YouTube Studio |
| 8 | **Insights** | Analytics + learning proposals | Linear / VS Code code health |

### 2.2 Dockable panels (available in EVERY workbench; shown per-workbench by default)

| Panel | Content |
|---|---|
| **Project Explorer** | Production tree: episodes, runs, artifacts, checkpoints |
| **Asset Browser** | Media grid: run outputs, assets workspace, config; drop targets |
| **Inspector** | Context properties of the current selection (scene, node, clip, provider, episode) |
| **Timeline** | Bottom dock: tracks + player (primary in Edit; optional elsewhere) |
| **Terminal** | Structured process logs + raw stdout of `pr1me` runs |
| **Connections** | Provider/connection center (health, config, test) |
| **Palette** | Modal overlay (never a panel) |
| **Welcome** | First-run + empty states |

### 2.3 Global chrome (never workbench-specific)

- **Title bar** — window controls; center: production switcher; right: queue count + provider health dots.
- **Workbench bar** — the eight modes with icons; right side: Generate, Connections, Preferences.
- **Activity Bar** (left rail) — toggles for dock panels (Explorer, Assets, Inspector, Timeline, Terminal).
- **Status bar** — version, active run, queue ETA, provider dots, shortcut hint.

---

## 3. Window Layout (deliverable 4)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ▬ titlebar: [· · ·]      ◆ PR1ME — ＜ Production: Core-FDM ▾ ＞        [ queue 3 ] [●●●] │
├──────────────────────────────────────────────────────────────────────────────┤
│ ▏ Workbench bar: [◆ Library][✎ Script][🎬 Storyboard][⚙ Workflow]           │
│ ▏                 [▸ Render][✂ Edit][📤 Deliver][📈 Insights]   [⊕ Generate][⛁ Connections][⚙] │
├──────┬──────────────────────────────────────────────────────┬────────────────┤
│ Act. │  DOCK ZONE LEFT        │  EDITOR AREA (tabs)          │  DOCK ZONE RIGHT│
│ Bar  │  Project Explorer      │  ┌─────────┬───────────┐     │  Inspector      │
│ ▤ ▤  │  ▾ Core-FDM            │  │ split A │  split B  │     │  (context)      │
│ ▤ ▤  │    ▸ episodes          │  │         │           │     │                 │
│ ▤ ▤  │    ▾ runs              │  │         │           │     │                 │
│ ▤ ▤  │  Asset Browser         │  └─────────┴───────────┘     │                 │
│ ▤ ▤  │  (when docked)         │                              │                 │
├──────┴────────────────────────┴──────────────────────────────┴────────────────┤
│ DOCK ZONE BOTTOM: Timeline | Terminal | Render board (per-workbench defaults)  │
├──────────────────────────────────────────────────────────────────────────────┤
│ ▏ status bar: pr1me 1.0.0 · run r-3f2a · queue ETA 1h 04m · ●●● ● ○ · Cmd+K │
└──────────────────────────────────────────────────────────────────────────────┘
```

Rules:

- **Three dock zones** (left, right, bottom) + a **tabbed editor area** (splittable, max 4
  splits). Every panel lives in a zone or floats.
- **Panels detach** into floating windows (multi-monitor): drag a panel header out of a zone →
  own window; re-dock by dragging back. Per-monitor layout is remembered.
- **Workbench presets**: each workbench has a default layout (which panels, where, what size).
  Layout changes persist per workbench and follow the production.
- **No page transitions.** Workbench switch = layout composition change (300 ms, panels slide);
  the editor area keeps open documents across switches.
- Min window 960×600; default 1440×900; remembers per-monitor geometry.

---

## 4. Navigation Philosophy (deliverable 5)

1. **Modes over links.** You never "go to" a queue page — you *switch to the Render workbench*.
   Mode switching is 3 keystrokes or 1 click; the current mode is always visible in the
   workbench bar.
2. **Palette is the universal jump.** `Cmd/Ctrl+Shift+P` reaches every command, workbench,
   episode, run, asset, and preference. The palette is the "address bar" of the product.
3. **Project context is persistent.** The production is a live context: everything (explorer,
   script browser, queues, inspector) is scoped to it. Switching production re-scopes the whole
   window.
4. **Spatial memory.** The workbench bar is fixed; the Activity Bar is fixed; panels hold their
   position. Moving the mouse less means thinking less.
5. **Depth only where meaningful.** Storyboard and Workflow are canvases (zoom/pan, no scrolling
   pages). Everything else is flat lists/filmstrips with virtualization.
6. **Forward-only creative flow, free lateral jumps.** Script → Storyboard → Render is the happy
   path, but you can jump anywhere; the pipeline state (not navigation) decides what's possible.

---

## 5. Interaction Model (deliverable 6)

| Pattern | Specification |
|---|---|
| **Selection** | Click selects (focus in inspector); `Cmd`+click multi-select; `Shift`+click range. Selection is always visible (accent ring), never a checkbox. |
| **Direct manipulation** | Drag episode cards into the render queue; drag assets onto scene candidates; drag clips along the timeline; drag panel headers to re-dock; drag palette rows onto a workbench. |
| **Candidate approval** | Storyboard scene shows a candidate strip (up to 6 thumbnails). Click to approve (accent border + check). This is a *product review layer* stored in the production manifest — the pipeline's chosen winner is pre-approved by default. |
| **Regenerate** | Per-scene action: spawns `pr1me run --row <topic> --resume --seed <n+1>` — upstream stage fingerprints are unchanged so only `render_loop` re-runs (deterministic, backend-untouched). New candidates stream into the strip. |
| **Non-modal inspector** | Selecting a scene/node/clip/episode/provider opens its properties in the Inspector. Edits apply live; no OK buttons. |
| **Documents** | Episodes open as tabs in the editor area (Script, Storyboard, Workflow, Deliver documents). Dirty tab = dot; `Cmd+S` saves (product-owned state). Undo/redo per document. |
| **Contextual menus** | Right-click on every surface: scene, candidate, node, clip, episode, provider, KB card, asset, tab. Always includes Copy path / Reveal in OS / Open in <workbench>. |
| **Keyboard-first** | Full shortcut system (§7); every list is arrow-navigable; Space plays/pauses; Esc dismisses overlays. |
| **Live streaming** | Runs update the UI as files appear (fs watch): stage rail advances, thumbnails pop in, log lines stream. No manual refresh anywhere. |
| **Hover affordance** | Hover reveals actions (icon buttons fade in); tooltips ≤120 ms; drag handles appear on hover. |
| **Empty states are actions** | No blank screens: welcome/onboarding, "Create production", "Select episodes", "Nothing rendering — queue from Script". |
| **Feedback discipline** | Every async action has: optimistic UI → spinner/progress → completion state. Errors surface inline (banner in the panel, not modals), with a Fix action where possible. |

---

## 6. Component Hierarchy (deliverable 7)

```
WindowShell
├── TitleBar (window controls · production switcher · queue chip · health dots)
├── WorkbenchBar (WorkbenchTab ×8 · GenerateButton · ConnectionsButton · PreferencesButton)
├── ActivityBar (PanelToggle ×5: Explorer, Assets, Inspector, Timeline, Terminal)
├── EditorArea
│   ├── EditorTabs (Tab: ScriptDocument | StoryboardDocument | WorkflowDocument | DeliverDocument)
│   ├── SplitView (nested, max 4)
│   └── EditorDocument (per type)
├── DockZone (left/right/bottom) → DockPanel
│   ├── PanelHeader (title · actions · menu · detach handle)
│   └── PanelBody
├── StatusBar (version · run chip · queue ETA · provider dots · hint)
├── FloatingWindow (detached panel host)
└── Overlays
    ├── CommandPalette (PaletteInput · PaletteResults · PaletteFooter)
    ├── ConnectionCenter (ConnectionCard ×7)
    ├── PreferencesModal (PrefNav · PrefSection)
    ├── Welcome (onboarding steps · recent productions)
    ├── ContextMenu
    ├── Tooltip / Toast / Modal
    └── ShortcutHelp (Cmd+Shift+/)

Domain components (per workbench)
├── Library: ProductionCard, ProductionGrid, EpisodeStrip, WelcomeWizard
├── Script: KnowledgeGallery (KnowledgeCard ×N), FilmstripNav, EpisodeTabs,
│           NarrationEditor (WordMeter, DurationMeter), TitleCard, MetaFields,
│           KnowledgeEditor (full-screen, 6 groups, JsonField, TagInput)
├── Storyboard: SceneBoard (canvas), SceneCard (CandidateStrip, SceneChips,
│           TransitionChip), ApproveMark, RegenerateButton, CameraPicker (pictograms),
│           LightingPicker, CompositionPicker, StageRail
├── Workflow: PromptChain (ChainNode ×15), GraphCanvas (WorkflowNode ×9, GraphEdge,
│           MiniMap, ZoomControls), ChainInspector (JsonView)
├── Render: RenderBoard (BoardColumn ×3: queued/running/done), EpisodeCard
│           (StageRing, ThumbCell, ProgressRail, EtaChip), QueueToolbar, LogTail
├── Edit: Timeline (Track ×4, Clip, Playhead, Marker, Ruler), Player
│           (TransportBar, Timecode, Volume)
├── Deliver: TargetCard (YouTube · Instagram-locked), ThumbnailPicker,
│           MetadataReview (JsonView), PublishButton
└── Insights: KpiRow (KpiCard), ChartPanel (BarChart, Donut, Gauge, Sparkline, Heatmap),
             ProposalList (ProposalCard → action buttons)

Primitives (Visual Design System §25): Button, IconButton, Toggle, Checkbox, Radio,
SegmentedControl, TextField, NumberField, TextArea, Select, ComboBox, Slider,
SearchField, Tabs, Breadcrumbs, Menu, ContextMenu, Tooltip, Popover, Modal, Sheet,
Toast, Kbd, StatusDot, Badge, Tag, ProgressRing, ProgressBar, Spinner, Skeleton,
TreeView, DataGrid, VirtualList, SplitView, TabBar, Panel, PanelToolbar, StatusBar,
JsonView, EmptyState, Stepper, DropZone, DragHandle
```

---

## 7. Keyboard Shortcuts (deliverable 8)

Modifier = `Cmd` on macOS / `Ctrl` on Windows. Global:

| Shortcut | Action |
|---|---|
| `Cmd+Shift+P` | Command palette |
| `Cmd+K` | Quick workbench switch (mini palette) |
| `Cmd+P` | Jump to episode / run / asset (fuzzy) |
| `Cmd+1 … Cmd+8` | Workbench 1–8 (Library … Insights) |
| `Cmd+,` | Preferences modal |
| `Cmd+Shift+D` | Connection Center |
| `Cmd+B` | Toggle left dock zone |
| `Cmd+Shift+E` / `A` / `I` / `T` / `` ` `` | Toggle Explorer / Assets / Inspector / Timeline / Terminal |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | Next / previous document tab |
| `Cmd+W` · `Cmd+Shift+T` | Close tab · reopen closed |
| `Cmd+Z` / `Cmd+Shift+Z` | Undo / redo |
| `Cmd+S` | Save product state (approvals, script edits, layout) |
| `Cmd+Shift+Enter` | Generate (queue selection) |
| `Esc` | Dismiss overlay / deselect |
| `Cmd+Shift+/` | Shortcut help overlay |
| `Cmd+Shift+F` | Search in current document (JSON/script) |

Workbench-specific:

| Workbench | Shortcuts |
|---|---|
| Library | `Cmd+N` new production · `Enter` open · `Space` preview selected episode |
| Script | `Cmd+Enter` queue episode · `Cmd+F` find · `↕` navigate gallery · `Cmd+E` open Knowledge Editor · `Cmd+D` duplicate row (editor) |
| Storyboard | `Space` play scene preview · `A` approve candidate · `R` regenerate scene · `N`/`P` next/prev scene · `+`/`-` zoom · `F` fit board · `Cmd+Enter` queue selected scenes as one run |
| Workflow | `W` fit graph · `+`/`-` zoom · `1`/`2` toggle Chain | Graph view · `Cmd+Click` multi-select node · `Del` clear selection |
| Render | `Cmd+Enter` render queue · `Space` pause/resume active · `↑`/`↓` navigate queue · `Del` remove item (confirm) · `L` log tail of selected |
| Edit | `Space` play/pause · `←`/`→` frame · `Shift+←/→` 1 s · `Home`/`End` jump · `M` marker · `I`/`O` mark in/out (preview range) |
| Deliver | `Cmd+Enter` publish selected (real) · `Cmd+Shift+Enter` dry-run publish · `T` thumbnail picker |
| Insights | `1`/`2` Analytics \| Learning · `Cmd+R` refresh exports |

---

## 8. Command Palette (deliverable 9)

- **Open:** `Cmd+Shift+P` (commands) / `Cmd+K` (workbench switch) / `Cmd+P` (jump). One
  implementation, scoped sources.
- **Sources (ranked, grouped):** commands (every registered action with id), workbenches,
  episodes of current production, recent runs, KB rows (insert into production), assets,
  preferences (deep-linked: "provider: ollama base url").
- **Row anatomy:** icon · title · contextual subtitle (production/run/topic) · right-aligned
  Kbd chip for the bound shortcut.
- **Fuzzy match** (subsequence scoring, 20 results max), arrow keys + Enter, `Tab` cycles
  groups, `Esc` closes, `Enter` on a command with args opens a mini-form.
- **Recents first** within each group; adaptive: palette remembers the last-used scope.
- Palette is also the **command source for undoable actions** (everything palette-executed
  lands in the active document's undo stack).

---

## 9. Project System (deliverable 10)

### 9.1 Model

```
Production  (config/productions/<slug>/production.json  — product-owned, backend-untouched)
├── identity: id, name, slug, created/updated
├── pipeline policy: default seed, max_attempts, publish default (dry-run/real)
├── scope: default KB filters (category, difficulty)
├── episodes: EpisodeRecord[]
└── ui: per-workbench layouts, palette recents

Episode = one Short = one KB row
├── topic (KB row key), row_index
├── status: drafted → queued → rendering → review → approved → rendered → delivered
├── seed (start), approvals: {scene_id: candidate_id|null}
├── run refs: run_id, run_dir (output/runs/<prod-slug>/<episode-slug>)
└── deliver: title/description overrides, publish state

Run  = backend artifact set (output/runs/<prod-slug>/<episode-slug>/)
└── manifest.json · execution_report.json · events.json · images/ · workflow/ ·
    history/ · video/ · thumbnail/ · checkpoints/
```

### 9.2 Rules

- **Runs are per-episode and stable**: `--run-dir output/runs/<prod-slug>/<episode-slug>` +
  `--row <topic>`; resume works because dir and row never change.
- **Approve state is product-owned** (production.json). The pipeline's QA winner is
  pre-approved; the artist may approve any candidate from the strip.
- **Regenerate** = re-run `--resume --seed <next>`; only `render_loop` re-executes (fingerprint
  change), everything upstream cache-hits. Documented in the Inspector as "Regenerate (new
  seed, deterministic)".
- **Templates:** New Production offers templates (default FDM photoreal · educational · batch
  campaign) that prefill policy + KB filters. No backend involvement.
- **Import:** create a production from the existing `output/runs/*` tree (adopt runs as episodes).
- **First run:** Welcome → create production → health check (LLM, ffmpeg, Kokoro) →
  Library shows first episodes.

---

## 10. Render Queue UX (deliverable 11)

The Render workbench is a **board**, not a table:

```
┌ Render ──────────────────────────────────────────────────────────────┐
│ [＋ Queue from Script] [▶ Render all] [⏸ Pause]      search ▾ [mode ▾] │
│ ┌─ QUEUED (4) ─────────┐ ┌─ RENDERING (1) ─────────┐ ┌─ DONE (12) ───┐ │
│ │ ▣ Gyroid           │ │ ▣ Infill              │ │ ✓ Layer Height │ │
│ │   ▓▓▓▓░░░░░░░░░░░  │ │   stage rail LIVE     │ │   ✓ …          │ │
│ │   ETA 18m · ⤒      │ │   7/15 render_loop    │ │   ETA 0 · ⤓    │ │
│ │ ▣ Injection mold   │ │   ▣ thumbnails stream │ │   ▣ …          │ │
│ │   ETA 24m · ⤒      │ │   [⏸] [■] [⟳]         │ │   [open ▾]     │ │
│ └────────────────────┘ └────────────────────────┘ └────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

- **Episode cards** (drag to reorder = spawn priority; product-level order only).
- **Stage ring** around the thumbnail (15 segments) + **progress rail** + **ETA chip**
  (deterministic runtime ticks from the estimator ÷ queue position).
- Running card expands: live stage rail (stage names with status), streaming thumbnails as
  `images/S*.png` appear, log-tail button (Terminal dock), pause/cancel/restart.
- Done card: click → Storyboard (review) · Deliver (publish) · "Open folder".
- Concurrency: 1 `pr1me` process at a time (product-enforced); the board communicates
  position honestly ("waiting — 2 ahead").
- Failure: card turns error state with error code banner + "Fix" (Connection Center) and
  "Retry" (`--resume`).

---

## 11. Storyboard Editor UX (deliverable 12)

The Storyboard workbench is a **scene board canvas**:

```
┌ Storyboard — Gyroid ─────────────────────────────────────────────────┐
│ [◆ Gyroid]  seeds:42   stage rail: ▓▓▓▓▓░░░░░░░  [⟳ Regenerate S2]  │
│ ┌─── S1 ───┐ ──▸ ┌─── S2 ───┐ ──▸ ┌─── S3 ───┐ ──▸ ┌─── S4 ───┐ … │
│ │ ▣ ▣ ▣ ▣  │      │ ▣ ▣ ▣ ▣  │      │ ▣ ▣ ▣ ▣  │      │ ▣ ▣ ▣ ▣  │  │
│ │ ★★▣▣    │      │ ▣ ▣ ★ ▣  │      │ ▣ ▣ ▣ ★  │      │ ★ ▣ ▣ ▣  │  │
│ │ push-in  │      │ orbit    │      │ dolly    │      │ tilt     │  │
│ │ rim      │      │ rim      │      │ soft     │      │ back     │  │
│ │ 6.2s     │      │ 7.1s     │      │ 5.4s     │      │ 8.0s     │  │
│ └──────────┘      └──────────┘      └──────────┘      └──────────┘  │
│  approved S2-S3          (zoom 50–200%, pan, fit)                    │
└──────────────────────────────────────────────────────────────────────┘
```

- **Scene cards** in a filmstrip: candidates (from `history/*/history.json` attempts and
  `images/`), approve star, camera/lighting/duration chips, transition arrow to next.
- **Approve/regenerate per scene** (see §5). Approved candidates get accent border + check;
  the pipeline winner is pre-approved.
- **Inspector (right)** for the selected scene: camera/lens/composition/lighting/motion
  pickers rendered as **pictogram preset grids** (static SVG, product-owned); values map to
  the KB scene fields and are *read-only overrides for preview* — the run uses KB values,
  so editing here explains and compares, not forks (determinism).
- **Stage rail** at top: live 15-stage pipeline status for the episode.
- **Scene order is script-locked** (determinism): cards show a lock glyph; reordering is a
  Script-workbench edit (narration order) which then re-runs.
- Canvas: zoom 50–200%, pan, fit, grid snap; thumbnails stream in live during render.

---

## 12. Workflow Visualizer UX (deliverable 13)

Two linked views in one workbench; `1`/`2` toggles, or side-by-side split.

**Prompt Chain** — the 15 stages as a vertical rail:

```
knowledge_load ✓ → educational_director ✓ → ai_director ✓ → visual_intelligence ✓ →
model_director ✓ → prompt_compiler ✓ → workflow_builder ✓ → render_loop ● (running) →
voice … → subtitles … → video_assembly … → video_render … → thumbnail … → metadata … → publisher …
```

- Node: status icon, stage name, duration ms, cache-hit badge (`⇄`), click → Inspector shows
  the stage contract (JSON from `artifacts/<stage>/output.json`) in a **JsonView** with
  copy/pretty-print.
- **Time travel:** clicking a *checkpoint* opens that stage's output as it was — no re-run.

**ComfyUI Graph** — canvas rendering of the `BackendWorkflow`:

```
 positive_prompt ──► ┌ profile: sdxl ──┐ ──► ┌ sampler: euler_a ─┐ ──► ┌ vae ─┐ ──► OUTPUT
 negative_prompt ──► │ cfg: 7 · steps  │      │ scheduler: …      │      └──────┘  1080×1920
                    │ resolution      │      │ loras: [3]        │
                    │ controlnet: [2] │      │ ip_adapter: …     │
                    │ upscaler: …     │      └───────────────────┘
                    └─────────────────┘
```

- Nodes derived from workflow JSON fields (profile, sampler, scheduler, vae, loras,
  controlnet, ip_adapter, upscaler, refiner, resolution, cfg/steps, prompt/negative) —
  honest rendering of real data, no invented topology.
- Node click → Inspector: value + **rationale** (from `WorkflowCompileLog.choices`).
- Zoom/pan/fit, minimap, multi-select; per-scene selector (S1–S5 + thumbnail) to compare
  profiles across scenes.

---

## 13. Asset Browser UX (deliverable 14)

- **Dockable panel** (Activity Bar), default-left; not a workbench.
- **Modes:** Grid (thumbnails, 4–8 cols, resizable) · Filmstrip (episodes/scenes) · Tree
  (folders). Tabs: **Run media** (current production's `images/audio/video/thumbnail`) ·
  **Assets** (`assets/`) · **Config/Knowledge** (CSV).
- **Drop targets:** drag an asset onto a scene card (attach as reference in the episode
  record — product-owned; the pipeline is not re-run for references), onto a Deliver
  thumbnail picker, or into a folder (reorganize assets workspace only).
- Hover: quick preview (image zoom, video seek-to-first-frame, audio waveform), reveal in OS,
  copy path, "open in Editor/Edit". Right-click context menu on everything.
- **Live:** new run artifacts appear automatically (fs watch); badge on the panel when new
  media arrived.

---

## 14. Timeline UX (deliverable 15)

Edit workbench = **Cut page** for a Short:

```
┌ Edit — Gyroid ──────────────────────────────────────────────────────────┐
│ [⏵ 00:00:12:08]  [◂][▸]  [│] [markers]        ruler 0…38s                │
│ ┌ Video    │ S1 ▣ 6.2s │ S2 ▣ 7.1s │ S3 ▣ 5.4s │ S4 ▣ 8.0s │ S5 ▣ … │ │
│ ├ Audio    │ narration ────────────────────────────── ▔▔▔ music ▔▔    │ │
│ ├ Subtitles│ [narration.srt ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔]                       │ │
│ └ Overlays │ text: 3    │                                                  │
│  preview: [video player — scrubs with playhead]                            │
└───────────────────────────────────────────────────────────────────────────┘
```

- **Tracks:** Video (scene clips with thumbnails), Audio (narration + music), Subtitles,
  Overlays. Clip widths = deterministic scene durations.
- **Scrub** preview player: local `video/short.mp4` when rendered; before that, clips show
  duration blocks with placeholder motion ("plan preview") and `Space` plays a silent
  simulated cut.
- **Markers** (`M`) — saved product-side; **in/out range** for preview loop.
- Clips link back: click clip → Storyboard scene; thumbnails = approved candidates.
- **Deliver**: publish state flows from Edit → Deliver with one click (`Cmd+Enter`).

---

## 15. Provider Management UX (deliverable 16)

- **Connection Center** (`Cmd+Shift+D`): one panel — seven **connection cards**
  (Ollama, DeepSeek, ComfyUI, Kokoro, ffmpeg, YouTube, Instagram-locked).
  Card: status light (unknown/checking/ok/error), latency ms, key config fields inline,
  actions: Test · Edit (Inspector) · Reveal `.env`.
- **Ambient health:** status bar + title bar dots aggregate providers; a failing provider
  opens the Center from its banner.
- **Auto-detect banners:** Ollama/ComfyUI/Kokoro/ffmpeg local defaults are probed on boot;
  found → green without touching settings; not found → card offers "Start" hint (paths) —
  never a wall of form fields.
- Preferences modal (general + publish defaults) stays minimal and searchable
  (`Cmd+,`). No provider content in Preferences — it lives in the Center.
- Secrets: masked, never logged, written to `.env` only.

---

## 16. Learning Dashboard UX (deliverable 17)

Insights workbench → **Learning** tab:

- **Proposal cards** from the learning engine exports (improvement proposals, knowledge
  diffs, failure patterns). Each card: pattern title, evidence (n failures, affected
  category), and concrete actions:
  - *Retry failed episodes* → queues them in Render.
  - *Open row in Script editor* → jump to the KB row (suggested edit).
  - *Adopt suggestion into defaults* → writes product-level policy (production.json) —
    never backend prompts.
- Nothing is auto-applied; every proposal is an explicit, undoable action.

---

## 17. Analytics UX (deliverable 18)

Insights workbench → **Analytics** tab:

- **KPI row:** success rate, mean QA, throughput/day, total episodes, ETA-style "time in
  queue" — computed from Production OS exports + run reports (read-only, backend exports
  verbatim).
- **Charts:** success rate over time (sparkline), mean QA by category (bars), status donut,
  QA score distribution, publish performance (views/duration — placeholders until real
  data), render cost per episode (tick time).
- **Filters:** production, time range, category, difficulty. All charts share the filter bar.
- Every chart is exportable (PNG/CSV) and hover-explains its source export file.
- Clicking a chart segment drills into the underlying run list → Render/Storyboard.

---

## 18. Per-Workbench Default Layouts

| Workbench | Left dock | Editor area | Right dock | Bottom dock |
|---|---|---|---|---|
| Library | Explorer | Production grid | (closed) | (closed) |
| Script | Explorer | Knowledge gallery + editor tabs | Inspector | Timeline (plan) |
| Storyboard | Explorer | Scene board (canvas) | Inspector | Terminal |
| Workflow | Explorer | Chain \| Graph (split) | Inspector | Terminal |
| Render | Explorer | Render board (full-bleed) | Inspector | Terminal |
| Edit | Explorer | Timeline + Player | Inspector | (Timeline is the editor) |
| Deliver | Explorer | Deliver documents | Inspector | Terminal |
| Insights | Explorer | Analytics \| Learning | (closed) | Terminal |

All layouts persist per workbench; panels detachable anywhere (multi-monitor).