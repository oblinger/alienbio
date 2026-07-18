"""``mk`` — the maker pegboard: terse, env-aware entity construction.

Root entities need an anchor (a ``Dat`` or a ``parent``); in tests and
throwaway code that anchor is pure boilerplate derivable from the entity's
name (``MockDat("mol/A")`` for a molecule ``"A"``). ``mk`` removes it.

Each entity family registers a short **maker key** with the singleton
(``mk.register("M", prefix="mol", build=...)``); the pegboard then exposes a
dynamically-resolved accessor per key::

    a = mk.M("A")                       # MoleculeImpl("A", dat=MockDat("mol/A"))
    r = mk.R("R1", {a: 1.0}, {b: 1.0})  # reactants/products positional
    c = mk.C("world", [a, b], [r])      # name-keyed dicts derived from entities

**Env-aware anchoring.** When neither ``dat`` nor ``parent`` is passed, the
maker asks the current environment how to anchor:

- inside ``with mk.anchor(target): ...`` — attach to ``target`` (a real ``Dat``
  gives every new entity that ``dat``; a parent ``Entity`` makes them children);
- otherwise — mint a ``MockDat(f"{prefix}/{local_name}")``.

The same ``mk.M("A")`` call therefore works unchanged in a bare test (MockDat)
and under a real catalog root (production). An explicit ``dat=`` / ``parent=``
always wins over the ambient environment.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from .entity import Entity, MockDat

# A maker builds one entity: build(local_name, anchor, *args, **kwargs) -> Entity,
# where ``anchor`` is the resolved {"dat": ...} or {"parent": ...} kwargs to splat.
Maker = Callable[..., Entity]


@dataclass(frozen=True)
class _Registration:
    key: str
    prefix: str
    build: Maker


class Pegboard:
    """Singleton registry of entity makers with an ambient anchor stack."""

    def __init__(self) -> None:
        self._registry: dict[str, _Registration] = {}
        self._anchor_stack: list[Any] = []

    def register(self, key: str, *, prefix: str, build: Maker) -> None:
        """Register a maker under ``key`` (e.g. ``"M"``) with an anchor ``prefix``.

        Idempotent for an identical re-registration (module re-import); a
        conflicting re-registration under the same key is an error.
        """
        existing = self._registry.get(key)
        if existing is not None and existing.build is not build:
            raise ValueError(
                f"maker key {key!r} already registered to {existing.build!r}"
            )
        self._registry[key] = _Registration(key, prefix, build)

    def registered_keys(self) -> list[str]:
        """The maker keys currently registered (sorted)."""
        return sorted(self._registry)

    @contextmanager
    def anchor(self, target: Entity | Any) -> Iterator[Any]:
        """Within this block, makers anchor new entities to ``target``.

        ``target`` is a parent ``Entity`` (new entities become its children) or
        a ``Dat`` (new entities take it as their root anchor). Nestable.
        """
        self._anchor_stack.append(target)
        try:
            yield target
        finally:
            self._anchor_stack.pop()

    def _anchor_for(self, prefix: str, local_name: str) -> dict[str, Any]:
        """Resolve the anchor kwargs for a new entity in the current environment."""
        if self._anchor_stack:
            target = self._anchor_stack[-1]
            if isinstance(target, Entity):
                return {"parent": target}
            return {"dat": target}
        return {"dat": MockDat(f"{prefix}/{local_name}")}

    def __getattr__(self, key: str) -> Callable[..., Entity]:
        # Only reached when normal attribute lookup misses; the real slots
        # (_registry, _anchor_stack) never land here, so no recursion.
        registry = self.__dict__.get("_registry", {})
        reg = registry.get(key)
        if reg is None:
            raise AttributeError(
                f"mk has no maker {key!r}; registered makers: {sorted(registry)}"
            )

        def make(
            local_name: str,
            *args: Any,
            dat: Any = None,
            parent: Entity | None = None,
            **kwargs: Any,
        ) -> Entity:
            if dat is not None:
                anchor = {"dat": dat}
            elif parent is not None:
                anchor = {"parent": parent}
            else:
                anchor = self._anchor_for(reg.prefix, local_name)
            return reg.build(local_name, anchor, *args, **kwargs)

        make.__name__ = f"mk.{key}"
        make.__qualname__ = f"mk.{key}"
        return make


# The one pegboard assumed to be in the environment.
mk = Pegboard()
