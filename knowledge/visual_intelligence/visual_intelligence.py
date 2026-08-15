"""Visual Intelligence Engine: from a Knowledge Base row to a VisualStoryboard.

The engine is the Phase 2 entry point. Given a VisualArchitecture V2
specification (and optionally the source Knowledge Base CSV row for topic
keywords and the engineering summary), it runs the ShotDirector and returns a
fully directed VisualStoryboard that the Prompt Compiler can compile directly.

The engine never reads or writes prompts, never calls a model, and never
modifies the Knowledge Base.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from knowledge.visual_architecture import VisualArchitecture
from knowledge.visual_intelligence.shot_director import ShotDirector
from knowledge.visual_intelligence.storyboard import VisualStoryboard
from knowledge.visual_intelligence.visual_goal import VisualGoal


def _parse_string_list(raw: str) -> list[str]:
    """Parse a CSV cell that holds a JSON array, with a lenient fallback."""
    value = raw.strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        import json

        try:
            parsed = json.loads(value)
            return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
    return [
        item.strip().strip("'\"")
        for item in value.strip("[]").split(",")
        if item.strip()
    ]


class KnowledgeBaseRow(BaseModel):
    """The fields of a V1 Knowledge Base CSV row the engine may consult.

    Only the fields the visual intelligence actually uses are modeled; the
    remaining CSV columns are ignored by construction (extra="ignore"), so the
    row loader stays forward compatible.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    topic: str = Field(min_length=1, max_length=200)
    category: str = Field(default="", max_length=120)
    subcategory: str = Field(default="", max_length=120)
    keywords: list[str] = Field(default_factory=list)
    search_intent: str = Field(default="", max_length=200)
    viewer_level: str = Field(default="", max_length=60)
    engineering_summary: str = Field(default="", max_length=4000)
    scene_count: int = Field(default=0, ge=0)
    materials: list[str] = Field(default_factory=list)
    environment: str = Field(default="", max_length=300)
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    hashtags: list[str] = Field(default_factory=list)

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> KnowledgeBaseRow:
        """Build a row from one CSV record (csv.DictReader output)."""
        keywords = _parse_string_list(row.get("keywords", ""))
        materials = _parse_string_list(row.get("materials", ""))
        hashtags = _parse_string_list(row.get("hashtags", ""))
        try:
            scene_count = int(row.get("scene_count", "0") or "0")
        except ValueError:
            scene_count = 0
        return cls(
            topic=row.get("topic", ""),
            category=row.get("category", ""),
            subcategory=row.get("subcategory", ""),
            keywords=keywords,
            search_intent=row.get("search_intent", ""),
            viewer_level=row.get("viewer_level", ""),
            engineering_summary=row.get("engineering_summary", ""),
            scene_count=scene_count,
            materials=materials,
            environment=row.get("environment", ""),
            title=row.get("title", ""),
            description=row.get("description", ""),
            hashtags=hashtags,
        )


class VisualIntelligenceEngine:
    """Deterministic storyboard planner; safe to instantiate once and reuse."""

    def __init__(self, director: ShotDirector | None = None) -> None:
        self._director = director or ShotDirector()

    @property
    def director(self) -> ShotDirector:
        return self._director

    def classify_goals(
        self,
        architecture: VisualArchitecture,
        *,
        keywords: Sequence[str] = (),
        summary: str = "",
    ) -> list[VisualGoal]:
        """Classify every scene's visual goal, with director-level dedupe."""
        return self._director.classify_goals(
            architecture, keywords=keywords, summary=summary
        )

    def plan_storyboard(
        self,
        architecture: VisualArchitecture,
        *,
        topic: str,
        keywords: Sequence[str] = (),
        summary: str = "",
    ) -> VisualStoryboard:
        """Direct a full VisualStoryboard from a VisualArchitecture spec."""
        return self._director.direct(
            architecture,
            topic=topic,
            keywords=keywords,
            summary=summary,
        )

    def build_storyboard(
        self,
        architecture: VisualArchitecture,
        row: KnowledgeBaseRow | dict[str, Any],
        *,
        topic: str | None = None,
    ) -> VisualStoryboard:
        """Direct a storyboard, pulling keywords and summary from a CSV row."""
        if isinstance(row, dict):
            row = KnowledgeBaseRow.from_csv_row(row)
        return self.plan_storyboard(
            architecture,
            topic=topic or row.topic,
            keywords=row.keywords,
            summary=row.engineering_summary,
        )