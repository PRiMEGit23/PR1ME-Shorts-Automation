# PR1ME Studio — UX Review (deliverables 1–2 of the Redesign)

**Scope:** critical review of the previous UX architecture (page-based, `docs/product/UX_ARCHITECTURE.md`
v1) against the standard of a premium creative production suite (Cursor, VS Code, DaVinci Resolve,
Blender, Unreal, Bambu Studio, Lightroom, Figma).
**Constraint honored throughout:** the backend architecture is FINAL and untouched. Every redesign
decision below binds only to the product layer (`app/**`).

---

## 1. Verdict

The previous proposal was a **competent, well-engineered admin application**. It would not be
shipped by Apple, Adobe, Blackmagic, or Bambu. It was page-based, form-heavy, mouse-first, and
table-first — every screen read as "web dashboard" rather than "creative instrument."

What survives from v1 (correct instincts we keep and refine):

- Dock + Command Palette as global chrome.
- The dark, precise surface/token system (rebuilt with more personality below).
- Sidebar rail → Activity Bar (retained as the panel-toggle rail, not the navigation).
- The 15-stage pipeline rail idea (becomes the backbone of the Storyboard and Render UIs).
- The `pr1me run` CLI binding model, run-dir artifact binding, `.env` config surface,
  Production OS exports — the entire backend contract. **Unchanged.**

---

## 2. Problems with the Previous Proposal

### 2.1 Screen-by-screen verdict

| v1 screen | Verdict | Why it fails the "would Blackmagic ship it?" test |
|---|---|---|
| Dashboard (landing) | **Fail** | Landing = numbers = admin. A creative suite opens into *work* (recent productions), not statistics. Stats belong to an Insights mode you visit on purpose. |
| Generate (form page) | **Fail** | A page of selects and toggles. Generation is an *ambient action*: queue from anywhere (palette, toolbar, drag), watch it live in the Render board. |
| Queue (table) | **Fail** | An enterprise CRUD grid. A render queue is a *conveyor*: episode cards with live stage rings, thumbnails, ETA. Resolve/Bambu render as cards, not rows. |
| Knowledge Base (spreadsheet) | **Fail** | The KB is raw creative material. It must be a *visual gallery* (cards, covers, difficulty, category) with a fast full-screen editor only when editing data. Table mode is a secondary toggle, never the default. |
| Assets (tree + grid page) | **Fail** | Assets must be a *dockable panel* present in every workbench — drop targets for scenes, thumbnails everywhere. A page removes it from the work. |
| History (table page) | **Fail** | History is not a destination; it is the *done column* of the render board and the data behind Insights. |
| Workflow Viewer (tab under a run page) | **Fail** | The storyboard/prompt chain/ComfyUI graph is the **heart of the product** — it deserves its own workbench, not a buried page. |
| Settings (page) | **Fail** | Settings as a top-level destination screams admin. Preferences are a *modal*; provider management is a *Connection Center* with ambient health. |
| Projects (card list) | **Pass with changes** | The card instinct was right; but projects must be the *Library home* (like Lightroom's Library / Resolve's Media), not a sidebar page. |

### 2.2 The fifteen core problems

1. **Page navigation instead of workbench modes.** Routes/sidebar links force a browser mental
   model (URLs, back buttons). Creative suites use *modes* (Resolve pages, Lightroom modules,
   Blender workspaces) where the whole window re-composes for the task. Pages fragment the flow
   "select topic → storyboard → workflow → render → edit → deliver."
2. **No document model.** v1 had no tabs, no open documents, no undo/redo. Episodes (script,
   storyboard, workflow, metadata) are *documents* that should open in a tabbed editor area.
3. **No spatial or direct manipulation.** No drag-and-drop, no zoom/pan canvases, no timeline
   scrubbing, no candidate-strip approval. The product generates *visuals* — the UI must handle
   visuals like Lightroom (approve/star), Resolve (clips on a timeline), Figma (canvas).
4. **Form-based generation.** Selecting rows + fields + a big button is a web checkout flow.
   The creative flow is: choose episodes in the Library/Script, then *queue* them; the queue is
   the feedback surface.
5. **Queue as a grid of rows.** Status text in cells cannot express a 15-stage production run.
   Visual state (rings, rails, thumbnails) communicates instantly.
6. **Knowledge base as a spreadsheet.** 39-column editing as the primary view buries the creative
   signal (topic, category, difficulty) under cells. Browsing must be visual; editing must be a
   dedicated, schema-aware editor — not a grid.
7. **Inspector absent.** No context-sensitive properties panel. In every creative suite, selecting
   something opens its properties (scene camera, node, provider, clip) in a right-side inspector.
8. **No timeline.** A Short is *time*: narration, scenes, subtitles, overlays. v1 had no timeline
   or preview player anywhere.
9. **Settings and provider config as first-class navigation.** Connection/health is ambient
   (status dots, palette commands); preferences are a modal. Top-level pages for them waste
   the creative surface.
10. **Single fixed window.** No detachable panels = no multi-monitor workflows. Professional
    suites let you tear out panels (Fusion page, Blender editors).
11. **Mouse-first.** Shortcuts were an afterthought. A serious tool is keyboard-first with a
    coherent system: workbench switching, palette, arrows, space-to-play.
12. **No contextual menus.** Right-click was never specified. Every surface (scene, node, clip,
    provider, KB card) needs one.
13. **Generic dark-admin aesthetic.** v1 tokens were competent but anonymous — any B2B dark
    theme. The product needs a distinct design language (see Visual Design System v2):
    editorial typography, restrained color, filmstrip chrome.
14. **History/dashboard as landing content.** Landing on charts is the definitive admin tell.
    Land on *work*; show charts only in Insights.
15. **Generation feedback gap.** v1 had no mechanism for approve/regenerate per scene, no
    candidate comparison, no visible "the storyboard is being built live." The pipeline's
    determinism means regeneration must be a *product-level* mechanism (see §12, seed-bump
    + `--resume`), and the UI must make that feel instantaneous and visual.

### 2.3 Root cause

The v1 proposal answered "how do we expose these 14 features as screens?" instead of
**"what is the artist's journey through a Short's lifecycle?"** The journey is linear and
creative (story → plan → generate → assemble → deliver → learn), so the product must be a
*studio with modes*, not a *website with pages*.

---

## 3. Principles the Redesign is Built On

1. **Workbench modes, not pages.** Eight modes; the window re-composes per mode; no back
   buttons; palette is the universal jump.
2. **Visual is primary.** Thumbnails, filmstrips, canvases, timelines. Text tables are the
   fallback, never the default.
3. **Direct manipulation everywhere.** Drag, drop, reorder, scrub, select, approve.
4. **Inspector over forms.** Select → properties. Non-modal, live.
5. **Documents with undo.** Episodes open as tabs; every edit is undoable; dirty state visible.
6. **Ambient generation.** Queue from anywhere; the Render board is the feedback loop.
7. **Ambient health.** Providers are connections (dots, palette, Connection Center), not forms.
8. **Keyboard-first.** Every action has a shortcut; palette completes the long tail.
9. **Determinism is a feature, not a constraint.** The pipeline is deterministic and locked;
   the product adds *review layers* (approval, candidates, history) on top — never changes the
   pipeline. Regenerate = new seed + `--resume` (upstream stages cache-hit; only the render loop
   re-runs). Scene order is script-locked; reordering is a script edit.
10. **Multi-monitor by default.** Every panel is detachable to its own window.

---

*Next: the complete architecture in `UX_ARCHITECTURE.md` v2, and the design system in
`VISUAL_DESIGN_SYSTEM.md` v2.*