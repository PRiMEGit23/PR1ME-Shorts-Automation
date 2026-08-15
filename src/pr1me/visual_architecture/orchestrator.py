"""Visual Intelligence Architecture orchestrator.

Chains the nine stages into one auditable flow:

    Knowledge Extractor -> Visual Analyzer -> Director AI -> Scene Planner
    -> Shot Planner -> Visual Director -> Consistency Engine -> Prompt Composer
    -> Prompt Validator -> ComfyUI-ready prompts

Every stage is a standalone engine with its own contract; the orchestrator only
wires them and runs the validator's regeneration loop. The final output carries
``comfyui_ready`` entries whose variables match the existing
``workflows/comfyui.json`` placeholders, so the prompts can be handed straight
to :class:`~pr1me.providers.comfyui.ComfyUIProvider` with no provider change.
"""

from __future__ import annotations

from collections.abc import Mapping

from pr1me.visual_architecture._common import (
    VisualArchitectureError,
    VisualContext,
    make_logger,
)
from pr1me.visual_architecture.consistency_engine import ConsistencyEngine
from pr1me.visual_architecture.contracts import (
    ComfyUIReady,
    ConsistencyOutput,
    KnowledgeOutput,
    PromptCompositionOutput,
    ShotPlanOutput,
    ValidatedPrompt,
    VisualArchitectureInput,
    VisualIntelligenceOutput,
    VisualizationStrategyOutput,
    VisualStyleOutput,
)
from pr1me.visual_architecture.director import Director
from pr1me.visual_architecture.knowledge_extractor import KnowledgeExtractor
from pr1me.visual_architecture.prompt_composer import PromptComposer
from pr1me.visual_architecture.prompt_validator import PromptValidator
from pr1me.visual_architecture.scene_planner import ScenePlanner
from pr1me.visual_architecture.shot_planner import ShotPlanner
from pr1me.visual_architecture.visual_analyzer import VisualAnalyzer
from pr1me.visual_architecture.visual_director import VisualDirector

__all__ = ["VisualArchitecture"]

#: Fixed sampler policy matching the channel's reproducible seed policy.
_SEED_BASE = 424242
_SEED_STEP = 7919
_STEPS = 28
_CFG = 7.0
_SAMPLER = "euler_a"
_SCHEDULER = "karras"


class VisualArchitecture:
    """The nine-stage visual generation chain, runnable in one call."""

    def __init__(self, context: VisualContext | None = None) -> None:
        self._context = context or VisualContext()
        self._logger = make_logger("orchestrator")
        self.knowledge_extractor = KnowledgeExtractor(self._context)
        self.visual_analyzer = VisualAnalyzer(self._context)
        self.director = Director(self._context)
        self.scene_planner = ScenePlanner(self._context)
        self.shot_planner = ShotPlanner(self._context)
        self.visual_director = VisualDirector(self._context)
        self.consistency_engine = ConsistencyEngine(self._context)
        self.prompt_composer = PromptComposer(self._context)
        self.prompt_validator = PromptValidator(self._context)

    async def run(self, payload: VisualArchitectureInput) -> VisualIntelligenceOutput:
        """Execute the full chain and return the final auditable output."""
        self._logger.info(
            "event=visual_architecture.started",
            topic=payload.topic,
            strict=self._context.strict,
        )

        knowledge = await self.knowledge_extractor.run(payload)
        strategy = await self.visual_analyzer.run(knowledge)
        director = await self.director.run(knowledge, strategy)
        scene_plan = await self.scene_planner.run(payload, knowledge, director)
        shot_plan = await self.shot_planner.run(scene_plan, director)
        visual_style = await self.visual_director.run(shot_plan, strategy)
        consistency = await self.consistency_engine.run(
            knowledge=knowledge,
            scene_plan=scene_plan,
            shot_plan=shot_plan,
            visual_style=visual_style,
            strategy=strategy,
        )

        composition = await self.prompt_composer.compose_all(
            shot_plan=shot_plan,
            knowledge=knowledge,
            strategy=strategy,
            visual_style=visual_style,
            consistency=consistency,
        )
        validation, final_composition = await self.prompt_validator.run(
            composition,
            knowledge=knowledge,
            consistency=consistency,
            composer=lambda repairs: self._regenerate(
                repairs,
                shot_plan,
                knowledge,
                strategy,
                visual_style,
                consistency,
            ),
            max_attempts=max(1, self._context.regeneration_attempts),
        )
        if validation.status == "rejected" and self._context.strict:
            raise VisualArchitectureError(
                "prompt validation could not reach the 95-point bar",
                detail={"scores": [result.score for result in validation.prompts]},
            )

        comfyui_ready = [
            _package_for_comfyui(
                result,
                index=index,
                width=self._context.target_width,
                height=self._context.target_height,
            )
            for index, result in enumerate(validation.prompts)
        ]

        output = VisualIntelligenceOutput(
            knowledge=knowledge,
            strategy=strategy,
            director=director,
            scene_plan=scene_plan,
            shot_plan=shot_plan,
            visual_style=visual_style,
            consistency=consistency,
            composition=final_composition,
            validation=validation,
            comfyui_ready=comfyui_ready,
        )
        self._logger.info(
            "event=visual_architecture.completed",
            n_scenes=len(scene_plan.scenes),
            n_shots=len(shot_plan.shots),
            n_prompts=len(comfyui_ready),
            validation_status=validation.status,
        )
        return output

    async def _regenerate(
        self,
        repairs: Mapping[int, list[str]],
        shot_plan: ShotPlanOutput,
        knowledge: KnowledgeOutput,
        strategy: VisualizationStrategyOutput,
        visual_style: VisualStyleOutput,
        consistency: ConsistencyOutput,
    ) -> PromptCompositionOutput:
        return await self.prompt_composer.compose_all(
            shot_plan=shot_plan,
            knowledge=knowledge,
            strategy=strategy,
            visual_style=visual_style,
            consistency=consistency,
            repairs=dict(repairs),
        )


def _package_for_comfyui(
    result: ValidatedPrompt, *, index: int, width: int, height: int
) -> ComfyUIReady:
    """Wrap one validated prompt into the workflow's exact variable set."""
    seed = (_SEED_BASE + (index + 1) * _SEED_STEP) % (2**63 - 1)
    return ComfyUIReady(
        shot_id=result.shot_id,
        positive_prompt=result.positive_prompt,
        negative_prompt=result.negative_prompt,
        width=width,
        height=height,
        seed=seed,
        steps=_STEPS,
        cfg=_CFG,
        sampler=_SAMPLER,
        scheduler=_SCHEDULER,
    )
