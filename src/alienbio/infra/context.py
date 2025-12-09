"""Context module: runtime pegboard and top-level operators."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from dvc_dat import Dat
from dvc_dat import do as dvc_do

if TYPE_CHECKING:
    from .entity import Entity
    from .io import IO as IOClass


@dataclass
class Context:
    """Runtime pegboard for alienbio.

    Holds configuration, connections, and references to all major subsystems.
    Stored in a ContextVar for thread/async safety.

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


# Global context variable
_ctx: ContextVar[Context | None] = ContextVar("alienbio_context", default=None)


def ctx() -> Context:
    """Access the runtime context.

    Returns the current Context from the ContextVar.
    Creates a default Context if none exists.
    """
    context = _ctx.get()
    if context is None:
        context = Context()
        _ctx.set(context)
    return context


def set_context(context: Context | None) -> None:
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


class _ContextProxy:
    """Proxy for accessing context attributes directly."""

    def __getattr__(self, name: str) -> Any:
        return getattr(ctx(), name)


o = _ContextProxy()
