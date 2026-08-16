# PR1ME Studio — Visual Design System v3: The Visual DNA (LOCKED · SINGLE SOURCE OF TRUTH)

**Status:** LOCKED. Supersedes `VISUAL_DESIGN_SYSTEM.md` v2. This document is the single
source of truth for every future UI implementation.
**Boundaries honored:** Backend, runtime, CLI, UX flow, information architecture, and
component hierarchy are LOCKED and unchanged. This document defines ONLY how PR1ME looks,
feels, and moves.

---

# PART A — BRAND

## 1. Brand Personality (deliverable 1)

**The PRIME lens story.** *PR1ME* is named after the prime lens — a fixed-focal-length lens
beloved by cinematographers for its sharpness, speed, and creative discipline. PR1ME Studio
is the prime lens of AI Shorts production: one instrument, one craft, maximum clarity.

| Trait | Manifestation |
|---|---|
| **Precise** | Everything is measured: 4 px grid, mono tabular numerals, timecode everywhere. No decorative looseness. |
| **Cinematic** | The language of film: film strips, aperture, exposure, timecode, storyboards, dailies. |
| **Engineered** | Technical-drawing restraint: thin rules, tolerance-like margins, blueprint grids in canvas views. |
| **Confident** | Quiet chrome, loud content. The UI never shouts; the media does. |
| **Fast** | Feels instant: 100–300 ms motion, streaming thumbnails, zero layout shift. |
| **Dark & calm** | A dark room is where films get made. Surfaces recede; content glows. |

**Voice:** short, declarative UI copy. "Queue 12 episodes." "3 failed. Retry?" Never
"Please configure your provider settings to proceed."

**Anti-personality (never):** skeuomorphic film grain, glassmorphism froth, gradients on
chrome, emoji in UI, rounded "friendly" 16 px radii on controls, pastel status colors,
light-mode-only features, decorative animation.

**Tagline:** *Make the Short.*

**Logo mark:** an aperture mark — a 5-blade ring enclosing the numeral **1**. Rendered as a
single stroke glyph; used at 20/24/32/48 px. Never recolored (always PRIME Blue on
surface-0, or surface-0 on accent in brand moments). Wordmark: `PR1ME` in
`--font-ui`, 600, tracking `0.12em`, with `STUDIO` as a caption underneath in `--label`.

## 2. Design Philosophy (deliverable 2)

1. **Instrument, not website.** The window is a tool: dense, keyboard-first, no marketing.
2. **Content is the interface.** Thumbnails, frames, and waveforms carry meaning; chrome
   is 1 px lines and quiet type.
3. **Color is information.** Monochrome-blue chrome; hue reserved for status, selection,
   and data. If a color isn't meaningful, it isn't used.
4. **One source of truth.** Every value in this document is a token. Components consume
   tokens; tokens never change per-screen.
5. **Determinism is the aesthetic too.** Layouts are fixed-height, grids are fixed,
   nothing reflows mid-interaction. The UI is as deterministic as the pipeline.
6. **Calm motion, decisive feedback.** 100–300 ms; state always acknowledged; never
   decorative.
7. **Respect the artist's attention.** Compact density, tabular numbers, zero noise.

## 3. Visual Language (deliverable 3)

**Core motifs:**

- **The film strip** — perforation rhythm (repeated 6×12 px notches) used sparingly: panel
  header underlines, dividers between scenes, the Workbench bar's active-tab underline.
- **Timecode** (`HH:MM:SS:FF`) — the signature numeric unit. Player, timeline, markers,
  and ETA all render as timecode.
- **The aperture ring** — appears in the logo, the stage ring (15-segment progress
  ring), and the loading states.
- **Blueprint grid** — 24 px dot grid in canvas workbenches (Storyboard, Workflow),
  `--border-subtle` dots, only inside canvas views.
- **The signal rule** — one accent at a time. An approved thumbnail is green, a running
  stage is blue, a failure is red — never two at once in one element.

**Texture:** none. Flat fills + 1 px borders + value-based depth. No noise, no gradients
except the two brand moments (§33).

## 4. Shape Language (deliverable 4)

| Radius | Value | Used by |
|---|---|---|
| `--radius-sm` | 4 px | chips, badges, tags, checkboxes, kbd, JSON nodes |
| `--radius-md` | 6 px | buttons, inputs, selects, cards, thumbnails, episode cards, scene cards |
| `--radius-lg` | 12 px | modals, sheets, palette, floating windows, toast groups |
| `--radius-full` | 999 px | pills, status dots, segmented thumb, progress ring cap |

Rules:

- Corners are **never** sharper than 4 px or rounder than 12 px on containers; controls
  stay at 6 px (no pill buttons — pills are for chips and status only).
- Thumbnails (9:16) use `--radius-md`; the inner image is hard-clipped (no inner radius).
- Borders: 1 px `--border-*` for all chrome; 2 px accent borders only for selection and
  approved thumbnails; 2 px focus rings.
- Status dots are the only perfect circles; the stage ring is a circle; everything else
  is squared.

---

# PART B — CHROME & COMPONENTS

## 5. Window Chrome (deliverable 5)

- **Custom title bar** (requires `decorations: false`): 40 px, `--surface-0`, 1 px bottom
  `--border-subtle`. Drag region across the full bar; double-click toggles maximize.
- **Layout (left → right):** window menu glyph ◆ · `PR1ME` wordmark (20 px, tracked) ·
  production switcher `◆ Production: Core-FDM ▾` (ghost button, centered-left) · spacer ·
  queue chip `(queue 3)` · provider dots `●●● ○` · window controls (min/max/close, 34 px
  wide each, hover `--surface-3`, close hover `--status-error`).
- **Workbench bar** below it: 44 px, `--surface-0`, tabs at left (icon + label, 8 items),
  right cluster: `⊕ Generate` (primary), `⛁ Connections` (icon), `⚙` (icon).
- **Status bar:** 26 px, `--surface-1`, 1 px top border: `v0.2.1 · pr1me 1.0.0` (mono-xs)
  left · center: active run chip · right: queue ETA (mono), provider dots, `Cmd+K` kbd hint.
- The title bar and status bar are the only elements allowed `--surface-0` full-width
  rules — they frame the work.

## 6. Sidebar / Activity Bar Design (deliverable 6)

- **Activity Bar:** 64 px, `--surface-0`, 1 px right `--border-subtle`. Five panel toggles
  (Explorer, Assets, Inspector, Timeline, Terminal), 40×40 icon buttons, 12 px vertical
  rhythm. Active: `--accent-soft` bg + 2 px left accent bar. Hover: `--surface-3`.
- **Project Explorer (left dock):** 280 px default. Header 40 px `--surface-2`
  (`EXPLORER` in `--label`) with search + menu. Tree rows 26 px, indent 14 px/level,
  chevron 16 px; selected = `--accent-soft` + accent text; file icons 14 px `--text-tertiary`;
  status glyphs right-aligned (`✓` ok, `⨯` error, `◉` running, `▓7/15` progress).
- Tooltips on every icon-only control; the bar collapses to a 64 px edge tab strip when
  the dock is unpinned (§39).

## 7. Panel System (deliverable 7)

- **Panel anatomy:** header 40 px (`--surface-2`, `--label` title left, actions right:
  pin ⧉, detach ⇱, menu ⋯) · body `--surface-1` · 1 px `--border-subtle` between header
  and body · 1 px outer `--border-default`.
- Panels live in dock zones; drag via header; drop zones per §39.
- **Panel density:** body padding `--space-4` (16 px); internal lists use 12 px row gaps.
- All panels are resizable (4 px handle, accent on hover) and pinnable.
- **Inspector (right dock, 320 px):** the only panel with a 12 px comfortable rhythm;
  sections separated by `--label` captions with 1 px `--border-subtle` rules; property
  rows: label (12.5 px secondary) left, control right, 34 px rows.

## 8. Card System (deliverable 8)

| Card | Size | Anatomy |
|---|---|---|
| `ProductionCard` | 280×176 | 9:16 thumbnail strip (3 thumbs, 56 px) · name (title-md) · episode count (mono-xs) · progress rail (4 px) · "last" caption |
| `EpisodeCard` | 240×120 (queue) / 120×170 (library) | 9:16 thumb · topic (2 lines) · duration + QA (mono-xs) · status glyph overlay |
| `SceneCard` | 200×~150 | thumbnail 64×112 · candidate strip 4×44 · camera/lighting chips (11 px) · duration mono |
| `KnowledgeCard` | 220×150 | category chip (colored soft) · difficulty badge · topic 2 lines · keyword tags (2 max) · scene count mono |
| `ConnectionCard` | full-width 120 | status dot + name (title-md) + latency (mono-xs) · inline field · Test/Edit/Reveal |

Card chrome: `--surface-1`, border `--border-default`, radius-md, hover: border
`--border-strong` + 1.5 px lift (shadow-1), selected: `--accent-soft` border 2 px.
Cards never contain more than one accent element at a time.

## 9. Button System (deliverable 9)

| Variant | Spec |
|---|---|
| **Primary** | `--accent` fill, `--text-inverse` 13 px 600, h 34, radius-md, px 16; hover `--accent-hover`; active `--accent-active`; disabled 0.45; icon slot 16 px left |
| **Secondary** | `--surface-3`, border `--border-default`, text-primary; hover `--surface-4` |
| **Ghost** | transparent, text-secondary; hover bg `--surface-3` |
| **Danger** | `--status-error` fill, inverse text; hover darken 6% |
| **Icon** | 34×34 ghost; `--text-secondary`; hover `--surface-3` + primary text; tooltip |
| **CTA (Generate)** | Primary, h 38, px 20, icon ⊕; only full-width accent element in the workbench bar |

States: idle → hover (+6% luminance, 100 ms) → active (+12%, pressed) → focus ring →
disabled (0.45 opacity, no shadow). Loading: spinner 16 px inline, width preserved
(zero shift). Buttons never show tooltips with text already on them.

## 10. Inputs (deliverable 10)

- **TextField/Select/ComboBox:** h 34, `--surface-3`, border `--border-default`,
  radius-md, text-base; focus: border `--border-accent` + ring; error: border
  `--status-error` + 11 px message below; mono mode for paths/JSON/seeds.
- **TextArea:** min-h 84 px, line-height 1.5; JSON fields mono 11 px.
- **SearchField:** ⌕ 16 px left, Esc clears, h 34, no label (placeholder + aria).
- **Checkbox:** 16 px, radius 4, accent check; **Toggle:** 34×20 track, 16 knob,
  accent when on, 200 ms knob slide.
- **SegmentedControl:** h 30, track `--surface-3` radius-full, thumb `--surface-4` +
  border-strong, indicator slides 200 ms.
- **Slider:** 2 px track, 14 px thumb, accent fill, mono value bubble on drag.
- **NumberField:** mono value, spinners on hover, validation ring.
- All inputs: label `--label` 11 px above (except search); helper 11 px below; focus
  never removed; placeholder `--text-tertiary`.

## 11. Tables (deliverable 11)

- **DataGrid:** header `--surface-2`, `--label` 11 px 600 uppercase tracking 0.06, sticky;
  rows 40 px, hover `--surface-3`; selected `--accent-soft` + 2 px left bar.
- Numeric cells right-aligned `--numeric`; first column sticky (left, `--surface-1` +
  shadow-1 seam); zebra off; virtualized above 200 rows.
- Status cells render as badge chips, never raw text; actions column = ghost icon
  buttons revealed on hover.
- Grid lines: only horizontal `--border-subtle` (no verticals); column resize 6 px
  handle, min 48 px.

## 12. Timeline Appearance (deliverable 12)

- **Ruler:** 20 px, `--surface-0`, mono 10 px timecode ticks at 1 s marks, major 5 s
  (`--border-subtle` ticks, `--text-tertiary` labels).
- **Tracks:** 4 tracks stacked, each 28 px: Video (thumbnail clips), Audio (waveform
  `--status-info` fill on `--surface-3`), Subtitles (chips), Overlays (markers).
- **Clips:** h 24, `--surface-3`, border `--border-default`, radius 4, thumbnail left
  24×24, duration mono right; selected: `--accent` 2 px border; hover: border-strong.
- **Playhead:** 1 px `--accent` line full height + 8 px handle with timecode bubble;
  scrub = `--ease-snap`, no easing.
- **Markers:** 10×14 accent tick above ruler with `M` label; in/out range = accent-soft
  wash + 1 px accent top rule.
- Tracks rows have 160 px label column (`--label` captions: VIDEO / AUDIO / SUBTITLES /
  OVERLAYS) on `--surface-1`.

## 13. Workflow Graph Appearance (deliverable 13)

- **Canvas:** `--surface-0`, blueprint dot grid (24 px, `--border-subtle` dots, 20 %
  opacity), infinite pan, zoom 50–200 %.
- **WorkflowNode:** width 220; header 32 px (`--surface-3`, icon 16 px + name 12.5 px
  600); body `--surface-1` with value rows 24 px (key `--text-tertiary` mono-xs, value
  `--text-primary` mono-xs); ports: 8 px squares (square = engineering precision) on
  `--border-default`, filled `--accent` when connected.
- **Edges:** 1.5 px bezier `--border-strong`; hovered edge = accent; selected node =
  `--accent-soft` bg + 2 px accent border.
- **MiniMap:** 160×100, `--surface-2`, viewport rect `--accent` 1 px outline, nodes
  reduced to 2 px squares `--surface-4`.
- Selected node's rationale renders in the Inspector as a `--status-info` soft panel.

## 14. Storyboard Appearance (deliverable 14)

- **SceneBoard canvas:** `--surface-0` + blueprint grid; filmstrip row of SceneCards
  with 16 px transition arrows (`--border-strong`, hover accent).
- **SceneCard:** 200 px wide; thumbnail area 64×112 center with `--surface-3` letterbox;
  candidate strip below (4 thumbs 44×78, scrollable if > 4); chips row (camera 11 px
  mono, lighting, duration).
- **Approval:** approved thumb = `--status-ok` 2 px border + ✓ 16 px badge top-right on
  `--surface-0` backing; hover on unapproved = border-strong; regenerate button = ghost
  ⟳ 28 px revealed on hover.
- **Locked order:** lock glyph 14 px `--text-tertiary` top-left + tooltip "Scene order is
  script-locked. Reorder in Script."
- **Stage rail:** top strip 36 px, 15 nodes (icon + index), 1 px `--border-subtle`
  connectors; states per §18.

## 15. Asset Cards (deliverable 15)

- Grid thumbnails: 9:16 images 96×170 or square 96×96 depending on media; video cards
  show first-frame + duration mono bottom-right; audio cards show 24 px waveform
  (`--status-info` on surface-3) + format chip.
- Card chrome: `--surface-1`, radius-md, border-default; hover: border-strong + play/
  preview affordance; selected: accent-soft border.
- Meta strip: name (12.5 px, 1 line, ellipsis), size mono-xs tertiary.
- Drop targets: accent dashed 2 px outline + `--accent-soft` wash on valid drop zone.
- Filmstrip mode: 56 px-tall rows (thumb 40 px + meta), tree mode: 26 px rows.

## 16. Queue Visualization (deliverable 16)

- **Board columns** (Queued/Rendering/Done): 300 px, header 40 px (`--label` + count
  badge), column body `--surface-0` (recessed), 12 px gaps, drop highlight = accent
  dashed inset.
- **EpisodeCard in queue:** 280 px; stage ring (34 px) overlays thumbnail bottom-right;
  progress rail 4 px under thumb (`--accent` on `--surface-3` track); ETA chip
  (mono-xs, `--text-tertiary`, running = `--status-info`); actions ghost 28 px
  (pause/cancel/retry/menu).
- Running card expands: live 15-node stage rail (36 px) + streaming thumbs row
  (56 px thumbs fade in staggered 12 ms) + log chip.
- **Honesty rule:** queued cards show position — "waiting · 2 ahead" (mono-xs); nothing
  pretends to run in parallel.

## 17. Progress Indicators (deliverable 17)

| Indicator | Spec |
|---|---|
| **StageRing** | 34 px circle, 3 px stroke `--surface-3` track, `--accent` sweep 300 ms/segment, 15 segments, center mono 9 px count |
| **ProgressRail** | 4 px, track `--surface-3`, fill `--accent` (running) / `--status-ok` (done) / `--status-error` (failed), width 200 ms ease-in-out |
| **ProgressBar** | 4 px linear; indeterminate = shimmer 1.2 s `--accent` sweep |
| **Spinner** | 16/24 px, 1.5 px stroke, `--accent`, 800 ms loop, eases |
| **Skeleton** | `--surface-2` blocks, 1.2 s gradient shimmer, zero layout shift |
| **StageRail node** | 28 px: status dot + index; active node = `--status-info` pulse (1.6 s) + 2 px ring |

Every indicator has a text twin (mono) for screen readers and the status bar.

## 18. Status Indicators (deliverable 18)

| State | Glyph | Color | Placement |
|---|---|---|---|
| ok / completed / approved | ✓ (or 8 px dot) | `--status-ok` | badges, tree, thumbnails |
| running / streaming | ◉ pulsing dot | `--status-info` | stage rail, queue, title bar |
| pending / paused / retry | ○ / ⟳ | `--status-warn` | queue, chips |
| failed / error | ⨯ | `--status-error` | badges, cards, banners |
| cancelled / idle / skipped | – | `--status-muted` | tree, stages |
| cache hit | ⇄ | `--text-tertiary` | stage rail, chain nodes |

Rules: status never by color alone — always glyph + color + (where density allows)
text; soft badges (`*-soft` bg + `--status-*` text) for inline chips; dots 8 px for
ambient (title/status bars) with pulsing only for running.

## 19. Notifications (deliverable 19)

- **Toast:** 320×64 max, `--surface-glass`, border `--border-default`, radius-lg,
  shadow-2; icon 16 px status + title (13 px 600) + message (12.5 px secondary, 2 lines)
  + action (text button) + close ×; slide-up 240 ms `--ease-out`; auto-dismiss 4 s
  (hover pauses); stack bottom-right above dock, max 4, newest bottom.
- **Toast kinds:** success (✓ green), error (⨯ red, persists until dismissed), info
  (blue, e.g. "render complete"), progress (spinner, live-updating).
- Never use toasts for decisions (dialogs own those) or for state that is already
  visible in the UI (the board already shows it — no toast).
- Errors also mirror into the Terminal dock as structured lines.

## 20. Dialogs (deliverable 20)

- **Modal:** 480 default (640 for editors), radius-lg, `--surface-1`, shadow-3; scrim
  `--overlay`; open 300 ms scale 0.98→1 `--ease-out`; header 48 px (title title-md +
  close); body padding 20; footer 48 px (secondary left, primary/danger right).
- **Sheet (right, e.g. Generate queue):** 380 px, radius-lg left corners only
  (0 on right edge), slides 300 ms `--ease-out`; same chrome as modal; scrim optional
  (side panels allow click-through).
- **Confirm dialog:** icon 20 px status + title + reason line (12.5 px secondary) +
  destructive action primary-danger; Esc cancels; `Enter` confirms.
- One dialog at a time; palette is closed when a dialog opens.

## 21. Loading States (deliverable 21)

| Surface | Pattern |
|---|---|
| First paint (lists/grids) | skeleton blocks matching final geometry, shimmer |
| Page/workbench composition | panels fade in 200 ms, staggered 30 ms |
| Action in progress | inline spinner in the control, width preserved |
| Streaming run | thumbs fade in 200 ms staggered 12 ms; stage rail advances; no full-screen spinner |
| Boot | startup screen (mockup M1) with mono progress line |
| Long health check | card-level 100 ms skeleton → spinner → status |

Rule: nothing blocks the artist. Long operations show progress *in place*; the app stays
interactive.

## 22. Empty States (deliverable 22)

- Anatomy: 24 px icon (workbench glyph, `--text-tertiary`) · title (title-md) ·
  subtitle (12.5 px secondary, 2 lines) · primary action (secondary button) · optional
  secondary link. Centered, `--space-6` padding.
- Copy lock: "No productions yet — create one to start." "Nothing rendering. Queue
  episodes from Script." "No failed episodes." "This production has no episodes."
- Empty states always carry a next action; never a bare "No data."

## 23. Error States (deliverable 23)

- **Error banner** (panel-level): 40 px, `--status-error-soft` bg, 1 px left accent
  border 3 px `--status-error`, ⨯ icon, message mono-xs, action buttons (Fix / Retry /
  Dismiss). Slides in 200 ms.
- **Run failure card:** card border `--status-error`, badge `⨯ failed`, reason mono-xs,
  actions: Retry (`--resume`) · Fix (opens Connection Center) · Log (Terminal dock).
- **Field errors:** border + 11 px message, never blocking; save blocked with summary
  banner (override allowed, logged).
- **Process crash:** dialog with exit code + log excerpt + "Restart app" / "Report".
- Error text is never decorative red prose — code + one-line reason + action.

---

# PART C — TYPE, COLOR, ICON

## 24. Typography Hierarchy (deliverable 24)

| Token | Size/Line/Weight | Usage |
|---|---|---|
| `--display-2xl` | 28/36, 650 | brand moments only (Welcome, startup) |
| `--display-xl` | 24/32, 650 | workbench titles |
| `--title-lg` | 19/27, 600 | panel titles, dialog titles |
| `--title-md` | 16/24, 600 | card titles, episode names |
| `--body-lg` | 14/21, 500 | default body (tables, lists) |
| `--body-md` | 13/19, 500 | dense body (tree, chips, status) |
| `--body-sm` | 12.5/18, 500 | metadata, captions |
| `--label` | 11/16, 600, +0.06em upper | section captions, headers, kbd captions |
| `--mono-xs` | 11/16, 400 | ids, hashes, JSON keys |
| `--mono-sm` | 12.5/18, 500 | paths, seeds, values |
| `--numeric` | inherited size, mono, tabular-nums | ALL time/scores/counts |

Rules (locked):

1. Every number is mono + tabular: timecode, ETA, ticks, QA, seeds, counts, versions.
2. Weights only 400/500/600/650. No 700+. No italics except inline annotations.
3. Uppercase only via `--label` (11 px tracked). Never uppercase body text.
4. Workbench titles are the largest type in the app; nothing exceeds 28 px except the
   brand mark.
5. Truncate with ellipsis everywhere; full value in tooltip.
6. JSON: mono-xs, keys `--text-primary`, strings `--chart-2`, numbers `--chart-4`,
   booleans `--chart-6`, 1.5 line-height.

## 25. Color Palette (deliverable 25)

### Surfaces (value ladder — the entire chrome)

| Token | Value |
|---|---|
| `--surface-0` | `#0B0E14` |
| `--surface-1` | `#10141C` |
| `--surface-2` | `#151A24` |
| `--surface-3` | `#1B212E` |
| `--surface-4` | `#232B3B` |
| `--overlay` | `rgba(4,6,10,0.72)` |
| `--surface-glass` | `rgba(16,20,28,0.78)` |

### Borders

| Token | Value |
|---|---|
| `--border-subtle` | `#1A212D` |
| `--border-default` | `#242D3D` |
| `--border-strong` | `#303B50` |
| `--border-accent` | `#4C8DFF` |

### Text

| Token | Value |
|---|---|
| `--text-primary` | `#E8ECF4` |
| `--text-secondary` | `#9AA4B8` |
| `--text-tertiary` | `#5E6A80` |
| `--text-inverse` | `#0B0E14` |
| `--text-link` | `#6FA3FF` |

### Status

| Token | Value | Soft |
|---|---|---|
| `--status-ok` | `#3FB96A` | `rgba(63,185,106,0.14)` |
| `--status-warn` | `#E5A83B` | `rgba(229,168,59,0.14)` |
| `--status-error` | `#E5484D` | `rgba(229,72,77,0.14)` |
| `--status-info` | `#38BDF8` | `rgba(56,189,248,0.14)` |
| `--status-muted` | `#5E6A80` | `rgba(94,106,128,0.14)` |

### Charts

`--chart-1` `#3D7EFF` · `--chart-2` `#38BDF8` · `--chart-3` `#3FB96A` · `--chart-4`
`#E5A83B` · `--chart-5` `#E5484D` · `--chart-6` `#A78BFA`

## 26. Accent Colors (deliverable 26)

| Token | Value | Role |
|---|---|---|
| `--accent` | `#3D7EFF` | **PRIME Blue** — the single brand + interaction accent |
| `--accent-hover` | `#5B93FF` | hover |
| `--accent-active` | `#2E66D6` | pressed |
| `--accent-soft` | `rgba(61,126,255,0.14)` | selection, active chips |
| `--accent-soft-strong` | `rgba(61,126,255,0.24)` | approved thumbs, selected hover |
| `--accent-gradient` | `linear-gradient(135deg,#6FA3FF,#3D7EFF 55%,#2E66D6)` | brand moments ONLY: logo mark, Welcome title, startup mark |
| `--accent-glow` | `0 0 24px rgba(61,126,255,0.10)` | running indicators, logo hover |

Discipline (locked):

1. PRIME Blue is the ONLY interaction accent. Status hues never act as accents.
2. Gradient appears in exactly two places: brand mark moments + Welcome; never on
   buttons, panels, or charts.
3. Accent usage per surface: on `--surface-0` use `--accent` text/icons at 100 %;
   on `--surface-1/2` use `--accent` or `--text-link` for links.
4. Selection is accent-soft + accent border/text — never a different hue.

## 27. Icon Style (deliverable 27)

- **Family:** single stroke set, 1.5 px stroke, 1.5 px rounded caps/joins, drawn on a
  24 grid, exported at 16/20/24. No fills (exception: state checks ✓ and dots).
- **Sizes:** 16 inline (buttons, tree, chips) · 20 panel headers/tabs · 24 workbench
  bar + empty states · 32–48 brand.
- **Status integration:** badges/dots around icons, never tinting them (icons are
  `currentColor`).
- **Workbench glyphs (locked):** Library ◫ grid · Script ✎ · Storyboard 🎞 film · Workflow
  ⌘-less: ⚙ graph · Render ▸ · Edit ✂ · Deliver ⇡ · Insights ▤▥ trend.
- **Pictogram sets (product-owned, static SVG):** CameraPicker (push-in, orbit, dolly,
  tilt, crane, static) · LightingPicker (rim, soft, key, back, practical, none) ·
  CompositionPicker (thirds, center, leading, frame, symmetry, negative). 44 px tiles,
  mono captions under; selected tile = accent border + soft bg.
- No emoji anywhere in the UI; no multicolor icons; mirror icons never used.

---

# PART D — DEPTH, SPACE, MOTION

## 28. Shadows (deliverable 28)

| Token | Value | Used by |
|---|---|---|
| `--shadow-1` | `0 1px 2px rgba(0,0,0,0.40)` | cards on surface-1, hover lift |
| `--shadow-2` | `0 4px 12px rgba(0,0,0,0.45)` | popovers, context menus, palette, toasts |
| `--shadow-3` | `0 12px 40px rgba(0,0,0,0.55)` | modals, sheets, floating windows |
| `--shadow-4` | `0 24px 64px rgba(0,0,0,0.60)` | Welcome, brand moments |
| `--accent-glow` | `0 0 24px rgba(61,126,255,0.10)` | running dot, stage ring active, logo |
| `--ring` | `0 0 0 2px #4C8DFF` | focus (2 px, always) |

Rules: shadows are for *float* (overlays, popovers, modals) — never on in-flow chrome;
hover lift = 1.5 px translateY + shadow-1 (only cards, 200 ms); no inner shadows.

## 29. Border Radius (deliverable 29)

Scale (locked, §4): `--radius-sm` 4 · `--radius-md` 6 · `--radius-lg` 12 ·
`--radius-full` 999. Mapping: controls/cards 6 · chips/badges/kbd 4 · overlays 12 ·
pills/dots full. Radius is never context-varied (no "this dialog is 10 px because it's
an editor"). Sheets: 12 on attached edge only, 0 on screen edge.

## 30. Spacing Scale (deliverable 30)

4 px base grid — tokens: `--space-1` 4 · `--space-2` 8 · `--space-3` 12 · `--space-4`
16 · `--space-5` 24 · `--space-6` 32 · `--space-7` 48 (canvas margins only).

Chrome sizes (locked): title bar 40 · workbench bar 44 · activity bar 64 · panel header
40 · status bar 26 · editor tab 36 · dock defaults: left 280 (min 200/max 480), right
320, bottom 200 · editor split min 320 · table row 40 · tree row 26 · control 34 ·
card padding 12 · canvas padding 32.

Rhythm rules: 8 px between siblings; 12 px inside cards; 16 px between sections; 24 px
between panel groups; lists virtualize at fixed heights (zero-shift streaming).

## 31. Animation Language (deliverable 31)

1. **Motion communicates three things only:** state change, spatial change, and the
   passage of work. Nothing else animates.
2. One easing family (§32); no springs, no bounces, no wobble.
3. **Zero layout shift:** only transform/opacity/color animate; sizes never animate.
4. Everything that changes state changes *in place* — badges morph, rails advance,
   cards repaint; nothing slides in to replace content.
5. Spatial moves (panels, sheets, palette) are the only large transforms; 300 ms max.
6. Streaming content staggers (12 ms) instead of rushing; the eye reads the pipeline.
7. Reduced motion: transforms → opacity only, durations 0 ms (progress keeps).
8. Dead motion is forbidden: no hover on touch, no idle loops except the running dot
   and indeterminate shimmer.

## 32. Motion Timing (deliverable 32)

| Token | Value | Used by |
|---|---|---|
| `--ease-out` | `cubic-bezier(0.16,1,0.3,1)` | spatial: panels, sheets, palette, modals |
| `--ease-in-out` | `cubic-bezier(0.65,0,0.35,1)` | state morphs, progress, toggles |
| `--ease-snap` | `cubic-bezier(0.2,0,0,1)` | playhead, scrub |
| `--dur-fast` | 100 ms | hover, active, focus |
| `--dur-base` | 200 ms | state changes, badges, chips |
| `--dur-slow` | 300 ms | panels, workbench composition, palette |
| `--dur-toast` | 240 ms | toasts |
| `--dur-shimmer` | 1.2 s loop | indeterminate, skeletons |
| `--dur-pulse` | 1.6 s loop | running dots, active stages |

Choreography (locked):

- Workbench switch: panels cross-fade + 8 px slide (300 ms, stagger 30 ms); editor
  documents persist silently; workbench underline slides between tabs.
- Dock/undock: 300 ms ease-out; drag ghost at 0.5 opacity, no rotation.
- Palette: 120 ms scale 0.98→1 + fade; result re-rank cross-fades.
- Thumbnails: 200 ms fade, 12 ms stagger.
- Stage ring: 300 ms per segment sweep; progress rails 200 ms width.
- Toasts: 240 ms rise; auto-dismiss 4 s.

## 33. Glass / Solid Usage (deliverable 33)

**Solid is the default.** Surfaces are flat value-ladder fills; glass is reserved for
the five *float* surfaces:

| Surface | Spec |
|---|---|
| Command palette | `--surface-glass` + `backdrop-filter: blur(12px) saturate(1.4)` |
| Context menus / tooltips | `--surface-glass`, blur 12 |
| Toasts | `--surface-glass`, blur 12 |
| Floating windows (detached panels) | `--surface-glass` title strip only; body solid `--surface-1` |
| Welcome / startup brand moment | `--surface-0` + `--accent-glow` (no blur) |

Rules: glass never sits on glass; never apply blur to panels in dock zones (they rest
on solid chrome); scrims are solid `--overlay`, never blurred content; if
`backdrop-filter` is unsupported, fall back to `--surface-2` opaque.

---

# PART E — TOKENS, ACCESSIBILITY, ADAPTIVITY

## 34. Theme Tokens (deliverable 34)

`src/lib/styles/tokens.css` MUST contain exactly this inventory (values per §25–§33):

```
--surface-0..4, --overlay, --surface-glass
--border-subtle, --border-default, --border-strong, --border-accent
--text-primary, --text-secondary, --text-tertiary, --text-inverse, --text-link
--status-ok/warn/error/info/muted + their --*-soft variants
--chart-1..6
--accent, --accent-hover, --accent-active, --accent-soft, --accent-soft-strong,
 --accent-gradient, --accent-glow
--radius-sm/md/lg/full
--shadow-1..4, --ring
--space-1..7
--ease-out, --ease-in-out, --ease-snap
--dur-fast, --dur-base, --dur-slow, --dur-toast, --dur-shimmer, --dur-pulse
--font-ui, --font-mono
--display-2xl, --display-xl, --title-lg, --title-md, --body-lg, --body-md, --body-sm,
 --label, --mono-xs, --mono-sm
--numeric  (font-variant-numeric: tabular-nums)
--focus-ring: 2px #4C8DFF
--scrollbar: 10px, thumb --surface-4, track transparent, radius-full, hover --border-strong
--selection: background --accent-soft, color --text-primary
--canvas-grid: dot 24px rgba(26,33,45,0.20)
```

## 35. Component Tokens (deliverable 35)

Semantic tokens per component family (all resolve to theme tokens — components never
hardcode hex):

```
--btn-primary:   bg accent / text inverse / radius-md / h 34 / px 16 / hover accent-hover / active accent-active / disabled 0.45
--btn-secondary: bg surface-3 / border default / text primary / hover surface-4
--btn-ghost:     bg transparent / text secondary / hover surface-3
--btn-danger:    bg status-error / text inverse / hover darken 6%
--input:         bg surface-3 / border default / h 34 / radius-md / focus border-accent+ring / error border status-error
--card:          bg surface-1 / border default / radius-md / padding 12 / hover border-strong+lift
--card-selected: border accent 2px / bg accent-soft
--panel:         header surface-2 h40 / body surface-1 / border subtle
--tree-row:      h 26 / hover surface-3 / selected accent-soft
--table:         header surface-2 label / row h40 / hover surface-3 / selected accent-soft+bar2px
--badge:         h20 radius-sm px8 11px600 / soft bg + status text
--chip:          h22 radius-sm / surface-3 border default / mono
--toast:         glass blur12 / border default / radius-lg / shadow-2 / 240ms
--modal:         surface-1 / radius-lg / shadow-3 / scrim overlay / 300ms scale
--kbd:           surface-3 / border default / radius-sm / mono-xs / px4
--tooltip:       glass blur12 / border default / radius-sm / mono/body-sm / 120ms
--json:          mono-xs / key primary / string chart-2 / number chart-4 / bool chart-6
--thumb-frame:   radius-md / image hard-clip / overlay badges 20px
--queue-card:    280w / thumb+ring / rail4px / eta mono-xs / expand=stage rail
```

## 36. Accessibility (deliverable 36)

| Area | Locked spec |
|---|---|
| Contrast | body ≥ 4.5:1 on its surface; `--text-secondary` ≥ 4.5:1 on `--surface-1`; `--text-tertiary` only for ≥ 4.5:1-safe large/mono UI or disabled; accent text on surface-0 ≥ 3:1 (large only — links also get underline on hover) |
| Focus | 2 px `#4C8DFF` ring + 1 px gap, on every focusable element, never removed; visible on dark surfaces by design |
| Target size | ≥ 24 px interactive minimum (chrome = 28–34 px); icon buttons 34×34 |
| Status | never color-alone: glyph + color + text where density allows; `✓/◉/⨯` shapes differ |
| Color vision | status hues also differ in luminance (green 0.55 / blue 0.52 / yellow 0.64 / red 0.55 + glyphs); charts pair hue with pattern/hatch on hover |
| Reduced motion | all transforms → opacity; durations 0 ms except progress; pulse off |
| Screen readers | icon buttons aria-labeled; stage rail = live region (polite); charts expose data tables; status = text not glyphs |
| Keyboard | full shortcut map (UX doc §7); lists arrow-nav; dialogs trap focus; Esc closes all overlays |
| Zoom | 200 % zoom: docks collapse to edge strips, editor stays usable, no horizontal loss (workbench bar scrolls) |
| Text scaling | all text tokens in px per lock; no line-height < 1.35 for 11–14 px |

## 37. Responsive Behavior (deliverable 37)

PR1ME is a desktop app — adaptivity is *window* adaptivity, never mobile layout:

| Width | Behavior |
|---|---|
| ≥ 1440 | full defaults; editor can split 3–4; right dock 320 |
| 1280–1439 | gallery columns 4→3; left dock 240 |
| 1100–1279 | left dock auto-collapses to edge tab strip (unpinned) or shrinks to 200; workbench bar labels hide (icons only) |
| 960–1099 | right dock 280; timeline ruler hides fractional labels; stage rail compresses to dots |
| < 960 | unsupported (min window) |

- Docks collapse to **edge tab strips** (28 px icon rail, tooltip) rather than hiding.
- Never: hamburger menus, stacked single-column layouts, or card reflow in docks.
- Editor splits never go below 320; panels never overlay content while pinned.

## 38. Multi-Monitor Behavior (deliverable 38)

- Panels detach to **floating windows** (Tauri multi-window): drag panel header outside
  the main window → floating window with `--surface-glass` title strip, solid body.
- Floating windows remember: monitor id, bounds, z-order; restored on launch.
- Context menu on any panel header: *Move to Next Monitor* (sends the floating window
  to the adjacent display, 300 ms slide).
- Main window remembers per-monitor bounds + maximized state.
- Layout presets are percent-based (monitor-agnostic): a layout saved on a 27" looks
  the same proportionally on a laptop display.
- Dock-and-float mix: users may float the Inspector on the second display while the
  main window keeps the board; re-docking re-attaches with a 300 ms settle.

## 39. Docking Behavior (deliverable 39)

- **Drag zones:** dragging a panel header shows drop indicators on: left dock, right
  dock, bottom dock, editor tab row (becomes a tab group), center (new split).
  Indicators: 2 px accent outline, radius 12, `--accent-soft` wash, 100 ms show.
- **Drop resolution:** center-left/right/top/bottom quadrants create splits (max depth
  3); full-center = new editor tab group.
- **Pin/unpin:** pinned = always visible; unpinned = auto-hide to edge tab strip
  (28 px, icon + tooltip, click re-opens as floating card; click outside re-hides).
- **Detach:** drag beyond window bounds (or ⇱ button) → floating window (§38).
- **Double-click header:** maximize panel in its zone (restore on second click).
- **Per-workbench presets:** 8 default layouts (UX doc §18); user edits persist per
  workbench per production; *Reset Layout* in the panel ⋯ menu restores the default.
- Split drag handles: 4 px, accent on hover, double-click = 50/50.

---

# PART F — OVERALL DESIGN MOCKUPS (deliverable 40)

> High-fidelity ASCII mockups. Colors annotated via markers:
> `●` ok/green · `◉` running/blue · `⨯` error/red · `◆` accent/blue · `★` approved ·
> `⇄` cache · `▓` fill · `░` empty · `▣` thumbnail · `⌕` search · `⋮/⋯` menus.
> Every mockup maps 1:1 to the component tokens in §35; none introduces new components
> or layout beyond the LOCKED UX architecture.

### M1 — Startup Screen

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                                                                              │
│                        ┌───────────────────────┐                              │
│                        │   ○      ○      ○      │                              │
│                        │       P R 1 M E        │     ← logo mark: aperture   │
│                        │   ○      ○      ○      │       ring + wordmark       │
│                        └───────────────────────┘                              │
│                                                                              │
│                              S T U D I O                                      │
│                            Make the Short.                                   │
│                                                                              │
│                        ██████████████░░░░░░░░  64%  loading services         │
│                                                                              │
│  v0.2.1 · pr1me 1.0.0                                  © PR1M3 Labs            │
└──────────────────────────────────────────────────────────────────────────────┘
```

Surface-0 field · logo `--accent-gradient` text · mono progress line (no spinner) ·
fade-in 300 ms.

### M2 — Home / Library

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ◆  PR1ME   ◆ Production: Core-FDM ▾            (queue 3)  ● ● ● ○   ─ □ ✕   │
├──────────────────────────────────────────────────────────────────────────────┤
│ ◆ Library   ✎ Script   🎞 Storyboard   ⚙ Workflow   ▸ Render   ✂ Edit   ⇡ Deliver   📈 Insights      ⊕ Generate   ⛁  ⚙ │
├───┬──────────────────────────────────────────────────────────────────────────┤
│ ▤ │  LIBRARY — Core-FDM                                                     │
│ ▤ │                                                                          │
│ ▤ │  RECENTS — TODAY                                              [View all] │
│ ▤ │   ╭────────────╮  ╭────────────╮  ╭────────────╮  ╭────────────╮          │
│ ▤ │   │  ▣▣▣▣▣▣▣▣▣  │  │  ▣▣▣▣▣▣▣▣▣  │  │  ▣▣▣▣▣▣▣▣▣  │  │  ▣▣▣▣▣▣▣▣▣  │          │
│ ▤ │   │  Gyroid      │  │  Infill      │  │  Layer Ht.   │  │  Bed Adh.   │          │
│ ▤ │   │  01:24 · 94  │  │  01:18 · 91  │  │  00:58 · 88  │  │  01:05 · 93  │          │
│ ▤ │   │  ✓ delivered │  │  ✓ delivered │  │  ✓ review    │  │  ✓ review    │          │
│ ▤ │   ╰────────────╯  ╰────────────╯  ╰────────────╯  ╰────────────╯          │
│ ▤ │                                                                          │
│ ▤ │  PRODUCTIONS                                                      [＋ New] │
│ ▤ │   ╭──────────────────────╮   ╭──────────────────────╮                     │
│ ▤ │   │ ◆ Core-FDM           │   │ ◆ Educational Series │                     │
│ ▤ │   │  24 episodes · 3 live│   │  12 episodes · idle  │                     │
│ ▤ │   │  ▓▓▓▓▓▓▓▓▓░░░  82%   │   │  ▓▓▓▓▓▓▓▓▓▓▓░  90%  │                     │
│ ▤ │   │  last: 2h ago        │   │  last: yesterday    │                     │
│ ▤ │   ╰──────────────────────╯   ╰──────────────────────╯                     │
│ ▤ │                                                                          │
├───┴──────────────────────────────────────────────────────────────────────────┤
│ v0.2.1 · pr1me 1.0.0      run r-3f2a · Layer Height       ETA 1h 04m · ●●● ○ · Cmd+K │
└──────────────────────────────────────────────────────────────────────────────┘
```

### M3 — Project Explorer

```
│ ▤ │  EXPLORER                                    ⌕  [⋮]                       │
│ ▤ │  ◆ Core-FDM                                            (24)               │
│ ▤ │  ├─ ◆ Episodes                                                           │
│ ▤ │  │   ├─ ▣ Gyroid                    ✓  01:24 · 94   ★                    │
│ ▤ │  │   ├─ ▣ Infill                    ✓  01:18 · 91   ★                    │
│ ▤ │  │   ├─ ◉ Layer Height              ▓  7/15  · 00:36                     │
│ ▤ │  │   ├─ ▣ Bed Adhesion              ✓  01:05 · 93   ★                    │
│ ▤ │  │   ├─ ▣ Retraction                ⨯  failed · 12                      │
│ ▤ │  │   └─ ▣ Ironing                   ○  queued                           │
│ ▤ │  ├─ ◆ Runs                                                                │
│ ▤ │  │   ├─ ▸ r-3f2a · Layer Height                                          │
│ ▤ │  │   │    ├─ ▸ images         (5)                                        │
│ ▤ │  │   │    ├─ ▸ workflow       (6)                                        │
│ ▤ │  │   │    ├─ ▸ history        (5)                                        │
│ ▤ │  │   │    ├─ ▸ checkpoints   (15)                                        │
│ ▤ │  │   │    ├─ ▸ video/short.mp4                                           │
│ ▤ │  │   │    └─ ▸ reports/execution_report.json                             │
│ ▤ │  │   └─ ▸ r-2f1c · Infill                                                 │
│ ▤ │  └─ ◆ Assets (workspace)                                                   │
```

26 px rows · status glyphs right · mono metadata · selection = accent-soft.

### M4 — Generate (Queue Episodes sheet, over Script workbench)

```
┌──────────────────────────────────────────────────────────────────┬───────────────┐
│ ◆ Library ✎ Script 🎞 Storyboard ⚙ Workflow ▸ Render ✂ Edit ⇡ Deliver 📈   │ GENERATE     │
├───┬──────────────────────────────────────────────────────────────┤───────────────┤
│ ▤ │  SCRIPT — Core-FDM                    [⌕  filter…]  [All ▾]  │ ╭───────────╮ │
│ ▤ │  SELECTED FOR PRODUCTION                                     │ │ ▣▣▣▣▣     │ │
│ ▤ │   ╭───────────╮ ╭───────────╮ ╭───────────╮ ╭───────────╮    │ │ 12 episodes│ │
│ ▤ │   │  ▣▣▣▣▣▣▣▣ │ │  ▣▣▣▣▣▣▣▣ │ │  ▣▣▣▣▣▣▣▣ │ │  ▣▣▣▣▣▣▣▣ │    │ │  selected  │ │
│ ▤ │   │  Gyroid    │ │  Infill    │ │  Bed Adh. │ │  Retraction│    │ ╰───────────╯ │
│ ▤ │   │  B · Slicer│ │  B · Slicer│ │  B · Slicer│ │  B · Slicer│    │               │
│ ▤ │   │  ✓✓✓✓      │ │  ✓✓✓       │ │  ✓✓✓✓      │ │  ✓✓       │    │  QUEUE ORDER  │
│ ▤ │   ╰───────────╯ ╰───────────╯ ╰───────────╯ ╰───────────╯    │  1  Gyroid  ↕   │
│ ▤ │                                                               │  2  Infill  ↕   │
│ ▤ │  (gallery continues… windowed)                                │  3  Bed Adh ↕   │
│ ▤ │                                                               │  (drag to       │
│ ▤ │                                                               │   reorder)      │
│ ▤ │                                                               │ ─────────────── │
│ ▤ │                                                               │  Seed      [42] │
│ ▤ │                                                               │  Attempts   [3] │
│ ▤ │                                                               │  Publish     [ ] │
│ ▤ │                                                               │ ─────────────── │
│ ▤ │                                                               │  ETA  1h 12m     │
│ ▤ │                                                               │  [Queue 12 ▸]    │
├───┴──────────────────────────────────────────────────────────────┴───────────────┤
│ v0.2.1 · pr1me 1.0.0                              ETA 1h 04m · ●●● ○ · Cmd+K      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Right sheet: 380 px, radius-lg on left edge only, slides 300 ms. Preview rows = KB
cards with difficulty/category chips. Queue order = drag list (mono index).

### M5 — Storyboard

```
│ STORYBOARD — Gyroid                    seed 42    ▓▓▓▓▓▓░░░░░░░░░░  7/15      │
│ ╭───────╮ ╭───────╮ ╭───────╮ ╭───────╮ ╭───────╮ ╭──────────╮    INSPECTOR  │
│ │  S1   │→│  S2   │→│  S3   │→│  S4   │→│  S5   │→│  THUMB    │    ───────── │
│ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣▣▣▣  │    SCENE S2  │
│ │ ★★★▣▣ │ │ ▣▣★▣▣ │ │ ▣▣▣★▣ │ │ ★▣▣▣▣ │ │ ▣▣▣★▣ │ │ ★★★★▣▣▣ │    ───────── │
│ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣ │ │ ▣▣▣▣▣▣▣▣  │  CAMERA     │
│ │ push │ │ orbit │ │ dolly │ │ tilt  │ │ crane │ │ thumb  │    (pictogram)  │
│ │ rim  │ │ rim   │ │ soft  │ │ back  │ │ key   │ │       │    [◧] push-in   │
│ │ 6.2s │ │ 7.1s  │ │ 5.4s  │ │ 8.0s  │ │ 6.4s  │ │ 3.0s   │    [ ] orbit    │
│ ╰───────╯ ╰───────╯ ╰───────╯ ╰───────╯ ╰───────╯ ╰──────────╯    [ ] dolly    │
│  ✓ approved S2-S3   🔒 scene order script-locked                    ─────────  │
│  (canvas: blueprint grid, zoom 50–200%, pan, fit)                 LIGHTING    │
│                                                                   [◧] rim     │
│                                                                   [ ] soft     │
│                                                                   ─────────    │
│                                                                   COMPOSITION │
│                                                                   [◧] thirds   │
└───────────────────────────────────────────────────────────────────────────────┘
```

### M6 — Workflow Viewer

```
│ WORKFLOW — Gyroid · S2                             [1 Chain][2 Graph]  ⌕  ⇣     │
│ ┌─ PROMPT CHAIN ─────────────────┐ ┌─ COMFYUI GRAPH ──────────────────────┐   │
│ │ knowledge_load        ✓  0.4s  │ │  positive_prompt ──────────┐          │   │
│ │ educational_director  ✓  1.2s  │ │  negative_prompt ──────────┤          │   │
│ │ ai_director           ✓  2.1s  │ │                            ▼          │   │
│ │ visual_intelligence   ✓  1.8s  │ │  ┌ PROFILE (sdxl) ──────────────┐     │   │
│ │ model_director        ✓  0.6s  │ │  │ cfg 7 · steps 28            │     │   │
│ │ prompt_compiler       ✓  0.9s  │ │  │ resolution 1080 × 1920      │     │   │
│ │ workflow_builder      ✓  0.8s  │ │  └─────────────┬───────────────┘     │   │
│ │ render_loop          ◉ 4m12s   │ │                ▼                     │   │
│ │ voice                ░  queued │ │  ┌ SAMPLER (euler_a) ──┐  ┌ VAE ──┐   │   │
│ │ subtitles            ░         │ │  │ scheduler karras    │  │ decode│   │   │
│ │ video_assembly       ░         │ │  └──────────┬──────────┘  └───┬────┘   │   │
│ │ video_render         ░         │ │             ▼                 ▼        │   │
│ │ thumbnail            ░         │ │  ┌ UPSCALER ┐         ┌ OUTPUT ─────┐  │   │
│ │ metadata             ░         │ │  │ 2x realesr│         │ 1080 × 1920 │  │   │
│ │ publisher            ░         │ │  └──────────┘         │ PNG         │  │   │
│ │                                  │  └───────────────────────────────┘  │   │
│ │ (click stage → contract JSON     │  (canvas: blueprint grid, mini-map   │   │
│ │  in Inspector; ⇄ = cache hit)    │   bottom-right, zoom 50–200%)        │   │
│ └────────────────────────────────┘ └──────────────────────────────────────┘   │
│ v0.2.1 · pr1me 1.0.0      S2 · workflow_builder · ✓ validated · QA 92.4       │
└───────────────────────────────────────────────────────────────────────────────┘
```

### M7 — Timeline (Edit)

```
│ EDIT — Gyroid                          [⏵] 00:00:12:08                [⇓]      │
│ ┌─ PREVIEW ─────────────────────────────────────────────────────────────┐     │
│ │               ▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣  (player · 16:9)  ▶ │     │
│ └───────────────────────────────────────────────────────────────────────┘     │
│ ruler    0        5        10       15       20       25       30       35   │
│ VIDEO   │▣ S1 6.2s│▣ S2 7.1s │▣ S3 5.4s│▣ S4 8.0s│▣ S5 6.4s│▣ THMB 3.0s│   │
│ AUDIO   │ narration ──────────────────────────── ▔▔▔▔▔ music ▔▔▔▔▔▔▔▔▔▔ │   │
│ SUBTITL │ [narration.srt ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔] │   │
│ OVERLAY │  M1 text                    M2 text                              │   │
│          │  │playhead│                                                   │   │
│ (clips = deterministic durations; click clip → Storyboard scene)          │   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### M8 — Asset Browser

```
│ ▤ │  ASSETS                        [Run media ▾] [Assets] [Config]  [⋮]      │
│ ▤ │  ⌕  filter…   ▦ grid ▤ strip ≡ tree                                   │
│ ▤ │  ╭────────╮ ╭────────╮ ╭────────╮ ╭────────╮ ╭────────╮ ╭────────╮     │
│ ▤ │  │ ▣▣▣▣▣▣ │ │ ▣▣▣▣▣▣ │ │ ▣▣▣▣▣▣ │ │ ▣▣▣▣▣▣ │ │ ▣▣▣▣▣▣ │ │ ▣▣▣▣▣▣ │     │
│ ▤ │  │ S1.png │ │ S2.png │ │ S3.png │ │ S4.png │ │ S5.png │ │ thumb │     │
│ ▤ │  │ 2.1 MB │ │ 2.3 MB │ │ 2.0 MB │ │ 2.4 MB │ │ 2.2 MB │ │ 1.8 MB │     │
│ ▤ │  ╰────────╯ ╰────────╯ ╰────────╯ ╰────────╯ ╰────────╯ ╰────────╯     │
│ ▤ │  ╭────────╮ ╭────────╮                                                  │
│ ▤ │  │ ▔▔▔▔▔▔ │ │ ▔▔▔▔▔▔ │   (video: first-frame + duration chip)           │
│ ▤ │  │ short  │ │ narr.  │                                                  │
│ ▤ │  │ .mp4 · │ │ .wav · │                                                  │
│ ▤ │  │ 00:35  │ │ 00:35  │                                                  │
│ ▤ │  ╰────────╯ ╰────────╯                                                  │
│ ▤ │  (drop targets: scene candidate, thumbnail picker, assets folder)        │
```

### M9 — Learning Dashboard (Insights → Learning)

```
│ INSIGHTS                                    [1 Analytics] [2 Learning]        │
│ LEARNING — Core-FDM                                          [30d ▾]          │
│  ╭──────────────────────────────────────────────────────────────╮            │
│  │ ⚠  Repeated QA failure · Slicer & Print Settings             │            │
│  │    6 episodes · mean QA 71 < threshold 90        [Review] [Retry ▸]      │
│  ╰──────────────────────────────────────────────────────────────╯            │
│  ╭──────────────────────────────────────────────────────────────╮            │
│  │ ⚠  Narration over budget · 3 episodes > 35 s                 │            │
│  │    drift +31 % vs scene plan                    [Open in Script]          │
│  ╰──────────────────────────────────────────────────────────────╯            │
│  ╭──────────────────────────────────────────────────────────────╮            │
│  │ ✓  Publishing momentum · Bed Adhesion                         │            │
│  │    highest retained views this production          [Review]              │
│  ╰──────────────────────────────────────────────────────────────╯            │
│  (proposals are read-only suggestions; every action is explicit + undoable)  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### M10 — Preferences (modal)

```
┌─────────────────────────── PREFERENCES ────────────────────────────────────┐
│ ┌──────────┬─────────────────────────────────────────────────────────────┐ │
│ │ GENERAL  │  ⌕  search preferences…                                     │ │
│ │          │                                                             │ │
│ │ GENERAL  │  Log level                    [INFO ▾]                      │ │
│ │ PUBLISH  │  JSON logs                    [●]                           │ │
│ │ UPDATE   │  Image critic                 [●]   threshold   [90]        │ │
│ │ ABOUT    │  Target duration              [35–45 ▾] s                   │ │
│ │          │  Padding (intro/outro)        [0]s [0]s                     │ │
│ │          │                                                             │ │
│ │          │  WORKSPACE (read-only)                                     │ │
│ │          │  prompts   D:\PR1ME-Shorts-Automation\prompts               │ │
│ │          │  output    D:\PR1ME-Shorts-Automation\output                │ │
│ │          │  assets    D:\PR1ME-Shorts-Automation\assets                │ │
│ │          │                                                             │ │
│ │          │  PUBLISH · YouTube                                          │ │
│ │          │  visibility  [public ▾]   category [Education ▾]            │ │
│ │          │  made for kids [ ]                                          │ │
│ │          │                                                             │ │
│ │          │                               [Restore defaults]  [Done ✓]  │ │
│ └──────────┴─────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

Searchable sections; left nav `--surface-1`; nothing provider-related here (see
Connection Center). Modal 640×480, radius-lg, shadow-3.

### M11 — Render Queue (Render workbench)

```
│ RENDER — Core-FDM                                  [▶ Render all] [⏸ Pause]   │
│ ┌─ QUEUED (4) ─────────────┐ ┌─ RENDERING (1) ────────────┐ ┌─ DONE (12) ─────┐ │
│ │ ╭────────────────────╮   │ │ ╭──────────────────────╮   │ │ ╭──────────────╮ │ │
│ │ │ ▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣  │   │ │ ▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣  ◐ │   │ │ ▣▣▣▣▣▣▣▣▣▣▣▣  ✓ │ │
│ │ │ Gyroid              │   │ │ Layer Height          │   │ │ Infill        │ │
│ │ │ ▓▓▓▓▓▓▓▓░░░░░░░░░░  │   │ │ ◉ render_loop 7/15   │   │ │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │ │
│ │ │ ETA 18m · waiting   │   │ │ ▣▣▣▣ ▣▣ ▣▣▣▣ stream   │   │ │ 01:18 · 91    │ │
│ │ │           [⋮]       │   │ │ [⏸][■][⟳] [log]      │   │ │           [⋮] │ │
│ │ ╰────────────────────╯   │ ╰──────────────────────╯   │ ╰──────────────╯ │ │
│ │ ╭────────────────────╮   │                            │ ╭──────────────╮ │ │
│ │ │ ▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣  │   │                            │ │ ▣▣▣▣▣▣▣▣▣▣▣▣  ⨯ │ │
│ │ │ Injection molding  │   │                            │ │ Retraction    │ │
│ │ │ ▓▓▓▓▓▓▓░░░░░░░░░░░ │   │                            │ │ failed: timeout│ │
│ │ │ ETA 24m · waiting   │   │                            │ │ [Retry] [Fix] │ │
│ │ │           [⋮]       │   │                            │ ╰──────────────╯ │ │
│ │ ╰────────────────────╯   │                            └──────────────────┘ │
│ └──────────────────────────┘                                                │
│ (stage ring = 15-segment aperture ring · ETA from deterministic runtime ticks)│
└──────────────────────────────────────────────────────────────────────────────┘
```

### M12 — Analytics (Insights → Analytics)

```
│ INSIGHTS — Analytics                          [Core-FDM ▾] [30d ▾] [⇓ CSV]    │
│ ╭ 128 runs ╮ ╭ 87% success╮ ╭ 92.4 mean QA ╮ ╭ 14/day ╮ ╭ 1h 12m ETA ╮      │
│ │ ▲ 12%   │ │ ▲ 3%       │ │ ▲ 1.2        │ │ ▲ 2    │ │ − 8m       │      │
│ ╰─────────╯ ╰────────────╯ ╰──────────────╯ ╰────────╯ ╰────────────╯      │
│  SUCCESS RATE                        │  MEAN QA BY CATEGORY                  │
│  ████████████████████▌  87%          │  Slicer      ████████████▌  92        │
│  ██████████████▌        66%          │  Materials   ██████████▌   89        │
│  ██████████▌            47%          │  Hardware    ████████▌     85        │
│  ██████▌                30%          │  Design      ███████▌      82        │
│  (sparkline over time)               │  (bars: mono values right)           │
│  STATUS DONUT                        │  QA DISTRIBUTION                      │
│   ✓ 87%  ✗ 8%  ⟳ 5%                 │  ▂▃▅▇██▇▅▃▂  (histogram)             │
│  (hover segment → drill into runs)   │  (hover bar → run list)               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### M13 — Publish (Deliver)

```
│ DELIVER — Gyroid                                            [Dry-run] [⇡ Publish]│
│ ┌─ TARGETS ─────────────────┐ ┌─ THUMBNAIL ──────────────┐ ┌─ METADATA ─────────┐ │
│ │ ⭘ YouTube           ● ok  │ │   ▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣  │ │ TITLE               │ │
│ │   visibility [public ▾]   │ │   ▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣  │ │ Why Layer Height     │ │
│ │   category [Education ▾]  │ │   ▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣▣  │ │ Matters              │ │
│ │   tags [3]  kids [ ]      │ │   ★ candidate 2 of 4     │ │ ──────────────       │ │
│ │ ────────────────────────  │ │   [◂][1][2][3][4][▸]     │ │ DESCRIPTION          │ │
│ │ ○ Instagram   (planned)   │ └──────────────────────────┘ │ (from KB row)        │ │
│ │   — not yet available     │                              │ ──────────────       │ │
│ └───────────────────────────┘                              │ TAGS  #3dprinting     │ │
│  publish payload: dry-run manifest        [view JSON ⇲]    │ #layerheight #shorts  │ │
│                                                            │ ──────────────       │ │
│                                                            │ VISIBILITY public ·   │ │
│                                                            │ made-for-kids false   │ │
│                                                            │ (dry-run ✓ will not   │ │
│                                                            │  upload)              │ │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 41. Implementation Rules (final)

1. `tokens.css` (§34) and component tokens (§35) are the only style inputs. Any hex
   outside the token tables is a review-blocking defect.
2. Mockups M1–M13 are the visual contract. Implementations are compared to them
   (proportion, hierarchy, density), not to taste.
3. No new components, no new layouts, no renames (UX doc + hierarchy are locked).
4. Dark theme is the only theme. Compact density is the only density.
5. Backend/runtime/CLI untouched; this document changes only `app/**`.
6. Every phase's visual QA: screenshot diff against the mockups + token audit
   (no hardcoded values, no non-token radii/shadows).
7. Reduced-motion and contrast rules (§36) are part of Definition of Done.