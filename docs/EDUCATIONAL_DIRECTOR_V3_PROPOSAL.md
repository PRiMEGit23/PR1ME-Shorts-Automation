# Educational Director (Phase 3) — Proposal

Pure architecture phase. Nothing below this subsystem is modified: the runtime
pipeline, the Knowledge Base CSV, the Prompt Compiler, Visual Intelligence,
the Storyboard, and the Workflow Builder are untouched. All 230+ tests remain
green.

## 1. Updated architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Knowledge Base  (assets/knowledge_base.csv, 400 curated rows)   │
└──────────────────────────────┬──────────────────────────────────┘
                               │ KnowledgeBaseRow (CSV record)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Knowledge Director        WHAT matters                           │
│   concept, misconception, phenomenon, difficult visualization,  │
│   objective, takeaway, prior knowledge, domain                  │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Educational Director        HOW it is best TAUGHT                │
│   teaching strategy, visual methods, cognitive sequence,        │
│   attention hook, retention, mental model, comparison, analogy, │
│   animation need, failure mode, final takeaway                  │
│   └─ strategy_selector · visual_method_selector · cognitive_flow│
└──────────────────────────────┬──────────────────────────────────┘
                               │ EducationalPlan (16 fields)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Visual Intelligence (Phase 2)   HOW each beat is SHOT            │
│   VisualGoal per scene → shot types → camera/lighting/          │
│   composition/transitions → thumbnail priority                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ VisualStoryboard
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Storyboard → Prompt Compiler   HOW it is PHRASED per model       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ CompiledRow (SDXL/FLUX/GPT/Qwen)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Workflow Builder → ComfyUI    HOW it is RENDERED                 │
└─────────────────────────────────────────────────────────────────┘
```

The pipeline now has four explicit decisions where a prompt-only system has
one: **what** to teach (Knowledge Director), **how to teach it** (Educational
Director), **how to shoot it** (Visual Intelligence), and **how to phrase it**
(Prompt Compiler). Each layer receives the previous layer's output as a
structured, deterministic, documented plan — never as free text.

## 2. Why this produces better educational videos than a prompt-only system

A prompt-only system treats a video as a string to generate. The Educational
Director treats it as an argument to make. Concretely:

1. **Teaching intent precedes rendering intent.** The gyroid topic is not
   "five SDXL prompts" — it is *"compare three infill patterns so the viewer
   chooses the right one for the load"*. That objective constrains everything
   below: the shots become a comparison arc, not a gallery. A prompt-only
   system has no concept of the objective, so every scene is equally likely
   and the video degenerates into "pictures of cubes".
2. **Every visualization is justified, never random.** The Educational
   Director's rules tie each visual method to a reason: cross-section because
   the concept is internal structure, stress visualization because the
   phenomenon is force distribution, transparent housing because the teaching
   strategy is progressive disclosure. The quality rule "never choose visuals
   randomly" is enforced by construction: there is no random source in the
   system.
3. **The cognitive sequence models how people actually learn.** Thirty-second
   videos are won or lost on their arc: hook → question → reveal → explain →
   evidence → conclude. The flow builder guarantees an opening that captures
   attention and a closing that states the takeaway; the failure-mode table
   names what would kill *this* topic's explanation (e.g. "comparison without
   context" for comparison topics) so the downstream visual director can
   defend against it.
4. **Misconceptions are taught against, not ignored.** The plan extracts the
   curated misconception, names why it is common, and pairs it with its
   refutation. A prompt-only system cannot know that "molding is always
   cheaper" is the belief to overturn, so its video — however beautiful —
   fails to change the viewer's mind.
5. **Retention is designed in.** The retention method (visual anchor, mental
   model, concrete reference) decides what the viewer keeps. The comparison
   board stays on screen as the memory peg; the mental model is stated as a
   transferable sentence. Prompts produce images; plans produce understanding.
6. **Everything remains deterministic and auditable.** Each choice carries a
   rationale string that survives into the plan, so a curator can inspect why
   a topic got "manufacturing sequence" and not "animation first" — and fix
   the rule table, not the prompt.
7. **The layers compose without coupling.** The Educational Plan does not
   mention cameras or prompts; the Visual Storyboard does not mention teaching
   strategy. Either layer can be re-run or re-rendered independently, and new
   models (FLUX, GPT Image) slot in at the compiler alone.

## 3. Module map

```
knowledge/educational_director/
    educational_models.py       EducationalPlan + taxonomies (enums)
    knowledge_director.py       extraction: what matters, prior knowledge, domain
    learning_objectives.py      measurable outcome + success verbs
    strategy_selector.py        teaching strategy table (21 strategies)
    visual_method_selector.py   visual methods per strategy (19 methods) + refinements
    cognitive_flow.py           cognitive sequences, hooks, retention, mental
                                models, analogies, comparisons, failure modes,
                                animation requirement, knowledge flow
    educational_director.py     orchestrator: row → EducationalPlan
    examples/                   gyroid · planetary_gear · injection_molding
```

## 4. Example outcomes (verified runs)

| Topic | Strategy | Primary visual methods | Cognitive arc | Animation |
|---|---|---|---|---|
| Infill Pattern Comparisons | comparison | comparison board, cross section, stress visualization | hook → question → comparison → reveal → explanation → evidence → conclusion | yes |
| Planetary Gears | progressive disclosure | transparent housing, motion visualization, exploded view, animation | hook → question → reveal → explanation → evidence → conclusion | yes |
| Injection Molding | manufacturing sequence | exploded view, animation, thermal visualization, timeline | hook → problem → explanation → evidence → example → conclusion | yes |

## 5. Next phase (not part of this proposal)

Bridging the EducationalPlan into the Visual Intelligence engine: a mapping
from TeachingStrategy/VisualTeachingMethod to the Phase 2 goal/shot tables, so
the director's intent becomes the storyboard's first input.
