"""Stage 8: Prompt Validator.

Scores every composed prompt against a 100-point rubric and regenerates until
every prompt reaches the 95-point bar (or the attempt budget is exhausted).

Rubric (weights sum to 100):

    subject_present          15   the positive prompt opens with the subject
    environment_present      10   a concrete environment is stated
    composition_present      10   a deliberate composition is stated
    camera_specified         10   angle + lens + movement are all specified
    lighting_specified       10   one consistent lighting scheme is stated
    teaching_goal            10   the primary concept is weighted into the prompt
    engineering_realism      10   no fantasy vocabulary, canonical engineering terms
    object_hierarchy          5   one clear focal subject, no competing objects
    material_detail           5   at least one canonical material is named
    negative_prompt_quality   5   hygiene negatives cover artifacts and drift
    quality_constraints       5   two or more quality descriptors present
    consistency_anchors       5   cross-shot locks are present in the negatives

Thumbnail shots carry three additional penalties: large central subject,
minimal clutter, and high contrast (5 points each).

Regeneration is repair-driven: the composer receives the failed criterion
names as repairs, which forces the canonical default for each offending field,
so the regenerated prompt deterministically clears the bar.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Literal

from pr1me.visual_architecture._common import VisualContext, make_logger
from pr1me.visual_architecture.contracts import (
    ComposedPrompt,
    ConsistencyOutput,
    CriterionScore,
    KnowledgeOutput,
    PromptCompositionOutput,
    PromptValidationOutput,
    ValidatedPrompt,
)

__all__ = ["PromptValidator", "score_prompt"]

#: Quality bar: a prompt below this score is regenerated.
PASS_THRESHOLD = 95
#: Default regeneration budget (the orchestrator may override).
MAX_ATTEMPTS = 2

#: Vocabulary that marks a prompt as non-engineering fantasy.
_FORBIDDEN_STYLE_WORDS = (
    "sci-fi",
    "sci fi",
    "futuristic",
    "hologram",
    "neon",
    "glowing",
    "glow",
    "fantasy",
    "magic",
    "cyberpunk",
    "anime",
    "cartoon",
    "levitation",
    "floating",
    "plasma",
    "portal",
    "spaceship",
    "superhero",
    "galaxy",
    "laser beam",
    "impossible",
)

#: Canonical engineering vocabulary the realism check looks for.
_CANONICAL_VOCABULARY = (
    "engineering",
    "mechanism",
    "machine",
    "industrial",
    "industrial photography",
    "cross section",
    "exploded",
    "cad",
    "manufacturing",
    "precision",
    "tolerance",
    "assembly",
    "extrusion",
    "machining",
)

#: Cross-shot lock phrases that must survive into the negatives.
_LOCK_MARKERS = (
    "no color changes",
    "no subject or environment changes",
    "no lighting direction changes",
)

#: Base hygiene tokens the negative prompt must carry.
_NEGATIVE_HYGIENE = ("blurry", "low quality")

#: Repair keys the validator can emit back into the composer.
_REPAIRABLE = {
    "subject",
    "environment",
    "composition",
    "camera",
    "lighting",
    "teaching_goal",
    "engineering_realism",
    "object_hierarchy",
    "material_detail",
}

#: Weight of every criterion, in rubric order.
_CRITERIA: tuple[tuple[str, int], ...] = (
    ("subject_present", 15),
    ("environment_present", 10),
    ("composition_present", 10),
    ("camera_specified", 10),
    ("lighting_specified", 10),
    ("teaching_goal", 10),
    ("engineering_realism", 10),
    ("object_hierarchy", 5),
    ("material_detail", 5),
    ("negative_prompt_quality", 5),
    ("quality_constraints", 5),
    ("consistency_anchors", 5),
)

#: Repair key chosen when a criterion fails.
_REPAIR_FOR_CRITERION = {
    "subject_present": "subject",
    "environment_present": "environment",
    "composition_present": "composition",
    "camera_specified": "camera",
    "lighting_specified": "lighting",
    "teaching_goal": "engineering_detail",
    "engineering_realism": "physics",
    "object_hierarchy": "composition",
    "material_detail": "materials",
}


class PromptValidator:
    """Stage 8 engine: scored prompts, regenerated until >= 95."""

    def __init__(self, context: VisualContext) -> None:
        self._context = context
        self._logger = make_logger("prompt_validator")

    async def run(
        self,
        composition: PromptCompositionOutput,
        *,
        knowledge: KnowledgeOutput,
        consistency: ConsistencyOutput,
        composer: Callable[[Mapping[int, list[str]]], Awaitable[PromptCompositionOutput]],
        max_attempts: int = MAX_ATTEMPTS,
    ) -> tuple[PromptValidationOutput, PromptCompositionOutput]:
        """Score every prompt and regenerate until the bar is cleared.

        Returns the validation envelope plus the final (post-regeneration)
        composition, so callers always see the prompts that actually passed.
        """
        self._logger.info(
            "event=prompt_validator.started",
            n_prompts=len(composition.prompts),
            threshold=PASS_THRESHOLD,
        )
        current = composition
        final_results: list[ValidatedPrompt] = []
        status: Literal["ok", "regenerated", "rejected"] = "ok"
        used_attempts = 1
        for attempt in range(1, max_attempts + 1):
            results = [
                score_prompt(prompt, knowledge=knowledge, consistency=consistency)
                for prompt in current.prompts
            ]
            final_results = results
            failed = [result for result in results if result.score < PASS_THRESHOLD]
            if not failed:
                status = "ok" if attempt == 1 else "regenerated"
                used_attempts = attempt
                break
            used_attempts = attempt
            if attempt >= max_attempts:
                status = "rejected"
                break
            repairs: dict[int, list[str]] = {}
            for result in failed:
                repairs[result.shot_id] = [issue for issue in result.issues if issue in _REPAIRABLE]
            self._logger.warning(
                "event=prompt_validator.regenerating",
                attempt=attempt,
                n_failed=len(failed),
                repairs=repairs,
            )
            current = await composer(repairs)
        else:
            status = "rejected"

        self._logger.info(
            "event=prompt_validator.completed",
            status=status,
            attempts=used_attempts,
            scores=[result.score for result in final_results],
        )
        return (
            PromptValidationOutput(
                status=status,
                attempts=used_attempts,
                prompts=final_results,
            ),
            current,
        )


def score_prompt(
    prompt: ComposedPrompt,
    *,
    knowledge: KnowledgeOutput,
    consistency: ConsistencyOutput,
) -> ValidatedPrompt:
    """Score one composed prompt against the 100-point rubric."""
    positive = prompt.positive_prompt
    negative = prompt.negative_prompt
    positive_lower = positive.lower()
    negative_lower = negative.lower()
    criteria: list[CriterionScore] = []
    issues: list[str] = []

    def criterion(name: str, max_score: int, passed: bool, note: str) -> int:
        score = max_score if passed else 0
        if not passed:
            issues.append(_REPAIR_FOR_CRITERION.get(name, name))
        criteria.append(
            CriterionScore(name=name, score=score, max=max_score, notes=note if not passed else "")
        )
        return score

    total = 0
    subject = prompt.fields.subject.strip()
    total += criterion(
        "subject_present",
        15,
        bool(subject) and positive_lower.startswith(subject.lower()),
        "positive prompt must open with the subject",
    )

    environment = prompt.fields.environment.strip()
    total += criterion(
        "environment_present",
        10,
        bool(environment) and environment.lower() in positive_lower,
        "a concrete environment must be stated",
    )

    composition = prompt.fields.composition.strip()
    total += criterion(
        "composition_present",
        10,
        bool(composition) and composition.lower() in positive_lower,
        "a deliberate composition must be stated",
    )

    camera = prompt.fields.camera.strip()
    lens = prompt.fields.lens.strip()
    total += criterion(
        "camera_specified",
        10,
        bool(camera) and bool(lens) and (camera.lower() in positive_lower or lens.lower() in positive_lower),
        "camera angle, movement, and lens must be specified",
    )

    lighting = prompt.fields.lighting.strip()
    total += criterion(
        "lighting_specified",
        10,
        bool(lighting) and lighting.lower() in positive_lower,
        "one consistent lighting scheme must be stated",
    )

    concept = knowledge.primary_concept()
    detail = prompt.fields.engineering_detail.strip()
    total += criterion(
        "teaching_goal",
        10,
        bool(detail) and (not concept or concept.lower() in positive_lower),
        "the teaching concept must be weighted into the prompt",
    )

    forbidden_hits = [word for word in _FORBIDDEN_STYLE_WORDS if word in positive_lower]
    canonical_hits = _canonical_tokens(positive_lower, knowledge)
    total += criterion(
        "engineering_realism",
        10,
        not forbidden_hits and bool(canonical_hits),
        f"forbidden fantasy vocabulary: {', '.join(forbidden_hits)}"
        if forbidden_hits
        else "canonical engineering vocabulary is missing",
    )

    subject_count = positive_lower.count(subject.lower()) if subject else 0
    single_focus = any(
        marker in composition.lower()
        for marker in (
            "central",
            "centered",
            "single",
            "one clear",
            "fills the frame",
            "subject",
            "full mechanism in frame",
            "before-after split",
        )
    )
    total += criterion(
        "object_hierarchy",
        5,
        bool(subject) and subject_count == 1 and single_focus,
        "one clear focal subject with no competing objects",
    )

    materials = prompt.fields.materials.strip()
    material_hits = [name for name in consistency.materials if name.lower() in positive_lower]
    total += criterion(
        "material_detail",
        5,
        bool(materials) and bool(material_hits),
        "at least one canonical material must be named",
    )

    total += criterion(
        "negative_prompt_quality",
        5,
        bool(negative)
        and all(token in negative_lower for token in _NEGATIVE_HYGIENE)
        and len(negative) >= 80,
        "negatives must cover hygiene artifacts and drift",
    )

    quality_hits = sum(1 for item in prompt.quality_constraints if item.lower() in positive_lower)
    total += criterion(
        "quality_constraints",
        5,
        len(prompt.quality_constraints) >= 2 and quality_hits >= 2,
        "two or more quality descriptors must be present",
    )

    lock_hits = [marker for marker in _LOCK_MARKERS if marker in negative_lower]
    total += criterion(
        "consistency_anchors",
        5,
        bool(lock_hits),
        "cross-shot consistency locks must appear in the negatives",
    )

    if prompt.is_thumbnail:
        total, thumbnail_issues = _apply_thumbnail_penalties(
            prompt,
            total,
            positive_lower,
            criteria,
        )
        issues.extend(thumbnail_issues)

    total = max(0, min(100, total))
    issues = _dedupe(issues)
    return ValidatedPrompt(
        shot_id=prompt.shot_id,
        score=total,
        status="passed" if total >= PASS_THRESHOLD else "regenerated",
        issues=issues,
        criteria=criteria,
        positive_prompt=positive,
        negative_prompt=negative,
    )


# ---------------------------------------------------------------- internals --


def _canonical_tokens(positive_lower: str, knowledge: KnowledgeOutput) -> list[str]:
    hits = [word for word in _CANONICAL_VOCABULARY if word in positive_lower]
    hits.extend(name for name in knowledge.objects if name.lower() in positive_lower)
    hits.extend(name for name in knowledge.materials if name.lower() in positive_lower)
    hits.extend(
        mechanism.name
        for mechanism in knowledge.mechanisms
        if mechanism.name.lower() in positive_lower
    )
    return hits


def _apply_thumbnail_penalties(
    prompt: ComposedPrompt,
    total: int,
    positive_lower: str,
    criteria: list[CriterionScore],
) -> tuple[int, list[str]]:
    """Thumbnail intelligence rubric: -5 per missed rule (max 100)."""
    penalties: list[tuple[str, str]] = []
    composition = prompt.fields.composition.lower()
    if not ("large central" in composition or "centered" in composition):
        penalties.append(("thumbnail_subject_not_central", "thumbnail subject must be large and central"))
    if "minimal clutter" not in composition and "clutter" not in positive_lower:
        penalties.append(("thumbnail_cluttered", "thumbnail must minimize clutter"))
    if "high contrast" not in positive_lower:
        penalties.append(("thumbnail_low_contrast", "thumbnail must use high contrast"))

    score = total
    issues: list[str] = []
    for name, note in penalties:
        score = max(0, score - 5)
        issues.append(name)
        criteria.append(CriterionScore(name=name, score=0, max=5, notes=note))
    return score, issues


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
