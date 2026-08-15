"""Application configuration loaded from environment, .env, and overrides.

The engine reads settings from environment variables (``PR1ME_*``), an optional
dotenv file, or explicit override objects supplied by callers (n8n, CLI, tests).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Engine-wide settings."""

    model_config = SettingsConfigDict(
        env_prefix="PR1ME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: Root directory of the repository that contains prompts/, config/, output/.
    repo_root: Path = Field(default_factory=lambda: _REPO_ROOT)

    #: Directory containing the stage prompt markdown files.
    prompts_dir: Path = Field(default_factory=lambda: _REPO_ROOT / "prompts")

    #: Workspace root for job artifacts. Stages exchange JSON files here.
    work_dir: Path = Field(default_factory=lambda: _REPO_ROOT / "output")

    #: Temporary scratch space for a single run.
    temp_dir: Path = Field(default_factory=lambda: _REPO_ROOT / "temp")

    #: Local asset workspace (b-roll, music, fonts, logo).
    assets_dir: Path = Field(default_factory=lambda: _REPO_ROOT / "assets")

    #: Structured log level.
    log_level: str = "INFO"

    #: Emit JSON logs.
    log_json: bool = True

    #: Default AI provider id resolved from the provider registry.
    provider: str = "ollama"

    #: Default target resolution for Shorts deliverables.
    target_width: int = 1080
    target_height: int = 1920

    #: Master timeline frame rate (frames per second) used by assembly.
    target_fps: int = Field(default=30, ge=1, le=240)

    #: Default Shorts duration budget in seconds (PIPELINE_SPEC).
    target_max_duration_seconds: float = 45.0
    target_min_duration_seconds: float = 35.0

    #: Optional timeline padding around the narration, in seconds. The final
    #: video duration is derived as ``narration + intro + outro``; both default
    #: to zero so the deliverable matches the narration length exactly unless
    #: the operator opts into a longer hold.
    intro_padding_seconds: float = Field(default=0.0, ge=0.0, le=30.0)
    outro_padding_seconds: float = Field(default=0.0, ge=0.0, le=30.0)

    #: Feature flag: render the legacy single-prompt path (``build_positive_prompt``
    #: over the visual plan) instead of the validated Visual Architecture payloads.
    #: The flag exists only for fallback/rollback; the active pipeline always uses
    #: the Workflow Builder payloads when available.
    use_legacy_image_prompts: bool = False

    #: Hard gate for the Visual Architecture chain: when enabled, an LLM output
    #: that violates a stage contract (or fails a content predicate) raises
    #: instead of falling back to the deterministic core.
    visual_architecture_strict: bool = False

    #: Enable the Image Critic quality gate after every render. A render below
    #: the threshold is regenerated with targeted corrections.
    image_critic_enabled: bool = True

    #: Image Critic quality bar: a render below this score is regenerated.
    image_critic_threshold: int = Field(default=90, ge=1, le=100)

    #: Regeneration budget for a failed render (thumbnail shots may render up
    #: to ``image_critic_thumbnail_candidates`` candidates instead).
    image_critic_max_attempts: int = Field(default=2, ge=1, le=5)

    #: Number of thumbnail candidates rendered for the thumbnail shot; each is
    #: critiqued and the strongest one is kept.
    image_critic_thumbnail_candidates: int = Field(default=3, ge=1, le=6)

    #: Hard gate for the Image Critic: when enabled and the regeneration budget
    #: is exhausted below the threshold, the stage fails. When disabled, the
    #: best-scoring render is accepted and the gate failure is recorded in the
    #: report.
    image_critic_strict: bool = False

    @property
    def run_dir(self) -> Path:
        return self.work_dir

    def ensure_dirs(self) -> None:
        """Create the workspace directories that the engine depends on."""
        for path in (self.prompts_dir, self.work_dir, self.temp_dir, self.assets_dir):
            path.mkdir(parents=True, exist_ok=True)