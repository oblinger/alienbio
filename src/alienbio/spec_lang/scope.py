"""Scope class for lexical scoping in spec files.

A Scope is a dict with a parent chain, enabling lexical scoping
where lookups climb the hierarchy until a value is found.

Usage:
    root = Scope({"x": 1, "y": 2})
    child = root.child({"y": 3, "z": 4})

    child["x"]  # -> 1 (inherited from root)
    child["y"]  # -> 3 (overridden in child)
    child["z"]  # -> 4 (defined in child)
"""

from __future__ import annotations
from typing import Any, Iterator


class Scope(dict):
    """A dict with lexical scoping (parent chain lookup).

    Variables are inherited through the scope chain. Lookups check the
    current scope first, then climb to parent scopes until found.

    The scope hierarchy is built at load time (via `extends:` in YAML),
    but variable lookups are dynamic - they climb the hierarchy at
    access time.

    Attributes:
        parent: Optional parent Scope for inheritance chain
        name: Optional name for this scope (for debugging)
    """

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        parent: Scope | None = None,
        name: str | None = None,
    ):
        """Create a new Scope.

        Args:
            data: Initial dict content
            parent: Parent scope for inheritance
            name: Optional name for debugging
        """
        super().__init__(data or {})
        self.parent = parent
        self.name = name

    def __getitem__(self, key: str) -> Any:
        """Get item, climbing parent chain if not found locally."""
        if key in self.keys():
            return super().__getitem__(key)
        if self.parent is not None:
            return self.parent[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Get item with default, climbing parent chain."""
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        """Check if key exists in this scope or any parent."""
        if super().__contains__(key):
            return True
        if self.parent is not None:
            return key in self.parent
        return False

    def local_keys(self) -> Iterator[str]:
        """Return keys defined directly in this scope (not inherited)."""
        return iter(super().keys())

    def all_keys(self) -> set[str]:
        """Return all keys including inherited ones."""
        keys = set(super().keys())
        if self.parent is not None:
            keys |= self.parent.all_keys()
        return keys

    def child(self, data: dict[str, Any] | None = None, name: str | None = None) -> Scope:
        """Create a child scope that inherits from this one.

        Args:
            data: Initial content for child scope
            name: Optional name for the child scope

        Returns:
            New Scope with this scope as parent
        """
        return Scope(data, parent=self, name=name)

    def resolve(self, key: str) -> tuple[Any, Scope | None]:
        """Resolve a key and return (value, defining_scope).

        Useful for debugging to see where a value comes from.

        Args:
            key: The key to look up

        Returns:
            Tuple of (value, scope_that_defined_it)

        Raises:
            KeyError: If key not found in any scope
        """
        if key in self.keys():
            return super().__getitem__(key), self
        if self.parent is not None:
            return self.parent.resolve(key)
        raise KeyError(key)

    def __repr__(self) -> str:
        name_part = f" {self.name!r}" if self.name else ""
        parent_part = f" parent={self.parent.name!r}" if self.parent and self.parent.name else ""
        if not parent_part and self.parent:
            parent_part = " parent=<Scope>"
        return f"<Scope{name_part}{parent_part} {dict(self)}>"
