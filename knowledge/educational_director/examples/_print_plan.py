"""Shared plan printing for the Educational Director examples."""

from __future__ import annotations

from knowledge.educational_director.educational_models import EducationalPlan


def print_plan(plan: EducationalPlan) -> None:
    """Render one EducationalPlan as readable terminal output."""
    print(f"Topic                  : {plan.topic}")
    print(f"Teaching strategy      : {plan.teaching_strategy.value}")
    print(f"  rationale            : {plan.strategy_rationale}")
    print(f"Difficulty level       : {plan.difficulty_level.value}")
    print(f"Learning objective     : {plan.learning_objective.statement}")
    print(f"  verbs                : {', '.join(plan.learning_objective.verbs)}")
    print(f"  success criteria     : {plan.learning_objective.success_criteria}")
    print(f"Core misconception     : {plan.core_misconception.statement}")
    print(f"  why common           : {plan.core_misconception.why_common}")
    print(f"  why dangerous        : {plan.core_misconception.why_dangerous}")
    print(f"  refutation           : {plan.core_misconception.refutation}")
    print(f"Visual methods         : {', '.join(m.value for m in plan.visual_teaching_method)}")
    print(f"  rationale            : {plan.method_rationale}")
    print(f"Visualization priority : {', '.join(m.value for m in plan.visualization_priority)}")
    print(f"Cognitive sequence     : {' > '.join(s.value for s in plan.cognitive_sequence)}")
    print(f"  rationale            : {plan.cognitive_flow_rationale}")
    print(f"Attention hook         : {plan.attention_hook}")
    print("Knowledge flow:")
    for step in plan.knowledge_flow:
        method = step.visual_method.value if step.visual_method else "-"
        print(
            f"  {step.step}. {step.stage.value:<13} via {method:<20} | "
            f"{step.concept}"
        )
    print(f"Retention method       : {plan.retention_method.value}")
    print(f"  rationale            : {plan.retention_rationale}")
    print(f"Expected mental model  : {plan.expected_mental_model}")
    print(f"Comparison strategy    : {plan.comparison_strategy}")
    print(f"Analogy strategy       : {plan.analogy_strategy}")
    print(f"Animation requirement  : {plan.animation_requirement.value}")
    print(f"  rationale            : {plan.animation_rationale}")
    print(f"Failure mode           : {plan.failure_mode.value}")
    print(f"  rationale            : {plan.failure_mode_rationale}")
    print(f"Final takeaway         : {plan.final_takeaway}")
    print(f"Prior knowledge        : {', '.join(plan.prior_knowledge)}")