"""Asset dependencies: what uses what, deterministically (Phase 12).

An asset's dependencies are declared edges (``DependencyEdge``) - for
example an image depends on its workflow JSON, prompt pack, camera path,
and model; a video depends on its images and voice. This module stores
the edges, answers who-depends-on-whom both ways, detects cycles, and
finds the top-level (root) assets. Everything is a pure function of the
edge set, and edges are validated against the registry.
"""

from __future__ import annotations

from knowledge.asset_engine.asset_models import DependencyEdge
from knowledge.asset_engine.asset_registry import AssetRegistry


class AssetDependencies:
    """The deterministic dependency graph over one registry."""

    def __init__(self, registry: AssetRegistry) -> None:
        self._registry = registry
        self._edges: dict[str, list[DependencyEdge]] = {}
        self._reverse: dict[str, list[DependencyEdge]] = {}

    # ----------------------------------------------------------------- write --

    def add(
        self,
        *,
        dependent: str,
        dependency: str,
        kind: str = "uses",
        reason: str = "",
    ) -> DependencyEdge:
        """Declare one validated dependency edge (idempotent)."""
        self._registry.get(dependent)
        self._registry.get(dependency)
        edge = DependencyEdge(
            dependent=dependent,
            dependency=dependency,
            kind=kind,
            reason=reason,
        )
        key = f"{dependent}->{dependency}:{kind}"
        if any(f"{e.dependent}->{e.dependency}:{e.kind}" == key for e in self._edges.get(dependent, ())):
            return edge
        self._edges.setdefault(dependent, []).append(edge)
        self._reverse.setdefault(dependency, []).append(edge)
        return edge

    # ------------------------------------------------------------------ read --

    def dependencies_of(self, asset_id: str) -> tuple[DependencyEdge, ...]:
        """The direct edges from an asset to its dependencies."""
        return tuple(sorted(self._edges.get(asset_id, ()), key=_edge_key))

    def dependents_of(self, asset_id: str) -> tuple[DependencyEdge, ...]:
        """The direct edges from an asset to its dependents (reverse)."""
        return tuple(sorted(self._reverse.get(asset_id, ()), key=_edge_key))

    def transitive_dependencies(self, asset_id: str) -> tuple[str, ...]:
        """Every asset reachable from one asset (sorted, cycle-safe)."""
        visited: set[str] = set()
        queue = [dependency.dependency for dependency in self.dependencies_of(asset_id)]
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            queue.extend(
                edge.dependency for edge in self.dependencies_of(current)
            )
        return tuple(sorted(visited))

    def roots(self) -> tuple[str, ...]:
        """Assets nothing else depends on (the top-level assets)."""
        dependents = set(self._reverse)
        all_ids = set(self._registry.ids())
        return tuple(sorted(all_ids - dependents))

    def edge_count(self) -> int:
        """How many distinct edges are declared."""
        return sum(len(edges) for edges in self._edges.values())

    def has_cycle(self) -> bool:
        """Whether the graph contains any directed cycle."""
        visited: set[str] = set()
        stack: set[str] = set()

        def visit(asset_id: str) -> bool:
            if asset_id in stack:
                return True
            if asset_id in visited:
                return False
            stack.add(asset_id)
            for edge in self.dependencies_of(asset_id):
                if visit(edge.dependency):
                    return True
            stack.remove(asset_id)
            visited.add(asset_id)
            return False

        return any(visit(asset_id) for asset_id in self._registry.ids())


def _edge_key(edge: DependencyEdge) -> tuple[str, str, str]:
    return edge.dependent, edge.dependency, edge.kind
