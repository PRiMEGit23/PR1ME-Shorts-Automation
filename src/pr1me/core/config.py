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
    provider: str = "noop"

    #: Default target resolution for Shorts deliverables.
    target_width: int = 1080
    target_height: int = 1920

    #: Default Shorts duration budget in seconds (PIPELINE_SPEC).
    target_max_duration_seconds: float = 45.0
    target_min_duration_seconds: float = 35.0

    @property
    def run_dir(self) -> Path:
        return self.work_dir

    def ensure_dirs(self) -> None:
        """Create the workspace directories that the engine depends on."""
        for path in (self.prompts_dir, self.work_dir, self.temp_dir, self.assets_dir):
            path.mkdir(parents=True, exist_ok=True)