"""Cognitive flow: the learning arc, attention, retention, and teaching aids.

This module owns everything the Educational Director must decide about HOW
people learn the topic: the step-by-step cognitive sequence (a template per
teaching strategy), the attention hook, the per-step knowledge flow (concept
+ visual method per beat), the retention method, the expected mental model,
the comparison and analogy strategies, the animation requirement, and the
most likely failure mode. Every decision is table-driven and justified.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import cycle

from knowledge.educational_director.educational_models import (
    AnimationRequirement,
    CognitiveStep,
    DifficultyLevel,
    FailureMode,
    KnowledgeDirectorResult,
    KnowledgeFlowStep,
    RetentionMethod,
    TeachingStrategy,
    VisualTeachingMethod,
)

_COGNITIVE_TEMPLATES: dict[TeachingStrategy, tuple[CognitiveStep, ...]] = {
    TeachingStrategy.COMPARISON: (
        CognitiveStep.HOOK,
        CognitiveStep.QUESTION,
        CognitiveStep.COMPARISON,
        CognitiveStep.REVEAL,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.BEFORE_AFTER: (
        CognitiveStep.HOOK,
        CognitiveStep.COMPARISON,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.CAUSE_EFFECT: (
        CognitiveStep.HOOK,
        CognitiveStep.PROBLEM,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.PROBLEM_SOLUTION: (
        CognitiveStep.HOOK,
        CognitiveStep.PROBLEM,
        CognitiveStep.SOLUTION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.EXAMPLE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.QUESTION_ANSWER: (
        CognitiveStep.HOOK,
        CognitiveStep.QUESTION,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.EXAMPLE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.LAYER_BY_LAYER_REVEAL: (
        CognitiveStep.HOOK,
        CognitiveStep.REVEAL,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.HIDDEN_GEOMETRY: (
        CognitiveStep.HOOK,
        CognitiveStep.REVEAL,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.FAILURE_ANALYSIS: (
        CognitiveStep.HOOK,
        CognitiveStep.PROBLEM,
        CognitiveStep.FAILURE,
        CognitiveStep.ROOT_CAUSE,
        CognitiveStep.SOLUTION,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.MECHANICAL_BREAKDOWN: (
        CognitiveStep.HOOK,
        CognitiveStep.QUESTION,
        CognitiveStep.REVEAL,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.ANIMATION_FIRST: (
        CognitiveStep.HOOK,
        CognitiveStep.DEMONSTRATION,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.DIAGRAM_FIRST: (
        CognitiveStep.HOOK,
        CognitiveStep.DEFINITION,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.SCALE_COMPARISON: (
        CognitiveStep.HOOK,
        CognitiveStep.COMPARISON,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.PROGRESSIVE_DISCLOSURE: (
        CognitiveStep.HOOK,
        CognitiveStep.QUESTION,
        CognitiveStep.REVEAL,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.MYTH_BUSTING: (
        CognitiveStep.HOOK,
        CognitiveStep.MYTH,
        CognitiveStep.EVIDENCE,
        CognitiveStep.EXPLANATION,
        CognitiveStep.COMPARISON,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.REAL_WORLD_EXAMPLE: (
        CognitiveStep.HOOK,
        CognitiveStep.EXAMPLE,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.SIMULATION: (
        CognitiveStep.HOOK,
        CognitiveStep.DEMONSTRATION,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.PROCESS_TIMELINE: (
        CognitiveStep.HOOK,
        CognitiveStep.QUESTION,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.EXAMPLE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.MANUFACTURING_SEQUENCE: (
        CognitiveStep.HOOK,
        CognitiveStep.PROBLEM,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.EXAMPLE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.FORCE_FLOW: (
        CognitiveStep.HOOK,
        CognitiveStep.PROBLEM,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.ENERGY_FLOW: (
        CognitiveStep.HOOK,
        CognitiveStep.PROBLEM,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
    TeachingStrategy.MATERIAL_TRANSFORMATION: (
        CognitiveStep.HOOK,
        CognitiveStep.PROBLEM,
        CognitiveStep.EXPLANATION,
        CognitiveStep.EVIDENCE,
        CognitiveStep.CONCLUSION,
    ),
}

_FALLBACK_SEQUENCE = (
    CognitiveStep.HOOK,
    CognitiveStep.QUESTION,
    CognitiveStep.EXPLANATION,
    CognitiveStep.EVIDENCE,
    CognitiveStep.CONCLUSION,
)

_ATTENTION_HOOKS: dict[TeachingStrategy, str] = {
    TeachingStrategy.COMPARISON: "Three cubes, same size, three different strengths.",
    TeachingStrategy.BEFORE_AFTER: "Watch what changes when the process changes.",
    TeachingStrategy.CAUSE_EFFECT: "One small change. One big failure.",
    TeachingStrategy.PROBLEM_SOLUTION: "This part fails every time. Here is why - and the fix.",
    TeachingStrategy.QUESTION_ANSWER: "You have asked this question a hundred times.",
    TeachingStrategy.LAYER_BY_LAYER_REVEAL: "Every layer you cannot see is deciding the outcome.",
    TeachingStrategy.HIDDEN_GEOMETRY: "Everything that matters is hidden inside.",
    TeachingStrategy.FAILURE_ANALYSIS: "It broke. The crack has a story to tell.",
    TeachingStrategy.MECHANICAL_BREAKDOWN: "This box is tiny. What it does inside is not.",
    TeachingStrategy.ANIMATION_FIRST: "Do not read the answer. Watch it move first.",
    TeachingStrategy.DIAGRAM_FIRST: "One drawing explains what ten words cannot.",
    TeachingStrategy.SCALE_COMPARISON: "Size is the hidden variable.",
    TeachingStrategy.PROGRESSIVE_DISCLOSURE: "Everything you need fits in this box - and hides a trick.",
    TeachingStrategy.MYTH_BUSTING: "Everything you were told about this is backwards.",
    TeachingStrategy.REAL_WORLD_EXAMPLE: "You used this today. You had no idea why it worked.",
    TeachingStrategy.SIMULATION: "Let us break it virtually, so you do not break it for real.",
    TeachingStrategy.PROCESS_TIMELINE: "Five steps. Twenty seconds. One part.",
    TeachingStrategy.MANUFACTURING_SEQUENCE: "This part was finished in seconds. Inside, a lot just happened.",
    TeachingStrategy.FORCE_FLOW: "Force is a traveler. Follow where it goes.",
    TeachingStrategy.ENERGY_FLOW: "Energy never disappears. Watch where it goes.",
    TeachingStrategy.MATERIAL_TRANSFORMATION: "Same material. Completely different behavior.",
}

_FALLBACK_HOOK = "Look closer - the answer is not where you expect it."

_RETENTION_METHODS: dict[TeachingStrategy, RetentionMethod] = {
    TeachingStrategy.COMPARISON: RetentionMethod.VISUAL_ANCHOR,
    TeachingStrategy.BEFORE_AFTER: RetentionMethod.VISUAL_ANCHOR,
    TeachingStrategy.CAUSE_EFFECT: RetentionMethod.MENTAL_MODEL,
    TeachingStrategy.PROBLEM_SOLUTION: RetentionMethod.MENTAL_MODEL,
    TeachingStrategy.QUESTION_ANSWER: RetentionMethod.RECAP,
    TeachingStrategy.LAYER_BY_LAYER_REVEAL: RetentionMethod.CHUNKING,
    TeachingStrategy.HIDDEN_GEOMETRY: RetentionMethod.VISUAL_ANCHOR,
    TeachingStrategy.FAILURE_ANALYSIS: RetentionMethod.MENTAL_MODEL,
    TeachingStrategy.MECHANICAL_BREAKDOWN: RetentionMethod.CHUNKING,
    TeachingStrategy.ANIMATION_FIRST: RetentionMethod.CONCRETE_REFERENCE,
    TeachingStrategy.DIAGRAM_FIRST: RetentionMethod.VISUAL_ANCHOR,
    TeachingStrategy.SCALE_COMPARISON: RetentionMethod.CONCRETE_REFERENCE,
    TeachingStrategy.PROGRESSIVE_DISCLOSURE: RetentionMethod.MENTAL_MODEL,
    TeachingStrategy.MYTH_BUSTING: RetentionMethod.RECAP,
    TeachingStrategy.REAL_WORLD_EXAMPLE: RetentionMethod.CONCRETE_REFERENCE,
    TeachingStrategy.SIMULATION: RetentionMethod.MENTAL_MODEL,
    TeachingStrategy.PROCESS_TIMELINE: RetentionMethod.CHUNKING,
    TeachingStrategy.MANUFACTURING_SEQUENCE: RetentionMethod.CONCRETE_REFERENCE,
    TeachingStrategy.FORCE_FLOW: RetentionMethod.MENTAL_MODEL,
    TeachingStrategy.ENERGY_FLOW: RetentionMethod.MENTAL_MODEL,
    TeachingStrategy.MATERIAL_TRANSFORMATION: RetentionMethod.MENTAL_MODEL,
}

_RETENTION_RATIONALES: dict[RetentionMethod, str] = {
    RetentionMethod.VISUAL_ANCHOR: "the comparison board stays on screen as the memory peg",
    RetentionMethod.CONCRETE_REFERENCE: "a real object the viewer has touched anchors the idea",
    RetentionMethod.MENTAL_MODEL: "the viewer leaves with a transferable model, not a fact",
    RetentionMethod.RECAP: "the answer is restated against the false belief",
    RetentionMethod.CHUNKING: "the steps are chunked into a short numbered chain",
    RetentionMethod.MNEMONIC: "a compact phrase encodes the takeaway",
}

_FAILURE_MODES: dict[TeachingStrategy, FailureMode] = {
    TeachingStrategy.COMPARISON: FailureMode.COMPARISON_WITHOUT_CONTEXT,
    TeachingStrategy.BEFORE_AFTER: FailureMode.COMPARISON_WITHOUT_CONTEXT,
    TeachingStrategy.CAUSE_EFFECT: FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR,
    TeachingStrategy.PROBLEM_SOLUTION: FailureMode.NO_STAKES,
    TeachingStrategy.QUESTION_ANSWER: FailureMode.OVERLOAD,
    TeachingStrategy.LAYER_BY_LAYER_REVEAL: FailureMode.WRONG_SEQUENCE,
    TeachingStrategy.HIDDEN_GEOMETRY: FailureMode.TERMS_BEFORE_INTUITION,
    TeachingStrategy.FAILURE_ANALYSIS: FailureMode.MISCONCEPTION_UNCHALLENGED,
    TeachingStrategy.MECHANICAL_BREAKDOWN: FailureMode.OVERLOAD,
    TeachingStrategy.ANIMATION_FIRST: FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR,
    TeachingStrategy.DIAGRAM_FIRST: FailureMode.TERMS_BEFORE_INTUITION,
    TeachingStrategy.SCALE_COMPARISON: FailureMode.MISSING_SCALE,
    TeachingStrategy.PROGRESSIVE_DISCLOSURE: FailureMode.TERMS_BEFORE_INTUITION,
    TeachingStrategy.MYTH_BUSTING: FailureMode.MISCONCEPTION_UNCHALLENGED,
    TeachingStrategy.REAL_WORLD_EXAMPLE: FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR,
    TeachingStrategy.SIMULATION: FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR,
    TeachingStrategy.PROCESS_TIMELINE: FailureMode.WRONG_SEQUENCE,
    TeachingStrategy.MANUFACTURING_SEQUENCE: FailureMode.WRONG_SEQUENCE,
    TeachingStrategy.FORCE_FLOW: FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR,
    TeachingStrategy.ENERGY_FLOW: FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR,
    TeachingStrategy.MATERIAL_TRANSFORMATION: FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR,
}

_FAILURE_RATIONALES: dict[FailureMode, str] = {
    FailureMode.COMPARISON_WITHOUT_CONTEXT: (
        "comparing options without showing what each axis means leaves no reason to choose"
    ),
    FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR: (
        "an invisible phenomenon needs a visible proxy or it is never believed"
    ),
    FailureMode.NO_STAKES: (
        "without a visible consequence the viewer has no reason to care"
    ),
    FailureMode.OVERLOAD: (
        "too many moving parts at once exceed working memory"
    ),
    FailureMode.WRONG_SEQUENCE: (
        "showing a later step before the foundation invalidates the chain"
    ),
    FailureMode.TERMS_BEFORE_INTUITION: (
        "naming the concept before showing the behavior makes the words empty"
    ),
    FailureMode.MISSING_SCALE: (
        "without a familiar reference the claimed size is meaningless"
    ),
    FailureMode.MISCONCEPTION_UNCHALLENGED: (
        "if the false belief is not named, the viewer keeps it and discards the fix"
    ),
}

_MENTAL_MODELS: dict[tuple[str, ...], str] = {
    ("gyroid", "infill", "isotropic"): (
        "Load travels along continuous curved surfaces, so a gyroid distributes "
        "force evenly in every direction."
    ),
    ("planetary", "sun gear", "epicyclic"): (
        "In a planetary set the input/output choice sets the ratio, and the "
        "planets split the load."
    ),
    ("injection", "molding"): (
        "A part's cost collapses once volume pays back the one-time steel tool."
    ),
    ("gear ratio",): (
        "A small gear driving a big gear trades speed for torque, countably."
    ),
    ("layer height",): (
        "Thinner layers smooth surfaces; every halving roughly doubles print time."
    ),
}

_COMPARISON_STRATEGIES: dict[tuple[str, ...], str] = {
    ("gyroid", "infill"): (
        "grid vs cubic vs gyroid on strength per gram, isotropy, and print speed"
    ),
    ("planetary", "sun gear"): (
        "sun vs ring vs carrier as input, on ratio, direction, and torque"
    ),
    ("injection", "molding"): (
        "printed vs machined vs molded on cost per part and break-even volume"
    ),
}

_ANALOGY_STRATEGIES: dict[tuple[str, ...], str] = {
    ("gyroid", "infill"): (
        "a gyroid is like a suspension bridge in 3D: curved surfaces carry load "
        "along their length instead of through sharp joints"
    ),
    ("planetary", "sun gear"): (
        "a planetary gearset is like three horses pulling one cart: the load "
        "splits across the team"
    ),
    ("injection", "molding"): (
        "injection molding is like a waffle iron with a timer: fill the cavity, "
        "clamp, wait, pop the part out"
    ),
}

_ANIMATING_METHODS = frozenset(
    {
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.MOTION_VISUALIZATION,
        VisualTeachingMethod.STRESS_VISUALIZATION,
        VisualTeachingMethod.THERMAL_VISUALIZATION,
        VisualTeachingMethod.ASSEMBLY_SEQUENCE,
    }
)
_PARTIALLY_ANIMATING_METHODS = frozenset(
    {
        VisualTeachingMethod.EXPLODED_VIEW,
        VisualTeachingMethod.CROSS_SECTION,
        VisualTeachingMethod.TRANSPARENT_HOUSING,
        VisualTeachingMethod.TIMELINE,
    }
)

_STEP_CONCEPTS: dict[CognitiveStep, str] = {
    CognitiveStep.HOOK: "the viewer's attention",
    CognitiveStep.QUESTION: "the question the topic answers",
    CognitiveStep.PROBLEM: "the problem the topic solves",
    CognitiveStep.COMPARISON: "the options being compared",
    CognitiveStep.REVEAL: "the structure hidden from plain view",
    CognitiveStep.EXPLANATION: "the mechanism that makes it work",
    CognitiveStep.EVIDENCE: "the measurable phenomenon",
    CognitiveStep.FAILURE: "the failure mode being explained",
    CognitiveStep.ROOT_CAUSE: "the physical root cause",
    CognitiveStep.SOLUTION: "the design or process fix",
    CognitiveStep.MYTH: "the belief to be overturned",
    CognitiveStep.DEFINITION: "the precise meaning of the concept",
    CognitiveStep.EXAMPLE: "a concrete real-world case",
    CognitiveStep.DEMONSTRATION: "the behavior shown live",
    CognitiveStep.CONCLUSION: "the takeaway that stays",
}

_DIFFICULTY_MAP: dict[str, DifficultyLevel] = {
    "beginner": DifficultyLevel.BEGINNER,
    "intermediate": DifficultyLevel.INTERMEDIATE,
    "advanced": DifficultyLevel.ADVANCED,
}


class CognitiveFlowBuilder:
    """Deterministic learning-arc construction for a teaching strategy."""

    def sequence_for(
        self,
        strategy: TeachingStrategy,
    ) -> tuple[CognitiveStep, ...]:
        return _COGNITIVE_TEMPLATES.get(strategy, _FALLBACK_SEQUENCE)

    def attention_hook(self, strategy: TeachingStrategy) -> str:
        return _ATTENTION_HOOKS.get(strategy, _FALLBACK_HOOK)

    def retention(self, strategy: TeachingStrategy) -> tuple[RetentionMethod, str]:
        method = _RETENTION_METHODS.get(strategy, RetentionMethod.RECAP)
        return method, _RETENTION_RATIONALES[method]

    def failure_mode(self, strategy: TeachingStrategy) -> tuple[FailureMode, str]:
        mode = _FAILURE_MODES.get(
            strategy, FailureMode.ABSTRACT_CONCEPT_WITHOUT_ANCHOR
        )
        return mode, _FAILURE_RATIONALES[mode]

    def animation_requirement(
        self,
        methods: Sequence[VisualTeachingMethod],
    ) -> tuple[AnimationRequirement, str]:
        method_set = set(methods)
        if method_set & _ANIMATING_METHODS:
            return AnimationRequirement.YES, (
                "the chosen methods need motion to communicate"
            )
        if method_set & _PARTIALLY_ANIMATING_METHODS:
            return AnimationRequirement.PARTIAL, (
                "the chosen methods work as stills but gain from subtle motion"
            )
        return AnimationRequirement.NO, (
            "the chosen methods communicate fully as stills"
        )

    def build_knowledge_flow(
        self,
        strategy: TeachingStrategy,
        methods: Sequence[VisualTeachingMethod],
        knowledge: KnowledgeDirectorResult,
    ) -> tuple[list[KnowledgeFlowStep], str]:
        sequence = self.sequence_for(strategy)
        method_cycle = cycle(methods) if methods else cycle((None,))
        steps: list[KnowledgeFlowStep] = []
        for index, stage in enumerate(sequence, start=1):
            method = next(method_cycle)
            concept = _STEP_CONCEPTS[stage]
            if stage is CognitiveStep.CONCLUSION:
                concept = knowledge.critical_takeaway
            elif stage is CognitiveStep.FAILURE or stage is CognitiveStep.MYTH:
                concept = knowledge.common_misconception
            steps.append(
                KnowledgeFlowStep(
                    step=index,
                    stage=stage,
                    concept=concept,
                    visual_method=method,
                    justification=(
                        f"{stage.value} stage delivers '{concept}'"
                        + (f" through {method.value}" if method else "")
                    ),
                )
            )
        rationale = (
            f"the {strategy.value} strategy opens with a {sequence[0].value} "
            f"and closes with a {sequence[-1].value}"
        )
        return steps, rationale

    def difficulty(self, viewer_level: str) -> DifficultyLevel:
        return _DIFFICULTY_MAP.get(viewer_level.strip().lower(), DifficultyLevel.INTERMEDIATE)

    def mental_model(
        self,
        knowledge: KnowledgeDirectorResult,
    ) -> str:
        combined = " ".join(
            (knowledge.topic, knowledge.most_important_concept)
        ).lower()
        for tokens, model in _MENTAL_MODELS.items():
            if any(token in combined for token in tokens):
                return model
        return knowledge.critical_takeaway

    def comparison_strategy(
        self,
        knowledge: KnowledgeDirectorResult,
    ) -> str:
        combined = " ".join(
            (knowledge.topic, knowledge.most_important_concept)
        ).lower()
        for tokens, strategy in _COMPARISON_STRATEGIES.items():
            if any(token in combined for token in tokens):
                return strategy
        return "the topic's options against each other on the axes that matter"

    def analogy_strategy(
        self,
        knowledge: KnowledgeDirectorResult,
    ) -> str:
        combined = " ".join(
            (knowledge.topic, knowledge.most_important_concept)
        ).lower()
        for tokens, analogy in _ANALOGY_STRATEGIES.items():
            if any(token in combined for token in tokens):
                return analogy
        return "an everyday object that behaves the same way"