"""Render repair engine: deterministic repair instructions, never re-renders.

Each QA issue maps to one or more concrete repair instructions. The mapping
is a static table keyed by check name, so the same issue always produces the
same repair - no LLM, no randomness, and the engine never re-renders anything.
A future stage (or a human editor) decides whether to act on the suggestions.
"""

from __future__ import annotations

from knowledge.image_qa.qa_models import QACheck, QAIssue

_REPAIR_TABLE: dict[QACheck, tuple[str, ...]] = {
    QACheck.PRIMARY_SUBJECT_VISIBILITY: (
        "Increase subject prominence",
        "Reduce occlusion of the primary subject",
        "Move the subject closer to the center of the frame",
    ),
    QACheck.SUBJECT_HIERARCHY: (
        "Emphasize the primary subject over secondary elements",
        "Dim or blur competing background elements",
    ),
    QACheck.ENGINEERING_ACCURACY: (
        "Re-check the engineering detail against the engineering_summary",
        "Render the planned engineering visualization exactly as specified",
    ),
    QACheck.GEOMETRY_CORRECTNESS: (
        "Re-render with corrected geometry",
        "Switch to macro shot to show the true geometry",
    ),
    QACheck.MATERIAL_CORRECTNESS: (
        "Re-render with the correct material finish",
        "Use the planned material in the prompt without substitutions",
    ),
    QACheck.CAMERA_SUITABILITY: (
        "Switch to macro shot",
        "Match the planned camera angle",
        "Use the planned lens",
    ),
    QACheck.LIGHTING_SUITABILITY: (
        "Improve lighting direction",
        "Match the planned lighting style",
    ),
    QACheck.COMPOSITION_QUALITY: (
        "Recompose to the planned framing rule",
        "Improve comparison framing",
    ),
    QACheck.VISUAL_CLUTTER: (
        "Remove distracting background",
        "Simplify the scene to the planned environment",
    ),
    QACheck.EDUCATIONAL_EFFECTIVENESS: (
        "Increase engineering annotations",
        "Show the planned visual teaching method explicitly",
        "Add the comparison axis the strategy requires",
    ),
    QACheck.THUMBNAIL_STRENGTH: (
        "Raise thumbnail contrast",
        "Sharpen the thumbnail focus",
        "Leave negative space for the overlay title",
    ),
    QACheck.SCENE_CONSISTENCY: (
        "Re-render to match the scene's consistency tags",
        "Keep palette, materials, and environment identical within the scene",
    ),
    QACheck.PROMPT_CONSISTENCY: (
        "Recompile the prompt with the missing terms",
        "Keep the prompt aligned with the storyboard's subject and shot intent",
    ),
}

_FALLBACK_REPAIR = "Re-render against the storyboard plan"


class RenderRepairEngine:
    """Maps QA issues to deterministic repair instructions."""

    def suggest(self, issues: list[QAIssue]) -> list[str]:
        """Return deduplicated repair instructions, one per offending check.

        Capped at 8 suggestions to stay within ImageQualityReport's
        repair_suggestions limit; the report cannot carry more.
        """
        suggestions: list[str] = []
        seen: set[QACheck] = set()
        for issue in issues:
            if issue.check in seen:
                continue
            seen.add(issue.check)
            repairs = _REPAIR_TABLE.get(issue.check, (_FALLBACK_REPAIR,))
            suggestions.append(repairs[0])
            if len(suggestions) >= 8:
                break
        return suggestions

    def suggest_all(self, issues: list[QAIssue]) -> list[str]:
        """Return every repair instruction for the issues, deduplicated."""
        suggestions: list[str] = []
        seen: set[str] = set()
        for issue in issues:
            for repair in _REPAIR_TABLE.get(issue.check, (_FALLBACK_REPAIR,)):
                if repair in seen:
                    continue
                seen.add(repair)
                suggestions.append(repair)
        return suggestions