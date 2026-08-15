"""Optimization rules: the deterministic knowledge of what fixes what.

The QA report says which checks failed. The rule table says which actions
fix which check, how much each action is expected to raise the relevant
report score (target_score is the exact field name on ImageQualityReport),
and which severity of issue triggers the rule.

The table is data, not code: every entry is frozen, and the optimizer only
assembles actions from it. Expected gains are deliberately conservative and
capped (MAX_GAIN_PER_ROUND) so the projection stays believable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge.image_qa.qa_models import IssueSeverity, QACheck
from knowledge.render_optimizer.optimization_models import OptimizationActionKind

#: Rules fire when the score they target falls below this floor.
OPTIMIZATION_FLOOR = 70.0

#: Rules fire only for issues at least this severe, unless the score is low.
MIN_TRIGGER_SEVERITY = IssueSeverity.MAJOR


@dataclass(frozen=True)
class ActionTemplate:
    """One candidate action: what kind, what to do, and what it buys."""

    kind: OptimizationActionKind
    instruction: str
    gain: float
    target_score: str
    severity: IssueSeverity = MIN_TRIGGER_SEVERITY


@dataclass(frozen=True)
class OptimizationRule:
    """All candidate actions for one QA check."""

    check: QACheck
    actions: tuple[ActionTemplate, ...] = field(default_factory=tuple)


#: Deterministic rule table, one rule per QA check.
OPTIMIZATION_RULES: dict[QACheck, OptimizationRule] = {
    QACheck.ENGINEERING_ACCURACY: OptimizationRule(
        check=QACheck.ENGINEERING_ACCURACY,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.VISUALIZATION,
                instruction="increase engineering visualization with a cutaway "
                "or exploded view of the part",
                gain=12.0,
                target_score="engineering_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.VISUALIZATION,
                instruction="add engineering annotations (callouts) to the scene",
                gain=8.0,
                target_score="engineering_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.WORKFLOW,
                instruction="switch to the cutaway workflow profile for interior "
                "geometry clarity",
                gain=6.0,
                target_score="engineering_score",
            ),
        ),
    ),
    QACheck.GEOMETRY_CORRECTNESS: OptimizationRule(
        check=QACheck.GEOMETRY_CORRECTNESS,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.WORKFLOW,
                instruction="switch to the CAD workflow profile for exact geometry",
                gain=10.0,
                target_score="engineering_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="strengthen geometry description in the prompt "
                "(exact silhouettes, sharp edges)",
                gain=8.0,
                target_score="engineering_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.CAMERA,
                instruction="use a more descriptive camera distance for geometry clarity",
                gain=4.0,
                target_score="engineering_score",
            ),
        ),
    ),
    QACheck.MATERIAL_CORRECTNESS: OptimizationRule(
        check=QACheck.MATERIAL_CORRECTNESS,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="correct the material tokens in the prompt to the "
                "planned material",
                gain=12.0,
                target_score="engineering_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.WORKFLOW,
                instruction="switch to the CAD workflow profile for material fidelity",
                gain=6.0,
                target_score="engineering_score",
            ),
        ),
    ),
    QACheck.CAMERA_SUITABILITY: OptimizationRule(
        check=QACheck.CAMERA_SUITABILITY,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.CAMERA,
                instruction="align camera distance, angle, lens, and framing "
                "with the planned shot",
                gain=12.0,
                target_score="engineering_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="re-assert the planned camera phrase in the prompt",
                gain=6.0,
                target_score="engineering_score",
            ),
        ),
    ),
    QACheck.LIGHTING_SUITABILITY: OptimizationRule(
        check=QACheck.LIGHTING_SUITABILITY,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.LIGHTING,
                instruction="align lighting direction and style with the "
                "planned lighting",
                gain=12.0,
                target_score="engineering_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="re-assert the planned lighting phrase in the prompt",
                gain=6.0,
                target_score="engineering_score",
            ),
        ),
    ),
    QACheck.PRIMARY_SUBJECT_VISIBILITY: OptimizationRule(
        check=QACheck.PRIMARY_SUBJECT_VISIBILITY,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.CAMERA,
                instruction="increase subject scale with a tighter framing",
                gain=12.0,
                target_score="composition_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.COMPOSITION,
                instruction="simplify the composition so the subject dominates",
                gain=8.0,
                target_score="composition_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="emphasize the primary subject in the prompt",
                gain=6.0,
                target_score="composition_score",
            ),
        ),
    ),
    QACheck.SUBJECT_HIERARCHY: OptimizationRule(
        check=QACheck.SUBJECT_HIERARCHY,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.COMPOSITION,
                instruction="make the primary subject hierarchy explicit "
                "(dominant subject, secondary elements)",
                gain=12.0,
                target_score="subject_hierarchy_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.CAMERA,
                instruction="tighter framing so nothing competes with the subject",
                gain=6.0,
                target_score="subject_hierarchy_score",
            ),
        ),
    ),
    QACheck.COMPOSITION_QUALITY: OptimizationRule(
        check=QACheck.COMPOSITION_QUALITY,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.COMPOSITION,
                instruction="reframe according to the planned composition rule "
                "(e.g. rule of thirds)",
                gain=12.0,
                target_score="composition_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.CAMERA,
                instruction="adjust framing and lens to improve composition",
                gain=6.0,
                target_score="composition_score",
            ),
        ),
    ),
    QACheck.VISUAL_CLUTTER: OptimizationRule(
        check=QACheck.VISUAL_CLUTTER,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.COMPOSITION,
                instruction="simplify the background and remove clutter",
                gain=12.0,
                target_score="composition_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="add clutter-avoidance tokens to the negative prompt",
                gain=8.0,
                target_score="visual_clarity_score",
            ),
        ),
    ),
    QACheck.EDUCATIONAL_EFFECTIVENESS: OptimizationRule(
        check=QACheck.EDUCATIONAL_EFFECTIVENESS,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.VISUALIZATION,
                instruction="switch the visualization strategy to the planned "
                "teaching method",
                gain=12.0,
                target_score="educational_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.VISUALIZATION,
                instruction="add annotations and callouts for the teaching method",
                gain=10.0,
                target_score="educational_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="add comparison or contrast elements for the "
                "teaching method",
                gain=6.0,
                target_score="educational_score",
            ),
        ),
    ),
    QACheck.THUMBNAIL_STRENGTH: OptimizationRule(
        check=QACheck.THUMBNAIL_STRENGTH,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.COMPOSITION,
                instruction="strengthen the hero composition and focal point",
                gain=12.0,
                target_score="thumbnail_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.LIGHTING,
                instruction="increase contrast with a dramatic key light",
                gain=8.0,
                target_score="thumbnail_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="add high-contrast thumbnail tokens to the prompt",
                gain=6.0,
                target_score="thumbnail_score",
            ),
        ),
    ),
    QACheck.SCENE_CONSISTENCY: OptimizationRule(
        check=QACheck.SCENE_CONSISTENCY,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.CONSISTENCY,
                instruction="enforce a consistent material and color palette "
                "across scenes",
                gain=15.0,
                target_score="consistency_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="fix prompt terms that contradict the planned scene",
                gain=10.0,
                target_score="consistency_score",
            ),
        ),
    ),
    QACheck.PROMPT_CONSISTENCY: OptimizationRule(
        check=QACheck.PROMPT_CONSISTENCY,
        actions=(
            ActionTemplate(
                kind=OptimizationActionKind.PROMPT,
                instruction="align prompt terms with the planned shot and scene",
                gain=12.0,
                target_score="consistency_score",
            ),
            ActionTemplate(
                kind=OptimizationActionKind.CONSISTENCY,
                instruction="enforce the planned palette tokens in the prompt",
                gain=8.0,
                target_score="consistency_score",
            ),
        ),
    ),
}


def rule_for(check: QACheck) -> OptimizationRule:
    """Fetch the rule for a check; unknown checks have no actions."""
    return OPTIMIZATION_RULES.get(check, OptimizationRule(check=check))


#: All report score field names the rules may target, in QA report order.
SCORE_FIELDS: tuple[str, ...] = (
    "engineering_score",
    "educational_score",
    "composition_score",
    "subject_hierarchy_score",
    "visual_clarity_score",
    "thumbnail_score",
    "consistency_score",
)