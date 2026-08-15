"""Optimization engine: iterate until the plan is predicted to pass.

One optimizer pass fires every applicable rule. The engine then simulates
the projected scores and runs further passes against them, so a plan that
cannot reach PASS in one round still gets the maximum deterministic set of
actions. Rounds are cheap: fired actions are deduplicated by (check,
instruction), so the loop terminates at MAX_ROUNDS or earlier and is
deterministic end to end.
"""

from __future__ import annotations

from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.image_qa.qa_models import ImageQualityReport
from knowledge.render_optimizer.optimization_models import OptimizedRenderPlan
from knowledge.render_optimizer.optimization_rules import SCORE_FIELDS
from knowledge.render_optimizer.optimizer import RenderOptimizer
from knowledge.visual_intelligence.storyboard import StoryboardScene

MAX_ROUNDS = 3


class OptimizationEngine:
    """Run the optimizer, simulating score gains until predicted pass."""

    def __init__(self, optimizer: RenderOptimizer | None = None) -> None:
        self._optimizer = optimizer or RenderOptimizer()

    def optimize(
        self,
        report: ImageQualityReport,
        *,
        scene: StoryboardScene | None = None,
        compiled_prompt: CompiledPrompt | None = None,
        max_rounds: int = MAX_ROUNDS,
    ) -> OptimizedRenderPlan:
        """Return the cumulative plan for the report.

        Deterministic: same inputs, same rounds, same plan. The number of
        rounds actually run is exposed on the plan through its action count
        and rationale; rounds beyond the first only add actions that were
        not already granted.
        """
        scores = {field: getattr(report, field) for field in SCORE_FIELDS}
        applied: list[tuple[str, str]] = []
        actions: list = []

        for _ in range(max(1, max_rounds)):
            new_actions = self._optimizer._collect_actions(scores, report.issues, applied)
            if not new_actions:
                break
            applied.extend((a.check.value, a.instruction) for a in new_actions)
            actions.extend(new_actions)
            projected = self._optimizer._project(scores, actions)
            if projected.predicted_pass:
                break

        return self._optimizer._assemble(
            report.topic,
            report.scene_id,
            scores,
            actions,
            scene=scene,
            compiled_prompt=compiled_prompt,
        )