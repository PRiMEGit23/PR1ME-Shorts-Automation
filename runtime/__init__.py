"""Phase 6 + 7 + 8 + 10 runtime: closed-loop generation and the pipeline.

Phase 6 wires the knowledge subsystems (Educational Director, Visual
Intelligence, Storyboard, Prompt Compiler, Image QA, Render Optimizer) into
a deterministic render -> QA -> optimize loop with retry budget,
duplicate-render guard, content cache, attempt artifact storage, and
replayable history.

Phase 7 wires the thirteen mission stages (knowledge load -> educational
director -> visual intelligence -> prompt compiler -> workflow builder ->
render loop -> voice -> subtitles -> video assembly -> video render ->
thumbnail -> metadata -> publisher) into one orchestratable pipeline with
content fingerprints, checkpoints, resume, structured events, artifacts, and
an execution report. Same row + same seed + same run directory reproduces
the same sequence; no LLM calls anywhere.

Phase 8 inserts the AI Director (the deterministic creative decision
engine) between the Educational Director and Visual Intelligence, so the
storyboard is directed from a full creative brief instead of fixed
heuristics - fourteen stages in total, still fully deterministic.

Phase 10 inserts the Model Director between Visual Intelligence and the
Prompt Compiler: every scene's workflow compiles from a compiled backend
profile (ModelProfile) chosen deterministically across the model registry,
compiled by backend adapters - fifteen stages in total, still fully
deterministic, with deterministic model switching on repeated QA failure.
"""

from runtime.artifact_store import ArtifactRecord, ArtifactStore
from runtime.cache import CachedRender, RenderCache
from runtime.checkpoint import CheckpointStore, StageCheckpoint
from runtime.events import EventSink, PipelineEvent, PipelineEventType
from runtime.fingerprint import artifact_version, canonical_json, fingerprint, stage_fingerprint
from runtime.history import (
    OptimizationActionPoint,
    PromptEvolution,
    QAScorePoint,
    RenderHistory,
    WorkflowEvolution,
)
from runtime.models import (
    DEFAULT_MAX_ATTEMPTS,
    RUNTIME_VERSION,
    WORKFLOW_VERSION,
    AttemptStatus,
    RenderAttempt,
    RenderRequest,
    RenderResult,
    RenderSessionResult,
    SessionConfig,
    attempt_dir,
    fingerprint_of,
    topic_slug,
)
from runtime.pipeline import PIPELINE_VERSION, STAGE_ORDER, PipelineResult, ProductionPipeline
from runtime.pipeline_context import (
    GPUProbe,
    MemoryProbe,
    NoopGPUProbe,
    NoopMemoryProbe,
    PipelineContext,
)
from runtime.pipeline_stages import (
    AIDirectorStage,
    EducationalDirectorStage,
    KnowledgeLoadStage,
    MetadataGenerationStage,
    ModelDirectorStage,
    PromptCompilerStage,
    PublisherStage,
    RenderLoopStage,
    SubtitleGenerationStage,
    ThumbnailSelectionStage,
    VideoAssemblyStage,
    VideoRenderStage,
    VisualIntelligenceStage,
    VoiceGenerationStage,
    WorkflowBuilderStage,
    build_srt,
    compose_narration,
)
from runtime.render_loop import RenderLoop
from runtime.render_session import RenderSession
from runtime.renderer import Renderer, SimulatedRenderer, tiny_png
from runtime.replay import replay, verify_replay_identical
from runtime.report import ExecutionReport, StageReport
from runtime.resume import ResumePlanner, StageDecision, StagePlan
from runtime.retry_manager import RetryManager
from runtime.stage_runner import Stage, StageError, StageRunner, StageRunResult
from runtime.storyboard_builder import StoryboardBuilder
from runtime.workflow_builder import WorkflowBuilder

__all__ = [
    "AIDirectorStage",
    "ArtifactRecord",
    "ArtifactStore",
    "AttemptStatus",
    "CachedRender",
    "CheckpointStore",
    "DEFAULT_MAX_ATTEMPTS",
    "EducationalDirectorStage",
    "EventSink",
    "ExecutionReport",
    "GPUProbe",
    "KnowledgeLoadStage",
    "MemoryProbe",
    "MetadataGenerationStage",
    "ModelDirectorStage",
    "NoopGPUProbe",
    "NoopMemoryProbe",
    "OptimizationActionPoint",
    "PIPELINE_VERSION",
    "PipelineContext",
    "PipelineEvent",
    "PipelineEventType",
    "PipelineResult",
    "ProductionPipeline",
    "PromptCompilerStage",
    "PromptEvolution",
    "PublisherStage",
    "QAScorePoint",
    "RUNTIME_VERSION",
    "RenderAttempt",
    "RenderCache",
    "RenderHistory",
    "RenderLoop",
    "RenderLoopStage",
    "RenderRequest",
    "RenderResult",
    "RenderSession",
    "RenderSessionResult",
    "Renderer",
    "ResumePlanner",
    "RetryManager",
    "STAGE_ORDER",
    "SessionConfig",
    "SimulatedRenderer",
    "Stage",
    "StageCheckpoint",
    "StageDecision",
    "StageError",
    "StagePlan",
    "StageReport",
    "StageRunResult",
    "StageRunner",
    "StoryboardBuilder",
    "SubtitleGenerationStage",
    "ThumbnailSelectionStage",
    "VideoAssemblyStage",
    "VideoRenderStage",
    "VisualIntelligenceStage",
    "VoiceGenerationStage",
    "WORKFLOW_VERSION",
    "WorkflowBuilder",
    "WorkflowBuilderStage",
    "WorkflowEvolution",
    "artifact_version",
    "attempt_dir",
    "build_srt",
    "canonical_json",
    "compose_narration",
    "fingerprint",
    "fingerprint_of",
    "replay",
    "stage_fingerprint",
    "tiny_png",
    "topic_slug",
    "verify_replay_identical",
]