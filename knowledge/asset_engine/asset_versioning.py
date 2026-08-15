"""Asset versioning: version chains, genealogy, and replacement (Phase 12).

Every asset belongs to a version chain - the deterministic grouping of
records that represent the same logical artifact (same type, topic, and
semantic key). ``add_version`` links a new record to its chain: it gets
the next version number, points at its parent, and supersedes the chain's
previous best when it is meaningfully better. The lineage (parents,
children, chain history) is a pure function of the records.
"""

from __future__ import annotations

from knowledge.asset_engine.asset_models import (
    REPLACE_QUALITY_GAP,
    AssetRecord,
    AssetStatus,
)
from knowledge.asset_engine.asset_registry import AssetRegistry

#: The chain key separator (never a letter or digit, so keys are safe).
_CHAIN_SEPARATOR = "::"

#: Record fields that define the logical identity of an asset.
_CHAIN_FIELDS: tuple[str, ...] = (
    "asset_type",
    "source_topic",
    "objects",
    "materials",
    "processes",
)


def chain_key(record: AssetRecord) -> str:
    """The deterministic logical identity of a record."""
    parts: list[str] = []
    for field in _CHAIN_FIELDS:
        value = getattr(record, field)
        if isinstance(value, tuple):
            parts.append("+".join(sorted(value)) or "(none)")
        else:
            parts.append(value.value if hasattr(value, "value") else str(value))
    return _CHAIN_SEPARATOR.join(parts).lower()


def add_version(registry: AssetRegistry, record: AssetRecord) -> AssetRecord:
    """Link a record into its chain; returns the versioned record.

    The first record of a chain is version 1. Later records become the
    next version, point at the chain's previous record as parent, and
    mark the previous best obsolete when they beat it by at least
    ``REPLACE_QUALITY_GAP``.
    """
    chain = chain_key(record)
    chain_members = _chain_members(registry, chain)
    if not chain_members:
        fields = record.model_dump()
        fields["version"] = 1
        fields["chain_id"] = chain
        return AssetRecord.model_validate(fields)

    previous = chain_members[-1]
    supersedes = _best_in_chain(chain_members)
    fields = record.model_dump()
    fields["version"] = previous.version + 1
    fields["chain_id"] = chain
    fields["parent_asset_id"] = previous.asset_id

    if (
        supersedes is not None
        and record.quality_score - supersedes.quality_score >= REPLACE_QUALITY_GAP
    ):
        fields["superseded_by"] = None
        _mark_obsolete(registry, supersedes, record)
    return AssetRecord.model_validate(fields)


def lineage(registry: AssetRegistry, asset_id: str) -> tuple[AssetRecord, ...]:
    """The full chain ancestry of one asset (oldest first, deterministic)."""
    record = registry.get(asset_id)
    chain = [record]
    parent_id = record.parent_asset_id
    seen: set[str] = {record.asset_id}
    while parent_id is not None and parent_id not in seen:
        seen.add(parent_id)
        parent = registry.try_get(parent_id)
        if parent is None:
            break
        chain.append(parent)
        parent_id = parent.parent_asset_id
    return tuple(reversed(chain))


def chain_members(registry: AssetRegistry, asset_id: str) -> tuple[AssetRecord, ...]:
    """Every record of an asset's chain, sorted by (version, asset_id)."""
    record = registry.get(asset_id)
    members = _chain_members(registry, record.chain_id)
    return tuple(sorted(members, key=lambda member: (member.version, member.asset_id)))


def newest_active(registry: AssetRegistry, asset_id: str) -> AssetRecord | None:
    """The newest active record of an asset's chain, or None."""
    active = [
        member
        for member in chain_members(registry, asset_id)
        if member.status is AssetStatus.ACTIVE
    ]
    if not active:
        return None
    return max(active, key=lambda member: (member.version, member.asset_id))


def _chain_members(registry: AssetRegistry, chain: str) -> list[AssetRecord]:
    return [
        record
        for record in registry.all()
        if record.chain_id == chain
    ]


def _best_in_chain(members: list[AssetRecord]) -> AssetRecord | None:
    if not members:
        return None
    return max(members, key=lambda member: (member.quality_score, member.version))


def _mark_obsolete(registry: AssetRegistry, old: AssetRecord, replacement: AssetRecord) -> None:
    """Set an old record obsolete with the replacement recorded."""
    fields = old.model_dump()
    fields["status"] = AssetStatus.OBSOLETE
    fields["superseded_by"] = replacement.asset_id
    registry.update(AssetRecord.model_validate(fields))
