# PR1ME Studio — Visual Design System v2 (LOCKED)

**Status:** LOCKED. Supersedes `VISUAL_DESIGN_SYSTEM.md` v1. Implement `tokens.css` exactly;
no deviations. Backend FINAL — this governs only the product layer.

---

## 19. Design Language (deliverable 19)

**Concept: "Cinematic Precision."** PR1ME is a filmmaking instrument for engineering stories.
The UI reads like a precision tool: quiet, dense, and typographically controlled — chrome in
monochrome, color reserved for *meaning* (status, selection, data). The aesthetic ancestry is
Blackmagic Resolve's editorial darkness, Figma's precision, and Cursor's modern restraint —
without their decoration.

Pillars:

1. **Neutral chrome, color as information.** The interface is grayscale-blue. Only status,
   selection, and chart data carry hue. If a color isn't meaningful, it isn't used.
2. **Layered depth by value, not blur.** Surfaces stack by luminance (0 → 4); separation via
   1 px borders + subtle shadows. No heavy gradients, no glass, no glow except the running
   indicator.
3. **Editorial typography.** UI text is small, 500-weight, tight line-height; headings are
   uppercase-optional labels with letter-spacing. Numbers are always tabular mono — the
   product is about time, scores, ticks.
4. **The filmstrip idiom.** Thumbnails, strips, rails, and boards are the visual vocabulary.
   Cards carry a 9:16 thumbnail as their crown; every state is shown with the artifact
   itself, not an icon.
5. **Calm motion.** Motion communicates state transitions and spatial change, never delight.
   120–300 ms, one easing family, nothing bounces.
6. **Compact density.** 34 px controls, 40 px rows, 4 px grid. The product is used for hours;
   density is respect for the artist's attention.

---

## 20. Motion Language (deliverable 20)

### 20.1 Tokens

| Token | Value |
|---|---|
| `--ease-out` | `cubic-bezier(0.16, 1, 0.3, 1)` — spatial (panels, palette, drawers) |
| `--ease-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` — state morphs, progress |
| `--ease-snap` | `cubic-bezier(0.2, 0, 0, 1)` — timeline scrubbing, playhead |
| `--dur-fast` | 100 ms — hover, active, focus |
| `--dur-base` | 200 ms — state changes, badges, tooltips |
| `--dur-slow` | 300 ms — panels, workbench composition, palette |
| `--dur-shimmer` | 1.2 s loop — indeterminate progress |

### 20.2 Choreography rules (locked)

1. **Workbench switch** = composition: dock panels cross-fade/slide 8 px, editor documents
   persist without animation. The workbench bar's active tab gets an accent underline that
   *slides* between tabs (300 ms).
2. **Panel dock/undock** = 300 ms ease-out, transform + opacity, with drag ghost at 0.5
   opacity and 0 rotation.
3. **Palette** = 120 ms scale 0.98→1 + fade (aperture), results re-rank with cross-fade.
4. **Status morphs** (stage rail, badges, queue cards): color + icon cross-fade in 200 ms,
   **zero layout shift** (fixed sizes).
5. **Progress**: bars animate width 200 ms ease-in-out; the stage ring sweeps 300 ms per
   segment; running indicator = 2 px pulsing dot (1.6 s, opacity 0.4→1).
6. **Thumbnail streaming** during render: images fade in 200 ms with a 12 ms stagger.
7. **Playhead**: `--ease-snap`, always follows the media clock, no easing on frame steps.
8. **Toast/context menus**: 200 ms rise/slide; never scale.
9. **Reduced motion** (`prefers-reduced-motion`): transforms become opacity-only, all
   durations 0 ms except required feedback (progress stays).
10. **Never animate layout-affecting properties** (width of cards, rows, grids).

---

## 21. Color System (deliverable 21)

### 21.1 Chrome (monochrome-blue, value ladder)

| Token | Value | Usage |
|---|---|---|
| `--surface-0` | `#0B0E14` | window background, workbench bar, title bar |
| `--surface-1` | `#10141C` | panels, cards |
| `--surface-2` | `#151A24` | panel headers, table headers, dock zones |
| `--surface-3` | `#1B212E` | inputs, hover |
| `--surface-4` | `#232B3B` | active, pressed, selected rows |
| `--overlay` | `rgba(4,6,10,0.72)` | scrim |
| `--border-subtle` | `#1A212D` | internal dividers |
| `--border-default` | `#242D3D` | controls, cards, panel edges |
| `--border-strong` | `#303B50` | hover chrome |
| `--border-accent` | `#4C8DFF` | focus, active tab, selection ring |

### 21.2 Text

| Token | Value | Usage |
|---|---|---|
| `--text-primary` | `#E8ECF4` | body, headings |
| `--text-secondary` | `#9AA4B8` | labels, metadata |
| `--text-tertiary` | `#5E6A80` | placeholders, disabled, panel captions |
| `--text-inverse` | `#0B0E14` | on accent |
| `--text-link` | `#6FA3FF` | links, paths |

### 21.3 Accent

| Token | Value | Usage |
|---|---|---|
| `--accent` | `#3D7EFF` | primary actions, active, selection |
| `--accent-hover` | `#5B93FF` | hover |
| `--accent-active` | `#2E66D6` | pressed |
| `--accent-soft` | `rgba(61,126,255,0.14)` | selected chips, active item bg |
| `--accent-soft-strong` | `rgba(61,126,255,0.24)` | selected hover, approved thumbnails |

### 21.4 Status (semantic — the only hues in the chrome)

| Token | Value | Usage |
|---|---|---|
| `--status-ok` | `#3FB96A` · soft `rgba(63,185,106,0.14)` | completed, passed, healthy, approved |
| `--status-warn` | `#E5A83B` · soft `rgba(229,168,59,0.14)` | pending, paused, retry, attention |
| `--status-error` | `#E5484D` · soft `rgba(229,72,77,0.14)` | failed, errors |
| `--status-info` | `#38BDF8` · soft `rgba(56,189,248,0.14)` | running, streaming |
| `--status-muted` | `#5E6A80` | cancelled, idle, skipped |

### 21.5 Charts

`--chart-1` `#3D7EFF` · `--chart-2` `#38BDF8` · `--chart-3` `#3FB96A` · `--chart-4`
`#E5A83B` · `--chart-5` `#E5484D` · `--chart-6` `#A78BFA`. Chart grids use
`--border-subtle`; axis text `--text-tertiary`.

### 21.6 Color rules (locked)

1. Chrome uses the value ladder only; hue appears solely via status/chart/accent tokens.
2. Status tokens are never used decoratively (no green buttons, no red badges for fun).
3. Approval = `--status-ok`; selection = `--accent`; running = `--status-info` pulse.
4. Surfaces never violate the ladder (a panel on `surface-2` is never lighter than its
   content). Selection rows: `--accent-soft` bg + 2 px left accent bar.
5. Focus ring: 2 px `--border-accent` with 1 px gap — always visible, never removed.

---

## 22. Typography (deliverable 22)

| Token | Value |
|---|---|
| `--font-ui` | `"Inter", "Segoe UI", system-ui, sans-serif` |
| `--font-mono` | `"JetBrains Mono", "Cascadia Code", Consolas, monospace` |
| `--text-xs` | 11 px / 16 px, 500 |
| `--text-sm` | 12.5 px / 18 px, 500 |
| `--text-base` | 14 px / 21 px, 500 |
| `--text-lg` | 16 px / 24 px, 600 |
| `--text-xl` | 19 px / 27 px, 600 |
| `--text-2xl` | 24 px / 32 px, 650 (workbench title, never larger) |
| `--text-mono-xs` | 11 px mono 400 |
| `--text-mono-sm` | 12.5 px mono 500 |
| `--label` | 11 px, 600, `letter-spacing: 0.06em`, uppercase — panel captions, table headers, section titles |
| `--numeric` | `font-mono`, `font-variant-numeric: tabular-nums` — all time/scores/counts |

Rules (locked):

1. **Every number is mono and tabular** — timecode, ETA, ticks, QA scores, counts, seeds,
   hashes, versions. `--numeric` is the default for any value that could be summed.
2. **IDs, fingerprints, JSON keys** render `--text-mono-xs` at 60–70% opacity.
3. **Headings are quiet**: workbench titles `--text-2xl` 650, page labels `--label`;
   no all-caps body text.
4. Weights limited to 400/500/600/650; no 700+ anywhere. Italics only for inline annotations.
5. Line-height 1.5 for body, 1.35 for dense lists; JSON views use mono 11 px / 1.5.
6. Truncation everywhere is ellipsis; tooltips carry full text (120 ms).

---

## 23. Iconography (deliverable 23)

- **Set:** stroke-based, 1.5 px stroke, rounded caps, geometric — consistent with Lucide but
  curated to a single family (all icons drawn on a 24 grid, exported 16/20/24).
- **Sizes:** 16 px inline (buttons, chips, menu items), 20 px panel headers/tabs, 24 px
  workbench bar + empty states.
- **Status glyphs:** 8 px dot (pulse when running) inside 16 px badge circles; check/!
  overlays on thumbnails (candidate approved/failed) at 20 px, top-right, `--status-*`.
- **Workbench icons** (locked set): Library `▤▤` grid, Script `✎`, Storyboard `🎬` film,
  Workflow `⚙`/graph, Render `▸` play-to, Edit `✂` scissors, Deliver `⇡` upload, Insights
  `📈` trend. All strokes, no fills.
- **Custom pictogram sets** (product-owned SVGs, static):
  - *CameraPicker*: push-in, orbit, dolly, tilt, crane, static (6).
  - *LightingPicker*: rim, soft, key, back, practical, none (6).
  - *CompositionPicker*: rule-of-thirds, center, leading-line, frame-in-frame, symmetry,
    negative-space (6).
  - Rendered as 44 px tiles with labels; selected tile = accent border.
- Icons never carry color other than `currentColor`; state comes from badges/dots around them.

---

## 24. Spacing System (deliverable 24)

| Token | Value | Usage |
|---|---|---|
| `--space-1` | 4 px | icon gaps, chip inner |
| `--space-2` | 8 px | input padding, tag gaps, card inner |
| `--space-3` | 12 px | card padding, list row gaps |
| `--space-4` | 16 px | panel padding, section gaps |
| `--space-5` | 24 px | panel group gaps, canvas margins |
| `--space-6` | 32 px | workbench margins, empty states |

- **Grid:** 4 px base; all spacings are multiples; canvas grids 24 px.
- **Chrome sizes (locked):** title bar 40 px · workbench bar 44 px · activity bar 64 px ·
  dock panel header 40 px · status bar 26 px · editor tab 36 px · control height 34 px ·
  table row 40 px · card padding 12 px.
- **Density variants:** *default* (above) everywhere; *timeline* denser (clips 24 px, ruler
  20 px); *canvas* looser (workbench content uses `--space-5/6`).
- **Zones:** left dock 280 px default (min 200 / max 480, resizable), right dock 320 px,
  bottom dock 200 px; editor splits min 320 px.
- **Virtual lists** (gallery/queue/log) keep fixed row heights for zero-shift streaming.

---

## 25. Component Library (deliverable 25)

### 25.1 Primitives

| Component | Locked spec |
|---|---|
| `Button` | h 34, radius 6, padding 0 16; primary = accent bg/inverse text; secondary = surface-3 + border-default; ghost = transparent + secondary text; danger = status-error bg. Hover +6% lightness, active +12%; disabled 0.45. Focus = ring. |
| `IconButton` | 34×34; ghost; tooltip required. |
| `Toggle` | 34×20 track (surface-3), 16 knob, accent when on; 200 ms. |
| `Checkbox` | 16 px, accent check, radius 4. |
| `SegmentedControl` | h 30, surface-3 track, active segment surface-4 + border-strong, indicator slides 200 ms. |
| `TextField/TextArea/NumberField` | h 34, surface-3, border-default, focus border-accent + ring; error border + 11 px message; mono mode for JSON/seed/path fields. |
| `Select/ComboBox` | custom popover (never native); list 200 px max-h, item h 28, virtualized. |
| `Slider` | 2 px track, 14 px thumb, accent fill. |
| `SearchField` | 34 px with ⌕ + Esc-to-clear; monochrome until focused. |
| `Tabs` | underline tabs (2 px accent slide), h 36; document tabs: 36 px, dirty dot, hover close ×, active = surface-2. |
| `ContextMenu` | surface-1, border-default, shadow-3, item h 28, radius 6, separator, kbd hint right-aligned; opens 100 ms. |
| `Tooltip` | surface-2, border-default, 11 px, radius 4, 120 ms. |
| `Modal` | surface-1, radius 10, shadow-3, scrim overlay, 300 ms scale .98→1. |
| `Sheet (Inspector)` | surface-1, left border, header 40 px with pin/detach. |
| `Toast` | 240 ms rise, 4 s auto-dismiss, action button inside, right-bottom above dock. |
| `StatusDot` | 8 px, pulse when running; `Badge` h 20 radius 4 soft bg + 11 px 600; `Tag` surface-3 + border. |
| `ProgressRing` | 34 px, 3 px stroke, 300 ms/segment sweep; `ProgressBar` 4 px track; `Spinner` 16/24 px stroke spinner. |
| `Skeleton` | surface-2 blocks with 1.2 s shimmer (gradient sweep, no layout shift). |
| `TreeView` | item h 26, chevron 16, indent 14/level, selection accent-soft. |
| `DataGrid` | sticky header (surface-2, label style), row h 40, hover surface-3, selected accent-soft + 2 px left bar, mono numerics right-aligned, virtualized. |
| `VirtualList` | fixed row height, windowed rendering, arrow-key nav. |
| `SplitView` | 4 px drag handle with accent hover; double-click = 50/50. |
| `Panel/PanelToolbar` | header h 40 (surface-2, label caption, actions right, detach handle), body surface-1. |
| `JsonView` | mono 11, syntax hues (keys primary, strings chart-2, numbers chart-4, booleans chart-6), collapsible nodes, copy/pretty, max-height + virtualized. |
| `EmptyState` | centered 24 px icon + title + subtitle + primary action. |
| `Stepper` | 28 px circles + connecting line, used in Welcome only. |

### 25.2 Composite & Domain (behaviors locked in UX_ARCHITECTURE §6)

| Component | Extra visual spec |
|---|---|
| `EpisodeCard` | 9:16 thumbnail 96×170 in a 12 px card; stage ring overlays thumbnail (34 px, bottom-right); ETA chip mono; drag handle on hover. |
| `SceneCard` | width 200; candidate strip 4×44 px thumbs; approve star overlays winner; camera/lighting chips 11 px; transition arrow 16 px connector. |
| `CandidateStrip` | thumbs 44×78, approved = accent-soft border + ok check; hover enlarge 1.05 with 200 ms. |
| `ChainNode` | h 40 pill: status dot + name + ms; active stage = info pulse border; cache badge ⇄ tertiary. |
| `WorkflowNode` | 220×variable; header (icon + name) surface-3, body surface-1, ports 8 px; selected accent-soft + accent border. |
| `BoardColumn` | 300 px column, header 40 px label + count badge, body = vertical scroll of cards, drop highlight = accent dashed border. |
| `TimelineClip` | h 24, thumbnail-left, mono duration, selected accent border; tracks labeled 160 px. |
| `Player` | 16:9 stage; transport 40 px (play/pause, frame step, timecode mono, volume); scrubber accent. |
| `KpiCard` | h 72: label caption + mono value 20 px + delta chip (ok/error). |
| `ConnectionCard` | h 120: status dot + name + latency mono + inline config (1 field) + actions (Test/Edit/Reveal). |
| `KnowledgeCard` | 220×150: category color chip + difficulty badge + topic (2 lines) + keywords tags (2 max) + scene count; hover lift 1.5 px. |
| `ProposalCard` | icon + pattern title + evidence line (mono n) + 2 action buttons (secondary/danger). |

### 25.3 Theming enforcement (locked)

1. `tokens.css` is the only source of color/type/space/motion values; hardcoding hex in a
   component is a review-blocking defect.
2. Components consume semantic tokens only (`--status-ok-soft`), never raw palettes.
3. Dark theme is the only theme (2S1–2S6); light theme out of scope.
4. Compact density is the only density (no comfort variant).
5. Surface ladder is never violated; focus rings are never removed; numbers are always
   `--numeric`.