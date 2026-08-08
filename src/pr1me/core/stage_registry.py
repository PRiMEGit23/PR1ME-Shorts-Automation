"""Stage registry.

Owns stage discovery and wiring only -- no execution logic. Responsibilities:

- register stages (instances or classes)
- resolve a stage by its ``stage_id``
- duplicate detection
- dependency validation
- pipeline execution-order computation (topological sort)
- pipeline validation

The registry is DI-friendly: classes are instantiated lazily through a caller
provided factory so stages can receive their :class:`StageContext`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from pr1me.core.base_stage import BaseStage, StageMetadata
from pr1me.core.context import StageContext
from pr1me.core.errors import (
    PipelineDependencyError,
    StageNotFoundError,
    StageRegistrationError,
)

StageT = TypeVar("StageT", bound=BaseStage[Any, Any])


class StageRegistry:
    """A registry of stage factories keyed by ``stage_id``.

    Accepts either concrete stage instances or stage classes. Classes are
    resolved into instances on demand through an optional ``factory``; when no
    factory is supplied, a stage is constructed with the registry's default
    ``context``.
    """

    def __init__(
        self,
        *,
        context: StageContext | None = None,
        factory: Callable[[type[BaseStage[Any, Any]]], BaseStage[Any, Any]] | None = None,
    ) -> None:
        self._context = context
        self._factory = factory
        self._stages: dict[str, BaseStage[Any, Any]] = {}
        self._factories: dict[str, Callable[[], BaseStage[Any, Any]]] = {}

    # ------------------------------------------------------------- register --

    def register(
        self,
        stage: BaseStage[Any, Any] | type[BaseStage[Any, Any]],
        *,
        replace: bool = False,
    ) -> BaseStage[Any, Any]:
        """Register a stage instance or class.

        :param stage: a stage instance or class.
        :param replace: allow overwriting an existing registration.
        :raises StageRegistrationError: on duplicate registration or an invalid
            ``stage_id``.
        """
        if isinstance(stage, type):
            stage_id = stage.stage_id
            factory = self._class_factory(stage)
        else:
            stage_id = stage.stage_id

            def factory() -> BaseStage[Any, Any]:
                return stage

        if not stage_id:
            raise StageRegistrationError("cannot register a stage without a stage_id")

        if stage_id in self._stages and not replace:
            raise StageRegistrationError(
                f"stage {stage_id!r} is already registered (duplicate registration)"
            )

        self._factories[stage_id] = factory
        self._stages[stage_id] = factory()
        return self._stages[stage_id]

    def unregister(self, stage_id: str) -> None:
        """Remove a stage from the registry. Raises if not present."""
        if stage_id not in self._stages:
            raise StageNotFoundError(f"stage {stage_id!r} is not registered")
        del self._stages[stage_id]
        del self._factories[stage_id]

    def register_all(
        self,
        stages: Iterable[BaseStage[Any, Any] | type[BaseStage[Any, Any]]],
        *,
        replace: bool = False,
    ) -> None:
        """Register several stages in one call."""
        for stage in stages:
            self.register(stage, replace=replace)

    # -------------------------------------------------------------- resolve --

    def resolve(self, stage_id: str) -> BaseStage[Any, Any]:
        """Resolve a stage instance by ``stage_id``.

        :raises StageNotFoundError: when the stage is unknown.
        """
        try:
            return self._stages[stage_id]
        except KeyError as exc:
            raise StageNotFoundError(f"stage {stage_id!r} is not registered") from exc

    def resolve_typed(self, stage_id: str, expected: type[StageT]) -> StageT:
        """Resolve a stage and assert it is an instance of ``expected``."""
        stage = self.resolve(stage_id)
        if not isinstance(stage, expected):
            raise StageNotFoundError(
                f"stage {stage_id!r} has type {type(stage).__name__}, expected {expected.__name__}"
            )
        return stage

    def __contains__(self, stage_id: object) -> bool:
        return stage_id in self._stages

    def get(self, stage_id: str) -> BaseStage[Any, Any] | None:
        """Resolve without raising."""
        return self._stages.get(stage_id)

    # ------------------------------------------------------------ inspection --

    @property
    def stage_ids(self) -> list[str]:
        """All registered stage ids in registration order."""
        return list(self._stages)

    def metadata(self, stage_id: str) -> StageMetadata:
        """Return typed metadata for a stage."""
        return self.resolve(stage_id).metadata()

    def all_metadata(self) -> dict[str, StageMetadata]:
        """Return metadata for every registered stage keyed by stage_id."""
        return {sid: self._stages[sid].metadata() for sid in self._stages}

    def dependencies(self, stage_id: str) -> tuple[str, ...]:
        """Return the declared upstream dependencies of a stage."""
        return tuple(self.resolve(stage_id).depends_on)

    # ------------------------------------------------------------- ordering --

    def execution_order(self, *, include: Iterable[str] | None = None) -> list[str]:
        """Topologically sort the registered stages by their dependencies.

        A dependency always appears before the stage that depends on it. Stages
        with no dependencies are ordered by registration order. ``include`` may
        restrict the sort to a subset; the result is the maximal valid prefix.

        :raises PipelineDependencyError: on unknown or cyclic dependencies.
        """
        selected = list(include) if include is not None else list(self._stages)
        self._validate_subset(selected)

        graph: dict[str, set[str]] = {sid: set(self.dependencies(sid)) & set(selected) for sid in selected}
        ordered: list[str] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(sid: str) -> None:
            if sid in visiting:
                raise PipelineDependencyError(
                    f"cyclic dependency detected involving stage {sid!r}"
                )
            if sid in visited:
                return
            visiting.add(sid)
            for dep in graph[sid]:
                if dep in selected:
                    visit(dep)
            visiting.remove(sid)
            visited.add(sid)
            ordered.append(sid)

        for sid in selected:
            visit(sid)
        return ordered

    def validate(self, *, include: Iterable[str] | None = None) -> None:
        """Validate the pipeline graph (dependencies + ordering).

        Raises on unknown dependencies, cycles, or unregistered include ids.
        Returns ``None`` on success.
        """
        self.execution_order(include=include)

    # ------------------------------------------------------------ internals --

    def _class_factory(
        self, stage_cls: type[BaseStage[Any, Any]]
    ) -> Callable[[], BaseStage[Any, Any]]:
        def build() -> BaseStage[Any, Any]:
            if self._factory is not None:
                return self._factory(stage_cls)
            if self._context is None:
                raise StageRegistrationError(
                    f"cannot instantiate {stage_cls.__name__}: "
                    "no context or factory was provided to the registry"
                )
            return stage_cls(context=self._context)

        return build

    def _validate_subset(self, selected: list[str]) -> None:
        registered = set(self._stages)
        missing = set(selected) - registered
        if missing:
            raise PipelineDependencyError(
                f"unknown stage(s) in pipeline: {sorted(missing)}"
            )
        for sid in selected:
            unknown = set(self.dependencies(sid)) - registered
            if unknown:
                raise PipelineDependencyError(
                    f"stage {sid!r} depends on unknown stage(s): {sorted(unknown)}"
                )