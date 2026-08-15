"""Visual Intelligence Architecture.

Replaces the single "topic -> prompt -> ComfyUI" hop with nine deterministic
stages that produce documentary-quality engineering imagery:

    1. Knowledge Extractor
    2. Engineering Visual Analyzer
    3. Director AI
    4. Scene Planner
    5. Shot Planner
    6. Visual Director
    7. Consistency Engine
    8. Prompt Composer
    9. Prompt Validator

Every stage is a standalone engine with a JSON contract; the
:class:`~pr1me.visual_architecture.orchestrator.VisualArchitecture` class
chains them in one call. LLM-backed stages use the existing
``BaseProvider`` interface (system prompt + structured JSON completion) and
fall back to their deterministic core when no provider is configured or the
response is invalid. The output prompts are packaged for the existing ComfyUI
workflow template, so nothing in the provider layer changes.

The Director AI sits between the analyzer and the scene planner and thinks
like a documentary director before any scene exists: what the viewer must see,
what must never appear, the teaching method, the attention flow, the visual
climax, the hero shot, and per-concept visual treatments. Downstream engines
pin those decisions onto scenes, shots, and prompts.

See ``docs/visual_architecture.md`` for the full pipeline, data flow, scoring
rubric, and extension guide.
"""

from __future__ import annotations

from pr1me.visual_architecture._common import VisualArchitectureError, VisualContext
from pr1me.visual_architecture.contracts import (
    ComfyUIReady,
    ComposedPrompt,
    ConsistencyOutput,
    DirectorOutput,
    KnowledgeOutput,
    PromptCompositionOutput,
    PromptValidationOutput,
    ScenePlanOutput,
    ShotPlanOutput,
    ValidatedPrompt,
    VisualArchitectureInput,
    VisualClimax,
    VisualIntelligenceOutput,
    VisualizationStrategyOutput,
    VisualStyleOutput,
    VisualTreatment,
)
from pr1me.visual_architecture.director import Director
from pr1me.visual_architecture.knowledge_extractor import KnowledgeExtractor
from pr1me.visual_architecture.orchestrator import VisualArchitecture
from pr1me.visual_architecture.prompt_composer import PromptComposer
from pr1me.visual_architecture.prompt_validator import PromptValidator
from pr1me.visual_architecture.scene_planner import ScenePlanner
from pr1me.visual_architecture.shot_planner import ShotPlanner
from pr1me.visual_architecture.visual_analyzer import VisualAnalyzer
from pr1me.visual_architecture.visual_director import VisualDirector

__all__ = [
    "ComfyUIReady",
    "ComposedPrompt",
    "ConsistencyOutput",
    "Director",
    "DirectorOutput",
    "KnowledgeExtractor",
    "KnowledgeOutput",
    "PromptComposer",
    "PromptCompositionOutput",
    "PromptValidationOutput",
    "PromptValidator",
    "ScenePlanner",
    "ScenePlanOutput",
    "ShotPlanner",
    "ShotPlanOutput",
    "ValidatedPrompt",
    "VisualAnalyzer",
    "VisualArchitecture",
    "VisualArchitectureError",
    "VisualArchitectureInput",
    "VisualClimax",
    "VisualContext",
    "VisualDirector",
    "VisualIntelligenceOutput",
    "VisualizationStrategyOutput",
    "VisualStyleOutput",
    "VisualTreatment",
]
