"""Context module: runtime pegboard and top-level operators."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Type, TYPE_CHECKING

from dvc_dat import Dat
from dvc_dat import do as dvc_do

if TYPE_CHECKING:
    from .entity import Entity
    from .io import IO as IOClass


@dataclass
class RuntimeContext:
    """Runtime pegboard for alienbio.

    Holds configuration, connections, and references to all major subsystems.
    Stored in a ContextVar for thread/async safety.

    Note: This is distinct from spec_lang.eval.EvalContext which is for
    spec evaluation. RuntimeContext is for runtime operations (DAT management,
    entity I/O, etc.).

    Note: For data path, use Dat.manager.sync_folder (single source of truth).
    """

    config: dict[str, Any] = field(default_factory=dict)
    _io: IOClass | None = field(default=None, repr=False)

    @property
    def io(self) -> IOClass:
        """Entity I/O: prefix bindings, formatting, lookup, persistence."""
        if self._io is None:
            from .io import IO
            self._io = IO()
        return self._io

    def do(self, name: str, *args, **kwargs) -> Any:
        """Execute a do-method by dotted name.

        Resolves the dotted name to a source code object and executes it.
        - If callable: calls it with args/kwargs
        - If dict: creates a DAT from it and runs it
        - If Dat: runs it
        """
        return dvc_do(name, *args, **kwargs)

    def create(self, spec: str | dict[str, Any], path: str | None = None) -> Dat:
        """Create a Dat from a spec.

        If spec is a string, loads it via dotted name from source code.
        Path can be specified explicitly or derived from spec's dat.name field.
        """
        return Dat.create(path=path, spec=spec)

    def load(self, path: str | Path) -> Dat:
        """Load a Dat from a data path."""
        return Dat.manager.load(Dat, str(path))

    def save(self, obj: Any, path: str | Path) -> Dat:
        """Save an object as a Dat to a data path."""
        if isinstance(obj, Dat):
            obj.save()
            return obj
        # Create a new Dat with the object as spec
        # Dat.create handles path resolution via Dat.manager.sync_folder
        spec = obj if isinstance(obj, dict) else {"value": obj}
        return Dat.create(path=str(path), spec=spec)

    def lookup(self, name: str) -> Entity:
        """Look up an entity by PREFIX:path string.

        Args:
            name: String in PREFIX:path format (e.g., "W:cytoplasm.glucose")

        Returns:
            The entity at the specified path
        """
        return self.io.lookup(name)

    def create_root(
        self,
        path: str,
        entity_type: Type[Entity] | None = None,
        **kwargs,
    ) -> Entity:
        """Create a new DAT with its root entity.

        This creates a DAT at the specified path and attaches a root entity to it.
        The root entity is the anchor for an entity tree - all other entities in
        the tree have parent chains leading back to this root.

        Cross-DAT references (e.g., a World referencing a Chemistry) are stored
        as references in the spec, not as parent-child relationships. This allows
        the same Chemistry to be referenced by multiple Worlds.

        Args:
            path: DAT path (e.g., "runs/exp1", "chem/kegg1")
            entity_type: Type of root entity to create (default: Entity)
            **kwargs: Passed to entity constructor (name, description, etc.)
                      If name not provided, uses last component of path.

        Returns:
            The root entity (with DAT attached via entity._dat)

        Example:
            world = create_root("runs/exp1", World, description="My experiment")
            cytoplasm = Compartment("cytoplasm", parent=world)
            world.save()  # Persists entire tree to runs/exp1/entities.yaml
        """
        from .entity import Entity as EntityClass

        if entity_type is None:
            entity_type = EntityClass

        name = kwargs.pop("name", path.rsplit("/", 1)[-1])
        dat = Dat.create(path=path, spec={"dat": {"kind": "Dat"}})
        return entity_type(name, dat=dat, **kwargs)


# Backward compat alias (prefer RuntimeContext for new code)
Context = RuntimeContext


# Global context variable
_ctx: ContextVar[RuntimeContext | None] = ContextVar("alienbio_context", default=None)


def ctx() -> RuntimeContext:
    """Access the runtime context.

    Returns the current RuntimeContext from the ContextVar.
    Creates a default RuntimeContext if none exists.
    """
    context = _ctx.get()
    if context is None:
        context = RuntimeContext()
        _ctx.set(context)
    return context


def set_context(context: RuntimeContext | None) -> None:
    """Set the runtime context."""
    _ctx.set(context)


def do(name: str, *args, **kwargs) -> Any:
    """Execute a do-method by dotted name."""
    return ctx().do(name, *args, **kwargs)


def create(spec: str | dict[str, Any], path: str | None = None) -> Dat:
    """Create a Dat from a spec."""
    return ctx().create(spec, path)


def load(path: str | Path) -> Dat:
    """Load a Dat from a data path."""
    return ctx().load(path)


def save(obj: Any, path: str | Path) -> Dat:
    """Save an object as a Dat to a data path."""
    return ctx().save(obj, path)


def lookup(name: str) -> Entity:
    """Look up an entity by PREFIX:path string."""
    return ctx().lookup(name)


def create_root(
    path: str,
    entity_type: Type[Entity] | None = None,
    **kwargs,
) -> Entity:
    """Create a new DAT with its root entity.

    See RuntimeContext.create_root for full documentation.
    """
    return ctx().create_root(path, entity_type, **kwargs)


class _ContextProxy:
    """Proxy for accessing context attributes directly."""

    def __getattr__(self, name: str) -> Any:
        return getattr(ctx(), name)


o = _ContextProxy()
