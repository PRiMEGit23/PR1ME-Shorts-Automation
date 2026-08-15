"""Asset Engine schemas: the studio's reusable asset record (Phase 12).

Every generated artifact becomes an indexed ``AssetRecord``: unique id,
content fingerprint, deterministic creation history, semantic fields
(topic, categories, objects, materials, processes, camera, lighting,
model, workflow version), measured quality, computed reuse score, visual
and semantic tags, usage, and genealogy (version, chain, parent,
supersession). No timestamps, no randomness: identical artifacts produce
identical assets, and every decision is a pure function of the records.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: The Asset Engine's own version stamp.
ASSET_ENGINE_VERSION = "12.0.0"

#: Every kind of artifact the studio indexes.
class AssetType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    VOICE = "voice"
    MUSIC = "music"
    SFX = "sfx"
    TRANSITION = "transition"
    BACKGROUND = "background"
    ENGINEERING_DIAGRAM = "engineering_diagram"
    CROSS_SECTION = "cross_section"
    ANIMATION = "animation"
    CAMERA_PATH = "camera_path"
    WORKFLOW_JSON = "workflow_json"
    PROMPT_PACK = "prompt_pack"
    QA_REPORT = "qa_report"
    OPTIMIZATION_HISTORY = "optimization_history"


class AssetStatus(StrEnum):
    ACTIVE = "active"
    OBSOLETE = "obsolete"
    MERGED = "merged"


class ReuseDecision(StrEnum):
    """What the selector decides for a candidate asset request."""

    REUSE = "reuse"
    IMPROVE = "improve"
    GENERATE = "generate"
    REPLACE = "replace"
    MERGE = "merge"


# ------------------------------------------------------------------ rules --

#: Reuse an existing asset only when its measured quality clears this bar.
REUSE_QUALITY_THRESHOLD = 75.0
#: Similarity at or above which a candidate is the same asset.
REUSE_SIMILARITY = 0.85
#: Similarity at or above which a candidate is improvable, not fresh.
IMPROVE_SIMILARITY = 0.60
#: Similarity at or above which two assets are duplicates of one another.
MERGE_SIMILARITY = 0.95
#: A newer version must beat an older one by at least this much QA to
#: propose replacement.
REPLACE_QUALITY_GAP = 2.0

#: Similarity weights: which semantic fields count how much (sum = 1.0).
SIMILARITY_WEIGHTS: dict[str, float] = {
    "topic": 0.15,
    "engineering_category": 0.10,
    "objects": 0.15,
    "materials": 0.15,
    "processes": 0.10,
    "camera": 0.10,
    "lighting": 0.05,
    "model": 0.05,
    "visual_tags": 0.10,
    "semantic_tags": 0.05,
}

#: Reuse score = quality share + usage share (both 0-100).
REUSE_SCORE_QUALITY_WEIGHT = 0.7
REUSE_SCORE_USAGE_WEIGHT = 0.3
#: Usage beyond this many recorded reuses stops adding to the reuse score.
REUSE_SCORE_USAGE_SATURATION = 5

#: The canonical query words for each asset type (rule-based parsing).
TYPE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "image": ("image", "render", "shot", "closeup", "close-up", "frame", "still"),
    "video": ("video", "clip", "footage"),
    "voice": ("voice", "narration", "vo", "voiceover"),
    "music": ("music", "score", "soundtrack", "bed"),
    "sfx": ("sfx", "sound effect", "sound effects", "whoosh"),
    "transition": ("transition", "wipe", "fade"),
    "background": ("background", "bg", "environment"),
    "engineering_diagram": ("diagram", "engineering diagram", "schematic", "exploded"),
    "cross_section": ("cross-section", "cross section", "crosssection", "section"),
    "animation": ("animation", "animate", "motion", "cam move"),
    "camera_path": ("camera path", "camera move", "camera"),
    "workflow_json": ("workflow", "workflow json", "graph"),
    "prompt_pack": ("prompt", "prompt pack", "prompts"),
    "qa_report": ("qa", "quality report", "qa report", "report"),
    "optimization_history": ("optimization", "optimization history", "history"),
}


# ------------------------------------------------------------------ models --


class CreationEvent(BaseModel):
    """One deterministic entry in an asset's creation history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Caller-supplied ordering (no timestamps: determinism).
    sequence: int = Field(ge=0)
    action: Literal["created", "improved", "reused", "merged"] = "created"
    reason: str = Field(min_length=1, max_length=200)
    run_id: str = Field(default="", max_length=120)
    scene_id: str = Field(default="", max_length=40)


class AssetRecord(BaseModel):
    """One indexed, reusable artifact - the studio's smallest unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Lowercase type, separator, and content hash - e.g. ``qa_report-<hash>``.
    asset_id: str = Field(pattern=r"^[a-z0-9\-_]+$")
    asset_type: AssetType
    #: Content hash: identical content always fingerprints identically.
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    #: Deterministic history: created -> improved -> reused (by sequence).
    creation_history: tuple[CreationEvent, ...] = Field(default_factory=tuple)

    #: Semantic identity (what this asset *is*).
    source_topic: str = Field(min_length=1, max_length=200)
    educational_category: str = Field(default="", max_length=120)
    engineering_category: str = Field(default="", max_length=120)
    objects: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
    materials: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
    processes: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
    camera: str = Field(default="", max_length=120)
    lighting: str = Field(default="", max_length=120)

    #: Production facts (what made it).
    model_used: str = Field(default="", max_length=40)
    workflow_version: str = Field(default="", max_length=40)

    #: Measured quality (winner QA) and the computed reuse score (0-100).
    quality_score: float = Field(ge=0.0, le=100.0)
    reuse_score: float = Field(ge=0.0, le=100.0)
    retention_prediction: float = Field(ge=0.0, le=100.0)
    optimization_count: int = Field(ge=0)

    #: Tags (deterministic labels, sorted).
    visual_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
    semantic_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=24)

    #: Usage (recorded by the reuse engine).
    usage_count: int = Field(ge=0)
    topics_using: tuple[str, ...] = Field(default_factory=tuple, max_length=24)

    #: Genealogy.
    status: AssetStatus = AssetStatus.ACTIVE
    version: int = Field(ge=1)
    chain_id: str = Field(min_length=1, max_length=120)
    parent_asset_id: str | None = None
    superseded_by: str | None = None


class AssetQuery(BaseModel):
    """A deterministic, rule-based search request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    topic: str = ""
    educational_category: str = ""
    engineering_category: str = ""
    asset_type: AssetType | None = None
    objects: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    materials: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    processes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    camera: str = ""
    lighting: str = ""
    model: str = ""
    visual_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    semantic_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    def is_empty(self) -> bool:
        """True when the query constrains nothing (matches everything)."""
        return not any(
            [
                self.topic,
                self.educational_category,
                self.engineering_category,
                self.asset_type is not None,
                self.objects,
                self.materials,
                self.processes,
                self.camera,
                self.lighting,
                self.model,
                self.visual_tags,
                self.semantic_tags,
            ]
        )


class SearchResult(BaseModel):
    """One deterministic search hit: asset, similarity, matched terms."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(min_length=1, max_length=120)
    similarity: float = Field(ge=0.0, le=1.0)
    matched_terms: tuple[str, ...] = Field(default_factory=tuple)


class SelectionDecision(BaseModel):
    """What the studio decides for one candidate asset request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: ReuseDecision
    #: The request being served (asset_id when re-serving an existing asset).
    candidate_key: str = Field(min_length=1, max_length=200)
    #: The chosen asset (reuse / improve / replace targets) or None.
    chosen_asset_id: str | None = None
    similarity: float = Field(ge=0.0, le=1.0)
    candidate_quality: float | None = Field(default=None, ge=0.0, le=100.0)
    rationale: str = Field(min_length=1, max_length=400)
    evidence: tuple[str, ...] = Field(default_factory=tuple)


class ReuseEvent(BaseModel):
    """One recorded reuse: who consumed which asset, when (by sequence)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=0)
    consumer: str = Field(min_length=1, max_length=80)
    asset_id: str = Field(min_length=1, max_length=120)
    decision: ReuseDecision
    rationale: str = Field(default="", max_length=400)
    topic: str = Field(default="", max_length=200)


class DependencyEdge(BaseModel):
    """One deterministic dependency between two assets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dependent: str = Field(min_length=1, max_length=120)
    dependency: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="uses", min_length=1, max_length=40)
    reason: str = Field(default="", max_length=200)
