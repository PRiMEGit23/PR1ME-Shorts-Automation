# Image QA Engine (Phase 4) — Proposal

Pure architecture phase. Nothing below this subsystem is modified: the
runtime, the Educational Director, Visual Intelligence, and the Prompt
Compiler are untouched. All existing tests remain green; every QA decision is
deterministic; the engine never re-renders anything.

## 1. Updated architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Knowledge Base  (assets/knowledge_base.csv, 400 curated rows)   │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Knowledge Director   WHAT matters                                │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Educational Director   HOW it is best TAUGHT  → EducationalPlan │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Visual Intelligence   HOW each beat is SHOT  → VisualStoryboard │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Storyboard → Prompt Compiler  HOW it is PHRASED  → CompiledPrompt│
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Workflow Builder → ComfyUI    HOW it is RENDERED                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │ GeneratedImageMetadata
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Image QA Engine  (this phase)   ACCEPT or REJECT                 │
│   engineering_critic · educational_critic · composition_critic  │
│   consistency_critic · thumbnail_critic                          │
│   → ImageQualityReport: 8 scores + pass/fail + repairs          │
│   RenderRepairEngine → deterministic instructions, never        │
│   re-renders; a human or future stage decides to act            │
└─────────────────────────────────────────────────────────────────┘
```

## 2. The checks

Every generated image is judged against the thirteen checks:

| Check | Owned by | What it verifies |
|---|---|---|
| Primary subject visibility | composition | subject present, prominent, unoccluded |
| Subject hierarchy | composition | primary subject dominates as directed |
| Engineering accuracy | engineering | reported accuracy vs the plan |
| Geometry correctness | engineering | geometry quality, zeroed when wrong |
| Material correctness | engineering | material plausibility, zeroed when wrong |
| Camera suitability | engineering | observed camera vs the CameraPlan |
| Lighting suitability | engineering | observed lighting vs the LightingPlan |
| Composition quality | composition | planned rule followed, quality floor |
| Visual clutter | composition | clean frame for a 9:16 short |
| Educational effectiveness | educational | plan's method implemented, annotations, comparison axis |
| Thumbnail strength | thumbnail | contrast, focus, negative space (candidate only) |
| Scene consistency | consistency | continuity vs world, palette, tags |
| Prompt consistency | consistency | required subject/shot/viz terms in the compiled prompt |

## 3. Scores and thresholds

- Eight scores (0..100): Engineering, Educational, Composition, Subject
  Hierarchy, Visual Clarity, Thumbnail, Consistency, and the weighted
  Overall.
- Weights: engineering 0.20, educational 0.20, composition 0.15, subject
  hierarchy 0.10, visual clarity 0.10, thumbnail 0.10, consistency 0.15.
- **PASS** requires: overall ≥ 75 **and** every sub-score ≥ 50 **and** no
  critical issue. Anything else is **FAIL**.
- The report schema enforces the rule itself: constructing a report whose
  scores contradict its pass/fail verdict raises a validation error.

## 4. The repair engine

`RenderRepairEngine` maps each check to deterministic repair instructions
(e.g. "Increase subject prominence", "Switch to macro shot", "Remove
distracting background", "Improve lighting direction", "Increase engineering
annotations", "Improve comparison framing"). It only emits instructions —
there is no code path that re-renders, and the same issue always produces the
same instruction.

## 5. Inputs and outputs

- Inputs: `EducationalPlan`, `VisualStoryboard`, `CompiledPrompt`, and
  `GeneratedImageMetadata` — the structured facts a vision pipeline reports
  about the actual render (subject presence, prominence, clutter, camera and
  lighting matches, geometry and material quality, annotations, consistency
  violations). This is the only input that comes from the render itself.
- Output: `ImageQualityReport` with `OverallScore`, `EngineeringScore`,
  `EducationalScore`, `CompositionScore`, `SubjectHierarchyScore`,
  `VisualClarityScore`, `ThumbnailScore`, `ConsistencyScore`, `PassFail`,
  `RepairSuggestions`, plus the underlying issues with severities.

## 6. Worked examples (verified runs)

| Example | Defect | Verdict | Representative repairs |
|---|---|---|---|
| Gyroid infill (S1–S5) | none — faithful renders | pass (≈95–100) | — |
| Planetary gears (S2) | occluded subject, wrong material, camera/lighting mismatch, clutter, violation | fail (75.7) | Increase subject prominence, Switch to macro shot, Remove distracting background, Re-render with the correct material finish |
| Injection molding (S2) | missing annotations, clutter, off-rule composition | fail (80.8, educational 33.3) | Increase engineering annotations, Remove distracting background, Recompose to the planned framing rule |

## 7. Next phase (not part of this proposal)

Feeding the pass/fail verdict back into the runtime: a repair-and-retry loop
that a human approves before any re-render happens.