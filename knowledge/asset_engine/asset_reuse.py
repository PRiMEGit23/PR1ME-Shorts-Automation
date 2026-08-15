"""Asset reuse: the studio's reuse policy and its recorded usage (Phase 12).

Reuse policy (deterministic): if an existing asset's measured quality
exceeds ``REUSE_QUALITY_THRESHOLD`` and it is similar enough, reuse it;
otherwise generate new. Every reuse is recorded as a ``ReuseEvent`` with
its consumer, and the record's usage count, topics, and reuse score
update accordingly. The reuse engine is the single place that decides
``REUSE`` - the selector feeds it, consumers call it, and nobody else
touches usage counters (no duplicated logic).
"""

from __future__ import annotations

from knowledge.asset_engine.asset_models import (
    REUSE_QUALITY_THRESHOLD,
    ReuseDecision,
    ReuseEvent,
    SelectionDecision,
)
from knowledge.asset_engine.asset_registry import AssetRegistry


class ReuseEngine:
    """Records reuses and answers the studio's usage questions."""

    def __init__(self, registry: AssetRegistry) -> None:
        self._registry = registry
        self._events: list[ReuseEvent] = []

    # ------------------------------------------------------------------ use --

    def apply(self, decision: SelectionDecision, *, consumer: str, topic: str) -> ReuseEvent:
        """Record one decision; increments usage when the asset is reused.

        Returns the recorded event. ``REUSE`` / ``REPLACE`` / ``IMPROVE``
        count as a reuse of the chosen asset (it is being consumed); other
        decisions record the event without touching usage.
        """
        sequence = len(self._events)
        asset_id = decision.chosen_asset_id
        if asset_id is not None and decision.decision in (
            ReuseDecision.REUSE,
            ReuseDecision.REPLACE,
            ReuseDecision.IMPROVE,
        ):
            self._registry.record_reuse(
                asset_id,
                topic=topic,
                consumer=consumer,
                reason=decision.rationale,
            )
        event = ReuseEvent(
            sequence=sequence,
            consumer=consumer,
            asset_id=asset_id or "(none)",
            decision=decision.decision,
            rationale=decision.rationale,
            topic=topic,
        )
        self._events.append(event)
        return event

    # ----------------------------------------------------------------- read --

    def events(self) -> tuple[ReuseEvent, ...]:
        """Every recorded reuse event, in recording order."""
        return tuple(self._events)

    def usage_count(self, asset_id: str) -> int:
        """How many times one asset has been consumed."""
        return self._registry.get(asset_id).usage_count

    def topics_using(self, asset_id: str) -> tuple[str, ...]:
        """The distinct topics that consumed one asset (sorted)."""
        return self._registry.get(asset_id).topics_using

    def most_used(self, limit: int = 10) -> tuple[str, ...]:
        """Asset ids ranked by (-usage, -reuse_score, asset_id)."""
        ranked = sorted(
            self._registry.all(),
            key=lambda record: (
                -record.usage_count,
                -record.reuse_score,
                record.asset_id,
            ),
        )
        return tuple(record.asset_id for record in ranked[:limit])

    def reuse_ratio(self) -> float:
        """Share of all decisions that ended in reuse (0.0 when none yet)."""
        if not self._events:
            return 0.0
        reused = sum(
            1
            for event in self._events
            if event.decision in (ReuseDecision.REUSE, ReuseDecision.REPLACE)
        )
        return round(reused / len(self._events), 3)

    def reuseable_candidates(self) -> tuple[str, ...]:
        """Active assets whose quality clears the reuse bar (sorted by id)."""
        return tuple(
            record.asset_id
            for record in self._registry.all()
            if record.status.value == "active"
            and record.quality_score > REUSE_QUALITY_THRESHOLD
        )
