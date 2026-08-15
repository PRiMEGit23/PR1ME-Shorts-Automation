"""Image QA schema: what is checked and what the report looks like.

The Image QA Engine answers one question: "was this generated image good
enough to accept?" It receives the EducationalPlan (how the topic is taught),
the VisualStoryboard (how the scene was directed), the CompiledPrompt (what
was asked), and GeneratedImageMetadata (what actually came back) - and
returns an ImageQualityReport.

Everything is deterministic: scores are computed from structured metadata
plus the plans, never from an LLM. The report carries the eight scores the
director needs, a PassFail verdict, the issues found, and deterministic
repair instructions (no automatic re-rendering: a human or a future repair
stage decides).

Check names mirror the 13 checks of the Phase 4 mission:
primary subject visibility, subject hierarchy, engineering accuracy, geometry
correctness, material correctness, camera suitability, lighting suitability,
composition quality, visual clutter, educational effectiveness, thumbnail
strength, scene consistency, prompt consistency.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

IMAGE_QA_VERSION = "1.0.0"

PASS_THRESHOLD = 75.0
FAIL_FLOOR = 50.0


class QACheck(StrEnum):
    """The thirteen checks every generated image must pass."""

    PRIMARY_SUBJECT_VISIBILITY = "primary subject visibility"
    SUBJECT_HIERARCHY = "subject hierarchy"
    ENGINEERING_ACCURACY = "engineering accuracy"
    GEOMETRY_CORRECTNESS = "geometry correctness"
    MATERIAL_CORRECTNESS = "material correctness"
    CAMERA_SUITABILITY = "camera suitability"
    LIGHTING_SUITABILITY = "lighting suitability"
    COMPOSITION_QUALITY = "composition quality"
    VISUAL_CLUTTER = "visual clutter"
    EDUCATIONAL_EFFECTIVENESS = "educational effectiveness"
    THUMBNAIL_STRENGTH = "thumbnail strength"
    SCENE_CONSISTENCY = "scene consistency"
    PROMPT_CONSISTENCY = "prompt consistency"


class IssueSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class QAIssue(BaseModel):
    """One finding: which check, how bad, and what the image did wrong."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check: QACheck
    severity: IssueSeverity
    message: str = Field(min_length=1, max_length=400)


class PassFail(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class GeneratedImageMetadata(BaseModel):
    """What a vision pipeline observes in a rendered image.

    This is the only input that comes from the actual render. In this phase
    it is supplied by the caller (a future runtime will fill it from a
    detector); every score below is derived from these facts deterministically.
    All quality fields are 0..1; 1 is always the ideal.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")

    # primary subject visibility
    subject_present: bool = True
    subject_prominence: float = Field(default=1.0, ge=0.0, le=1.0)
    subject_occluded: bool = False

    # subject hierarchy
    hierarchy_clear: bool = True

    # engineering accuracy
    engineering_accuracy: float = Field(default=1.0, ge=0.0, le=1.0)

    # geometry correctness
    geometry_correct: bool = True
    geometry_quality: float = Field(default=1.0, ge=0.0, le=1.0)

    # material correctness
    material_correct: bool = True
    material_quality: float = Field(default=1.0, ge=0.0, le=1.0)

    # camera suitability
    camera_distance_matches: bool = True
    camera_angle_matches: bool = True
    lens_matches: bool = True

    # lighting suitability
    lighting_direction_matches: bool = True
    lighting_style_matches: bool = True

    # composition quality
    composition_rule_matches: bool = True
    composition_quality: float = Field(default=1.0, ge=0.0, le=1.0)

    # visual clutter
    clutter_level: float = Field(default=0.0, ge=0.0, le=1.0)

    # visual clarity
    visual_clarity: float = Field(default=1.0, ge=0.0, le=1.0)

    # educational effectiveness
    method_implemented: bool = True
    annotations_present: bool = True
    annotation_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    comparison_axis_present: bool = True

    # thumbnail strength
    thumbnail_contrast: float = Field(default=1.0, ge=0.0, le=1.0)
    thumbnail_focus: float = Field(default=1.0, ge=0.0, le=1.0)
    thumbnail_negative_space: bool = True

    # consistency
    scene_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    consistency_violations: list[str] = Field(default_factory=list, max_length=12)
    prompt_term_mismatches: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def _clutter_limits_composition(self) -> GeneratedImageMetadata:
        if self.clutter_level > 0.6 and self.composition_quality > 0.8:
            raise ValueError(
                f"clutter_level {self.clutter_level} contradicts a pristine "
                f"composition_quality {self.composition_quality}"
            )
        return self


class CriticVerdict(BaseModel):
    """What one critic concluded about the image."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check: QACheck
    score: float = Field(ge=0.0, le=100.0)
    issues: list[QAIssue] = Field(default_factory=list, max_length=12)
    rationale: str = Field(min_length=1, max_length=500)


class ImageQualityReport(BaseModel):
    """The complete QA verdict for one generated image."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = IMAGE_QA_VERSION
    topic: str = Field(min_length=1, max_length=200)
    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    overall_score: float = Field(ge=0.0, le=100.0)
    engineering_score: float = Field(ge=0.0, le=100.0)
    educational_score: float = Field(ge=0.0, le=100.0)
    composition_score: float = Field(ge=0.0, le=100.0)
    subject_hierarchy_score: float = Field(ge=0.0, le=100.0)
    visual_clarity_score: float = Field(ge=0.0, le=100.0)
    thumbnail_score: float = Field(ge=0.0, le=100.0)
    consistency_score: float = Field(ge=0.0, le=100.0)
    pass_fail: PassFail
    issues: list[QAIssue] = Field(default_factory=list, max_length=24)
    repair_suggestions: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def _scores_must_be_consistent_with_pass_fail(self) -> ImageQualityReport:
        sub_scores = (
            self.engineering_score,
            self.educational_score,
            self.composition_score,
            self.subject_hierarchy_score,
            self.visual_clarity_score,
            self.thumbnail_score,
            self.consistency_score,
        )
        any_sub_failed = any(score < FAIL_FLOOR for score in sub_scores)
        any_critical = any(issue.severity is IssueSeverity.CRITICAL for issue in self.issues)
        passed = self.pass_fail is PassFail.PASS
        if passed and (
            self.overall_score < PASS_THRESHOLD or any_sub_failed or any_critical
        ):
            raise ValueError(
                f"pass_fail=pass requires overall_score >= {PASS_THRESHOLD}, no "
                f"sub-score below {FAIL_FLOOR}, and no critical issue; got "
                f"overall={self.overall_score} sub_failed={any_sub_failed} "
                f"critical={any_critical}"
            )
        if not passed and not (
            self.overall_score < PASS_THRESHOLD or any_sub_failed or any_critical
        ):
            raise ValueError(
                f"pass_fail=fail requires overall_score < {PASS_THRESHOLD}, a "
                f"sub-score below {FAIL_FLOOR}, or a critical issue; got "
                f"overall={self.overall_score}"
            )
        return self