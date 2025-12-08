"""Context module: runtime pegboard and top-level operators."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Context:
    """Runtime pegboard for alienbio.

    Holds configuration, connections, and references to all major subsystems.
    Stored in a ContextVar for thread/async safety.
    """

    config: dict[str, Any] = field(default_factory=dict)
    data_path: Path = field(default_factory=lambda: Path("data"))

    def do(self, name: str) -> Any:
        """Resolve a dotted name to an object."""
        # TODO: Integrate with dvc_dat for full resolution
        parts = name.split(".")
        # For now, return a placeholder
        return {"_name": name, "_parts": parts}

    def create(self, spec: str | dict[str, Any]) -> Any:
        """Instantiate an object from a prototype specification."""
        if isinstance(spec, str):
            proto = self.do(spec)
            return {"_proto": spec, "_resolved": proto}
        return {"_proto": spec.get("_proto"), "_spec": spec}

    def load(self, path: str | Path) -> Any:
        """Load an entity from a data path."""
        full_path = self.data_path / path
        # TODO: Read _spec.yaml and reconstruct object
        return {"_path": str(full_path), "_loaded": True}

    def save(self, obj: Any, path: str | Path) -> None:
        """Save an entity to a data path."""
        full_path = self.data_path / path
        full_path.mkdir(parents=True, exist_ok=True)
        # TODO: Write _spec.yaml with object serialization
        spec_file = full_path / "_spec.yaml"
        spec_file.write_text(f"# Saved object\nname: {path}\n")


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


def do(name: str) -> Any:
    """Resolve a dotted name to an object."""
    return ctx().do(name)


def create(spec: str | dict[str, Any]) -> Any:
    """Instantiate an object from a prototype specification."""
    return ctx().create(spec)


def load(path: str | Path) -> Any:
    """Load an entity from a data path."""
    return ctx().load(path)


def save(obj: Any, path: str | Path) -> None:
    """Save an entity to a data path."""
    return ctx().save(obj, path)


class _ContextProxy:
    """Proxy for accessing context attributes directly."""

    def __getattr__(self, name: str) -> Any:
        return getattr(ctx(), name)


o = _ContextProxy()
