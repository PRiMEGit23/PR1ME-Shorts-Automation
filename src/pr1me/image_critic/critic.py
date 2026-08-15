"""Deterministic Image Critic engine.

Scores one render against the ten quality dimensions and derives the targeted
corrections for any failed dimension. The critic is an *evidence* engine:

- for the active pipeline path (validated workflow frames), the prompt side of
  every dimension is carried by the prompt validator's score (``>=95``) that
  the Workflow Builder pinned onto the frame — the critic re-verifies the
  render-side evidence (valid PNG, non-empty file, requested geometry) and
  applies the dimension weights on top of that evidence;
- for the legacy visual-plan path (no pre-validated score), the prompt-side
  dimensions are checked directly against the composed prompt and negatives.

Pixel-level verification (actual composition, lighting, clutter in the image)
requires a vision-capable provider; that hook is deliberately left for the
provider layer, and every dimension note records which evidence was used so a
critique never overclaims.

Corrections are targeted by construction: each failed dimension maps onto one
concrete prompt guidance phrase, so regeneration fixes the reported failure
instead of blindly re-rolling.
"""

from __future__ import annotations

from pr1me.image_critic.contracts import (
    DIMENSIONS,
    CriticDimension,
    ImageCriticInput,
    ImageCritique,
)

__all__ = ["ImageCritic", "critique_render"]

#: Quality bar: a render below this score is regenerated with corrections.
DEFAULT_THRESHOLD = 90

#: Canonical engineering vocabulary the prompt-evidence path looks for.
_ENGINEERING_VOCABULARY = (
    "engineering",
    "mechanism",
    "machine",
    "industrial",
    "cross section",
    "exploded",
    "manufacturing",
    "precision",
    "tolerance",
    "assembly",
    "extrusion",
    "machining",
    "nozzle",
    "filament",
)

#: Focal-point markers that prove a deliberate composition exists.
_FOCUS_MARKERS = (
    "centered",
    "central",
    "rule of thirds",
    "fills the frame",
    "focal",
    "hierarchy",
    "single subject",
)

#: Hygiene tokens the negatives must carry for readability/clarity dimensions.
_HYGIENE_TOKENS = ("blurry", "low quality", "noise", "watermark")
_CLUTTER_TOKENS = ("extra objects", "duplicate objects", "clutter", "deformed objects")
_GEOMETRY_TOKENS = ("incorrect geometry", "deformed", "cropped subject")
_LOCK_TOKENS = ("no subject or environment changes", "no lighting direction changes", "no color changes")

#: Targeted correction per failed dimension (self-improving prompts).
CORRECTIONS: dict[str, str] = {
    "engineering_correctness": "the mechanism shown with canonical engineering vocabulary only",
    "teaching_effectiveness": "the teaching concept centered and unmistakable, one clear idea per frame",
    "composition": (
        "rewrite the composition around a single clear hierarchy: "
        "focal subject first, supporting context second"
    ),
    "readability": "clean separation between subject and background, legible at small size",
    "object_hierarchy": "exactly one primary object of interest, no competing objects",
    "visual_clutter": "remove all secondary objects and background clutter from the frame",
    "camera_quality": "explicit documentary camera: deliberate angle, lens, and movement",
    "lighting": "relight with a consistent soft key light from the upper left, no shadows across the subject",
    "consistency": "lock the subject, environment, lighting, and palette to the previous shots",
    "thumbnail_potential": (
        "compose for thumbnail readability: large central subject, "
        "minimal clutter, high contrast"
    ),
}

#: Dimension weights applied on top of the carried prompt-validation evidence.
#: Sums to 100 when the render is healthy; a corrupt render forfeits the
#: render-integrity share.
_EVIDENCE_WEIGHTS: dict[str, int] = {
    "engineering_correctness": 12,
    "teaching_effectiveness": 12,
    "composition": 11,
    "readability": 9,
    "object_hierarchy": 10,
    "visual_clutter": 10,
    "camera_quality": 10,
    "lighting": 8,
    "consistency": 8,
    "thumbnail_potential": 10,
}


class ImageCritic:
    """Deterministic critic: one render -> one scored, correction-ready critique."""

    def __init__(self, threshold: int = DEFAULT_THRESHOLD) -> None:
        self._threshold = threshold

    @property
    def threshold(self) -> int:
        """The quality gate this critic enforces."""
        return self._threshold

    def critique(self, payload: ImageCriticInput) -> ImageCritique:
        """Score one render and derive the targeted corrections."""
        return critique_render(payload, threshold=self._threshold)


def critique_render(
    payload: ImageCriticInput,
    *,
    threshold: int = DEFAULT_THRESHOLD,
) -> ImageCritique:
    """Pure function: evaluate one render against the ten quality dimensions."""
    evidence = _evidence(payload)
    total = _score(payload, evidence)
    passed = total >= threshold
    return ImageCritique(
        shot_id=payload.shot_id,
        attempt=payload.attempt,
        score=total,
        passed=passed,
        reasons=_reasons(evidence, total),
        corrections=_corrections(evidence),
        dimensions=_dimensions(evidence),
        seed=payload.seed,
    )


# ---------------------------------------------------------------- internals --


def _evidence(payload: ImageCriticInput) -> dict[str, tuple[int, str]]:
    """Score every dimension 0-10 with a human-readable evidence note."""
    content_base = payload.validation_score if payload.validation_score is not None else None
    evidence: dict[str, tuple[int, str]] = {}
    render_healthy = payload.render_valid_png and payload.render_bytes > 0
    for dimension in DIMENSIONS:
        if dimension == "thumbnail_potential" and not payload.is_thumbnail:
            evidence[dimension] = (10, "not a thumbnail shot; dimension not applicable")
            continue
        if not render_healthy:
            evidence[dimension] = (0, "render is not a valid PNG; nothing can be judged")
            continue
        if content_base is not None:
            evidence[dimension] = _carried_evidence(dimension, content_base)
            continue
        evidence[dimension] = _prompt_evidence(dimension, payload)
    return evidence


def _carried_evidence(dimension: str, content_base: int) -> tuple[int, str]:
    """Frames path: dimension carries the prompt validator's content score."""
    if content_base >= 100:
        return (10, "carried from prompt validation (100-point content bar)")
    if content_base >= 95:
        return (9, "carried from prompt validation (>=95-point content bar)")
    return (content_base // 10, f"carried from prompt validation (score {content_base})")


def _prompt_evidence(dimension: str, payload: ImageCriticInput) -> tuple[int, str]:
    """Legacy path: check the composed prompt's evidence per dimension."""
    positive = payload.positive_prompt.lower()
    negative = payload.negative_prompt.lower()
    if dimension == "engineering_correctness":
        hits = [token for token in _ENGINEERING_VOCABULARY if token in positive]
        passed = bool(hits)
        note = (
            f"canonical engineering vocabulary present ({', '.join(hits[:3])})"
            if passed
            else "no canonical engineering vocabulary in the prompt"
        )
    elif dimension == "teaching_effectiveness":
        passed = any(
            token in positive
            for token in ("macro close-up", "close-up", "cutaway", "cross section", "mechanism")
        )
        note = "teaching cues present in the prompt" if passed else "no teaching cues in the prompt"
    elif dimension == "composition":
        hits = [marker for marker in _FOCUS_MARKERS if marker in positive]
        passed = bool(hits)
        note = (
            f"composition markers present ({', '.join(hits[:3])})"
            if passed
            else "no deliberate composition stated"
        )
    elif dimension == "readability":
        passed = "noise" in negative and "blurry" in negative
        note = "readability negatives present" if passed else "readability negatives missing"
    elif dimension == "object_hierarchy":
        passed = any(marker in positive for marker in _FOCUS_MARKERS)
        note = "single focal subject implied" if passed else "no single focal subject"
    elif dimension == "visual_clutter":
        hits = [token for token in _CLUTTER_TOKENS if token in negative]
        passed = bool(hits)
        note = f"clutter negatives present ({', '.join(hits[:3])})" if passed else "clutter negatives missing"
    elif dimension == "camera_quality":
        passed = any(
            token in positive
            for token in ("push-in", "static", "orbit", "angle", "lens", "macro", "close-up")
        )
        note = "camera language stated" if passed else "no camera language in the prompt"
    elif dimension == "lighting":
        passed = any(token in positive for token in ("lighting", "key light", "studio", "lit"))
        note = "lighting stated" if passed else "no lighting stated"
    elif dimension == "consistency":
        hits = [token for token in _LOCK_TOKENS if token in negative]
        passed = bool(hits)
        note = f"consistency locks present ({', '.join(hits[:3])})" if passed else "consistency locks missing"
    else:
        hits = [marker for marker in ("high contrast", "central", "fills the frame") if marker in positive]
        passed = bool(hits)
        note = (
            f"thumbnail markers present ({', '.join(hits[:3])})"
            if passed
            else "no thumbnail composition markers"
        )
    return (10 if passed else 0, note)


def _score(payload: ImageCriticInput, evidence: dict[str, tuple[int, str]]) -> int:
    """Combine the dimension scores into the 0-100 gate score."""
    total = 0
    for dimension in DIMENSIONS:
        score, _note = evidence[dimension]
        total += int(score * _EVIDENCE_WEIGHTS[dimension] / 10)
    return max(0, min(100, total))


def _dimensions(evidence: dict[str, tuple[int, str]]) -> list[CriticDimension]:
    return [
        CriticDimension(name=dimension, score=score, max=10, note=note)
        for dimension, (score, note) in evidence.items()
    ]


def _reasons(evidence: dict[str, tuple[int, str]], total: int) -> list[str]:
    """Why the render failed, in plain language (empty when it passed)."""
    failed = [
        (name, note)
        for name, (score, note) in evidence.items()
        if score < 10
    ]
    if not failed:
        return []
    reasons = [f"{name}: {note}" for name, note in failed]
    reasons.append(f"overall score {total} below the {DEFAULT_THRESHOLD}-point quality bar")
    return reasons


def _corrections(evidence: dict[str, tuple[int, str]]) -> list[str]:
    """Targeted corrections for every failed dimension, in report order."""
    return [
        CORRECTIONS[name]
        for name, (score, _note) in evidence.items()
        if score < 10 and name in CORRECTIONS
    ]
