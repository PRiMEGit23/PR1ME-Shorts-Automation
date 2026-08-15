"""Educational Director: the creative brain above the Visual Intelligence engine.

Given a curated Knowledge Base row, the director answers one question first:
"What is the most effective visual strategy for teaching this concept in under
30 seconds?" It consults the Knowledge Director (what matters), the strategy
selector (how people learn this best), the visual method selector (what to
show), and the cognitive flow builder (in what order) - then assembles the
full EducationalPlan. No scene plans, no prompts, no rendering decisions:
those belong to the subsystems below, which this module never touches.

Fully deterministic and self-contained. Nothing in the runtime, the Prompt
Compiler, Visual Intelligence, or the Knowledge Base is modified.
"""

from __future__ import annotations

from knowledge.educational_director.cognitive_flow import CognitiveFlowBuilder
from knowledge.educational_director.educational_models import (
    CoreMisconception,
    EducationalPlan,
    KnowledgeDirectorResult,
)
from knowledge.educational_director.knowledge_director import KnowledgeDirector
from knowledge.educational_director.learning_objectives import derive_learning_objective
from knowledge.educational_director.strategy_selector import StrategySelector
from knowledge.educational_director.visual_method_selector import VisualMethodSelector
from knowledge.visual_intelligence.visual_intelligence import KnowledgeBaseRow


class EducationalDirector:
    """Orchestrates the full educational decision pipeline for one row."""

    def __init__(
        self,
        *,
        knowledge_director: KnowledgeDirector | None = None,
        strategy_selector: StrategySelector | None = None,
        visual_method_selector: VisualMethodSelector | None = None,
        cognitive_flow_builder: CognitiveFlowBuilder | None = None,
    ) -> None:
        self._knowledge = knowledge_director or KnowledgeDirector()
        self._strategy = strategy_selector or StrategySelector()
        self._methods = visual_method_selector or VisualMethodSelector()
        self._flow = cognitive_flow_builder or CognitiveFlowBuilder()

    def direct(
        self,
        row: KnowledgeBaseRow,
        *,
        csv_row: dict[str, str] | None = None,
    ) -> EducationalPlan:
        """Produce the EducationalPlan for one curated Knowledge Base row."""
        knowledge = self._knowledge.analyze(row, csv_row=csv_row)
        strategy, strategy_rationale = self._strategy.select(row, csv_row=csv_row)
        methods, method_rationale = self._methods.select(strategy, row)
        objective = derive_learning_objective(
            curator_objective=knowledge.primary_objective,
            concept=knowledge.most_important_concept,
            strategy=strategy,
        )
        sequence = self._flow.sequence_for(strategy)
        flow, flow_rationale = self._flow.build_knowledge_flow(
            strategy, methods, knowledge
        )
        retention, retention_rationale = self._flow.retention(strategy)
        failure_mode, failure_rationale = self._flow.failure_mode(strategy)
        animation, animation_rationale = self._flow.animation_requirement(methods)
        misconception = CoreMisconception(
            statement=knowledge.common_misconception,
            why_common=self._why_common(knowledge),
            why_dangerous=(
                "a viewer acting on it chooses the wrong option exactly when the "
                "choice matters"
            ),
            refutation=knowledge.critical_takeaway,
        )

        return EducationalPlan(
            topic=row.topic,
            learning_objective=objective,
            core_misconception=misconception,
            teaching_strategy=strategy,
            strategy_rationale=strategy_rationale,
            visual_teaching_method=methods,
            method_rationale=method_rationale,
            cognitive_sequence=list(sequence),
            cognitive_flow_rationale=flow_rationale,
            attention_hook=self._flow.attention_hook(strategy),
            knowledge_flow=flow,
            retention_method=retention,
            retention_rationale=retention_rationale,
            difficulty_level=self._flow.difficulty(row.viewer_level),
            expected_mental_model=self._flow.mental_model(knowledge),
            comparison_strategy=self._flow.comparison_strategy(knowledge),
            analogy_strategy=self._flow.analogy_strategy(knowledge),
            animation_requirement=animation,
            animation_rationale=animation_rationale,
            visualization_priority=methods,
            failure_mode=failure_mode,
            failure_mode_rationale=failure_rationale,
            final_takeaway=knowledge.critical_takeaway,
            prior_knowledge=knowledge.required_prior_knowledge,
        )

    def direct_from_csv(self, csv_row: dict[str, str]) -> EducationalPlan:
        """Convenience: build the plan straight from a build_knowledge_csv.py record."""
        row = KnowledgeBaseRow.from_csv_row(csv_row)
        return self.direct(row, csv_row=csv_row)

    @staticmethod
    def _why_common(knowledge: KnowledgeDirectorResult) -> str:
        lowered = knowledge.common_misconception.lower()
        rules: tuple[tuple[str, str], ...] = (
            ("strongest", "one property is assumed constant across every condition"),
            ("stronger", "one property is assumed constant across every condition"),
            ("weaker", "one property is assumed constant across every condition"),
            ("cheaper", "cost is assumed to scale linearly with part count"),
            ("space", "capability is assumed to scale with size"),
            ("always", "a single example is generalized to every situation"),
            ("everywhere", "a single example is generalized to every situation"),
        )
        for token, reason in rules:
            if token in lowered:
                return reason
        return "an everyday analogy is applied beyond its valid range"