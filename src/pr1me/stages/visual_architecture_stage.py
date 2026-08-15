"""Visual Architecture stage.

Runs the nine-engine Visual Intelligence chain as one auditable pipeline step:

    Knowledge Extractor -> Visual Analyzer -> Director AI -> Scene Planner
    -> Shot Planner -> Visual Director -> Consistency Engine
    -> Prompt Composer -> Prompt Validator

The stage consumes the approved narration plus the fact-check verdict and
corrections, runs :class:`~pr1me.visual_architecture.VisualArchitecture`, and
returns the full :class:`VisualIntelligenceOutput`. Every engine of the
architecture is wired here: KnowledgeExtractor, VisualAnalyzer, Director,
ScenePlanner, ShotPlanner, VisualDirector, ConsistencyEngine, PromptComposer,
and PromptValidator. LLM-backed engines fall back to their deterministic core
when the provider is missing or the model reply violates the contract, unless
``visual_architecture_strict`` is enabled.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from pr1me.core.base_stage import BaseStage
from pr1me.models.common import ScriptCorrections
from pr1me.models.contracts.base import StageInput
from pr1me.visual_architecture import (
    VisualArchitecture,
    VisualArchitectureInput,
    VisualContext,
    VisualIntelligenceOutput,
)

__all__ = ["VisualArchitectureStage", "VisualArchitectureStageInput"]


class VisualArchitectureStageInput(StageInput):
    """Stage input: the approved narration plus the fact-check verdict.

    The runner feeds the flattened outputs of the topic, script, and fact-check
    stages; the board consumes only the fields the architecture needs.
    """

    model_config = ConfigDict(extra="ignore")

    topic: str | None = Field(default=None, min_length=1)
    hook: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    practical_insight: str = Field(..., min_length=1)
    ending: str = Field(..., min_length=1)
    word_count: int | None = Field(default=None, ge=1, le=120)
    verdict: str | None = Field(default=None)
    corrections: ScriptCorrections = Field(default_factory=ScriptCorrections)
    factual_context: str | None = Field(default=None)


class VisualArchitectureStage(BaseStage[VisualArchitectureStageInput, VisualIntelligenceOutput]):
    """Runs the full Visual Architecture chain on the approved narration."""

    stage_id = "visual_architecture"
    name = "Visual Architecture"
    description = (
        "Runs knowledge extraction, scene/shot planning, direction, consistency, "
        "prompt composition, and validation."
    )
    version = "1.0.0"
    depends_on = ("topic", "script", "fact_check")
    input_model = VisualArchitectureStageInput
    output_model = VisualIntelligenceOutput

    async def execute(self, payload: VisualArchitectureStageInput) -> VisualIntelligenceOutput:
        settings = self.context.settings
        architecture = VisualArchitecture(
            VisualContext(
                provider=self.context.provider,
                strict=settings.visual_architecture_strict,
                target_width=settings.target_width,
                target_height=settings.target_height,
            )
        )
        return await architecture.run(self._build_input(payload))

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _build_input(payload: VisualArchitectureStageInput) -> VisualArchitectureInput:
        values: dict[str, Any] = dict(payload.model_dump())
        if not values.get("topic"):
            values["topic"] = values["hook"]
        return VisualArchitectureInput(**values)
