"""Prompt Compiler: converts model-agnostic VisualArchitecture specs into
model-specific prompts. Deterministic, versioned, and free of LLM calls."""

from knowledge.compiler.compilers import sdxl  # noqa: F401  (registers the SDXL compiler)
from knowledge.compiler.model_profiles import PROFILES, ModelProfile, PromptStyle
from knowledge.compiler.prompt_compiler import (
    COMPILER_VERSION,
    CompiledPrompt,
    CompiledRow,
    CompileError,
    compile_for_model,
    compile_for_storyboard,
)

__all__ = [
    "COMPILER_VERSION",
    "PROFILES",
    "CompiledPrompt",
    "CompiledRow",
    "CompileError",
    "ModelProfile",
    "PromptStyle",
    "compile_for_model",
    "compile_for_storyboard",
]
