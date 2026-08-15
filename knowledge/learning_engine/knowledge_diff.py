"""Knowledge diff: the before/after edit behind every proposal (Phase 11).

The Learning Engine never applies a diff - it only *produces* them. Every
proposal carries a ``KnowledgeDiff`` describing the reviewable edit: the
affected module and table, the exact entry and field, the current value
(before), the proposed value (after), the reason, the confidence, the
supporting evidence (exact run:scene references), and the predicted
improvement. All of it deterministic.
"""

from __future__ import annotations

from knowledge.learning_engine.learning_models import (
    CompilerRecommendation,
    DirectorRecommendation,
    ImprovementProposal,
    KnowledgeDiff,
    KnowledgeProposal,
    ModelRecommendation,
    OptimizationRecommendation,
    WorkflowRecommendation,
)


def build_diff(proposal: ImprovementProposal) -> KnowledgeDiff | None:
    """The reviewable before/after edit a proposal implies (or None)."""
    table, entry, field, before, after = _edit(proposal)
    if table is None:
        return None
    return KnowledgeDiff(
        proposal_kind=proposal.kind,
        module=proposal.affected_modules[0] if proposal.affected_modules else "(unset)",
        table=table,
        entry_key=entry,
        field=field,
        before=before,
        after=after,
        reason=proposal.reason,
        confidence=proposal.confidence,
        evidence=proposal.evidence,
        predicted_improvement=proposal.predicted_improvement,
    )


def build_diffs(proposals: tuple) -> tuple[KnowledgeDiff, ...]:
    """The diffs for every proposal that maps to a concrete edit."""
    diffs = [diff for proposal in proposals if (diff := build_diff(proposal)) is not None]
    return tuple(diffs)


def _edit(proposal: ImprovementProposal) -> tuple[str | None, str, str, str, str]:
    """(table, entry_key, field, before, after) for one proposal kind."""
    if isinstance(proposal, KnowledgeProposal):
        return (
            proposal.knowledge_table,
            proposal.entry_key,
            proposal.field,
            proposal.before,
            proposal.after,
        )
    if isinstance(proposal, ModelRecommendation):
        return (
            "model_registry",
            proposal.to_model,
            "capability_benchmark",
            f"measured as {proposal.from_model}",
            f"measured lead {proposal.predicted_qa_gain:+.1f} QA",
        )
    if isinstance(proposal, DirectorRecommendation):
        return (
            "director_rules",
            proposal.area,
            "preferred_value",
            proposal.current_value,
            proposal.suggested_value,
        )
    if isinstance(proposal, CompilerRecommendation):
        return (
            "compiler_negatives",
            proposal.prompt_field,
            "tokens",
            "(empty)",
            proposal.token,
        )
    if isinstance(proposal, WorkflowRecommendation):
        return (
            "workflow_selector",
            proposal.scope_key,
            "profile",
            proposal.current_profile,
            proposal.suggested_profile,
        )
    if isinstance(proposal, OptimizationRecommendation):
        return (
            "optimization_rules",
            proposal.optimizer_rule,
            "strategy",
            proposal.current_value,
            proposal.suggested_value,
        )
    return None, "", "", "", ""
