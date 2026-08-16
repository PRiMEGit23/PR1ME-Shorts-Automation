# PR1ME Studio — Visual Design System (LOCKED)

**Status:** LOCKED. Implement `tokens.css` exactly; no deviations, no ad-hoc colors.

The system is a **dark, engineering-grade** theme: high information density, precise
borders, restrained accent color, and motion that communicates state without distraction.

---

## 1. Color Tokens

### 1.1 Surfaces (backgrounds)

| Token | Value | Usage |
|---|---|---|
| `--surface-0` | `#0B0E14` | window / app background |
| `--surface-1` | `#11151D` | panels, cards |
| `--surface-2` | `#171C26` | raised panels, table headers |
| `--surface-3` | `#1E2430` | inputs, hover states |
| `--surface-4` | `#252C3B` | active row, pressed states |
| `--overlay` | `rgba(5,7,10,0.72)` | modal/drawer scrim |

### 1.2 Borders & Dividers

| Token | Value | Usage |
|---|---|---|
| `--border-subtle` | `#1C2230` | panel dividers |
| `--border-default` | `#262E3F` | controls, cards |
| `--border-strong` | `#333D52` | hover, focused chrome |
| `--border-accent` | `#3D7EFF` | focus rings, active tabs |

### 1.3 Text

| Token | Value | Usage |
|---|---|---|
| `--text-primary` | `#E6EAF2` | headings, body |
| `--text-secondary` | `#9AA3B5` | labels, metadata |
| `--text-tertiary` | `#5C6577` | disabled, placeholders |
| `--text-inverse` | `#0B0E14` | text on accent buttons |
| `--text-link` | `#6FA3FF` | links |

### 1.4 Accent (PR1ME blue)

| Token | Value | Usage |
|---|---|---|
| `--accent` | `#3D7EFF` | primary buttons, active states, focus |
| `--accent-hover` | `#5B93FF` | hover |
| `--accent-active` | `#2E66D6` | pressed |
| `--accent-soft` | `rgba(61,126,255,0.14)` | selected row, badge bg |
| `--accent-soft-strong` | `rgba(61,126,255,0.22)` | selected hover |

### 1.5 Status

| Token | Value | Usage |
|---|---|---|
| `--status-ok` | `#3FB96A` | completed, passed, healthy |
| `--status-ok-soft` | `rgba(63,185,106,0.14)` | badge bg |
| `--status-warn` | `#E5A83B` | pending, paused, retry |
| `--status-warn-soft` | `rgba(229,168,59,0.14)` | badge bg |
| `--status-error` | `#E5484D` | failed, errors |
| `--status-error-soft` | `rgba(229,72,77,0.14)` | badge bg |
| `--status-info` | `#38BDF8` | running, info |
| `--status-info-soft` | `rgba(56,189,248,0.14)` | badge bg |
| `--status-muted` | `#5C6577` | cancelled, idle, skipped |

### 1.6 Charts

| Token | Value |
|---|---|
| `--chart-1` | `#3D7EFF` |
| `--chart-2` | `#38BDF8` |
| `--chart-3` | `#3FB96A` |
| `--chart-4` | `#E5A83B` |
| `--chart-5` | `#E5484D` |
| `--chart-6` | `#A78BFA` |

---

## 2. Typography

| Token | Value |
|---|---|
| `--font-ui` | `"Inter", "Segoe UI", system-ui, sans-serif` |
| `--font-mono` | `"JetBrains Mono", "Cascadia Code", Consolas, monospace` |
| `--text-xs` | 11px / 16px, 500 |
| `--text-sm` | 12.5px / 18px, 500 |
| `--text-base` | 14px / 21px, 500 |
| `--text-lg` | 16px / 24px, 600 |
| `--text-xl` | 20px / 28px, 600 |
| `--text-2xl` | 26px / 34px, 700 (page titles) |
| `--text-mono-xs` | 11px mono, 400 (JSON, hashes, ids) |

Rules:
- Numeric data (tick counts, QA scores, durations, ETA) renders in `--font-mono`
  with tabular figures.
- IDs, hashes, fingerprints, JSON: `--font-mono` at `--text-xs`/`--text-mono-xs`.
- Headings never exceed `--text-2xl`; page titles are sentence case.

---

## 3. Spacing, Radius, Elevation

| Token | Value | Usage |
|---|---|---|
| `--space-1` | 4px | inner icon gaps |
| `--space-2` | 8px | input padding, tag gaps |
| `--space-3` | 12px | card padding, row gaps |
| `--space-4` | 16px | panel padding |
| `--space-5` | 24px | section gaps |
| `--space-6` | 32px | page margins |
| `--radius-sm` | 4px | tags, badges |
| `--radius-md` | 6px | inputs, buttons, cards |
| `--radius-lg` | 10px | modals, drawers, large cards |
| `--shadow-1` | `0 1px 2px rgba(0,0,0,.4)` | cards on surface-1 |
| `--shadow-2` | `0 4px 12px rgba(0,0,0,.45)` | popovers, palette |
| `--shadow-3` | `0 12px 40px rgba(0,0,0,.55)` | modals, drawers |
| `--ring` | `0 0 0 2px var(--border-accent)` | focus ring (2px offset) |

Layout constants: sidebar 64px (collapsed) / 200px (expanded); dock 48px;
titlebar 40px (native); max content width 1280px, centered.

---

## 4. Motion

| Token | Value |
|---|---|
| `--ease-out` | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `--ease-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` |
| `--dur-fast` | 120ms |
| `--dur-base` | 200ms |
| `--dur-slow` | 300ms |
| `--dur-palette` | 120ms (scale .98→1 + fade) |
| `--dur-toast` | 240ms slide-up |

Usage contract:
- Hover/active: `--dur-fast`, colors + elevation only.
- State morph (status badge): `--dur-base` color/icon, no layout shift.
- Panels/drawers/palette/modals: `--dur-slow` transform+fade with `--ease-out`.
- Progress bars: width transitions `--dur-base`; indeterminate shimmer 1.2s loop.
- Respect `prefers-reduced-motion`: drop all transforms to opacity-only, 0ms.

---

## 5. Component Specifications (locked details)

### 5.1 Button

| Variant | Styles |
|---|---|
| `primary` | bg `--accent`, text `--text-inverse`, radius-md, h 34px, padding 0 16px, hover `--accent-hover`, active `--accent-active`, disabled opacity .45 |
| `secondary` | bg `--surface-3`, border `--border-default`, text `--text-primary`, hover bg `--surface-4` |
| `ghost` | transparent, text `--text-secondary`, hover bg `--surface-3` + text primary |
| `danger` | bg `--status-error`, text inverse, hover darken 6% |
| `icon` | 34×34px square, ghost; tooltip on hover |

### 5.2 Badge / Tag

- Height 20px, padding 0 8px, `--radius-sm`, 11px 600.
- Status badges use `*-soft` background + matching text color.
- Category tags: `--surface-3` bg, `--text-secondary`, border `--border-default`.

### 5.3 Input / Select / Textarea

- Height 34px, bg `--surface-3`, border `--border-default`, radius-md, text-base.
- Focus: border `--border-accent` + `--ring`.
- Error: border `--status-error`; helper text 11px `--status-error`.
- Textarea: min-height 84px, mono only for JSON fields.

### 5.4 DataTable

- Header: `--surface-2`, 12px 600 uppercase, letter-spacing .04em, text-tertiary.
- Rows: 40px height, zebra off; hover `--surface-3`; selected `--accent-soft` +
  border-left 2px `--accent`.
- Numeric cells right-aligned mono. Checkboxes 16px accent.
- Virtualized above 200 rows; sticky header + first column.

### 5.5 Sidebar & Dock

- Sidebar: `--surface-0` with 1px right `--border-subtle`. Item: 40×40 icon button,
  radius-md; active: `--accent-soft` bg + `--accent` icon + 2px left bar.
- Dock: `--surface-1` with 1px top `--border-subtle`; GenerateButton fills left
  cluster; status chip right cluster.

### 5.6 Command Palette

- 640px wide, centered 20% from top, `--surface-1`, `--shadow-3`, radius-lg.
- Input row 48px; results max-height 400px, item 40px, selected `--surface-4`.
- Kbd chips: `--surface-3`, 11px mono, border-default.

### 5.7 Charts

- Gridlines `--border-subtle` 1px; axis labels text-tertiary 11px mono.
- Bars rounded 2px; donut stroke-width 12px; gauges 120° arc.
- Tooltip: `--surface-2` card, shadow-2, 12px mono values.

### 5.8 Icons

- Stroke-based set (Lucide), 16px default, 1.5 stroke, `currentColor`.
- State icons: dot 8px with status color + soft glow on running.

---

## 6. Theming Rules (enforcement)

1. `tokens.css` is the ONLY source of color/type/spacing/motion values. Components never
   hardcode hex.
2. Semantic-only usage: components consume semantic tokens (e.g. `--status-ok-soft`),
   never raw palette.
3. Dark theme is the only theme in 2S1..2S6; light theme is out of scope.
4. Density: compact by default (34px controls) — matches the locked spec, no "comfort"
   variant.
5. All surfaces stack: `--surface-0` < `--surface-1` < `--surface-2` < `--surface-3`
   < `--surface-4` (never a surface under a lighter one).
6. Focus is never removed; keyboard nav always visible.