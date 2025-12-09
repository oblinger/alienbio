"""Entity module: base class for all biology objects."""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from dvc_dat import Dat


class Entity:
    """Base class for all biology objects.

    Entities form a tree structure with bidirectional links:
    - _parent: link to containing entity
    - _children: dict of child entities by local name
    - _dat: optional anchor to filesystem (DAT)

    Names are derived by walking up the parent chain until a DAT anchor
    is found, then building the qualified path.
    """

    __slots__ = ("_local_name", "_parent", "_children", "_dat", "description")

    def __init__(
        self,
        name: str,
        *,
        parent: Optional[Entity] = None,
        dat: Optional[Dat] = None,
        description: str = "",
    ) -> None:
        """Initialize an entity.

        Args:
            name: Local name within parent's children dict
            parent: Link to containing entity (optional if dat provided)
            dat: DAT anchor to filesystem (optional if parent provided)
            description: Human-readable description

        Raises:
            ValueError: If neither parent nor dat is provided
        """
        if parent is None and dat is None:
            raise ValueError("Entity must have either a parent or a DAT anchor")

        self._local_name = name
        self._parent: Optional[Entity] = None
        self._children: Dict[str, Entity] = {}
        self._dat: Optional[Dat] = dat
        self.description = description

        # Set parent (which also registers us as a child)
        if parent is not None:
            self.set_parent(parent)

    @property
    def name(self) -> str:
        """Local name within parent's children dict."""
        return self._local_name

    @property
    def parent(self) -> Optional[Entity]:
        """Link to containing entity."""
        return self._parent

    @property
    def children(self) -> Dict[str, Entity]:
        """Child entities by local name (read-only view)."""
        return self._children.copy()

    @property
    def dat(self) -> Optional[Dat]:
        """DAT anchor to filesystem."""
        return self._dat

    def set_parent(self, parent: Optional[Entity]) -> None:
        """Set the parent entity.

        Handles registration/deregistration in parent's children dict.
        """
        # Remove from old parent's children
        if self._parent is not None:
            self._parent._children.pop(self._local_name, None)

        self._parent = parent

        # Add to new parent's children
        if parent is not None:
            if self._local_name in parent._children:
                raise ValueError(
                    f"Parent already has child named {self._local_name!r}"
                )
            parent._children[self._local_name] = self

    def set_dat(self, dat: Optional[Dat]) -> None:
        """Set the DAT anchor."""
        self._dat = dat

    @property
    def qualified_name(self) -> str:
        """Full path computed by walking up to DAT anchor.

        Walks up the parent chain until a DAT anchor is found,
        then builds the path from there.

        Raises:
            ValueError: If no DAT anchor found in ancestry
        """
        if self._dat is not None:
            return self._dat.get_path_name()
        if self._parent is None:
            raise ValueError(
                f"Entity {self._local_name!r} has no DAT anchor and no parent"
            )
        return f"{self._parent.qualified_name}.{self._local_name}"

    def lookup(self, path: str) -> Entity:
        """Find child entity by relative dotted path.

        Args:
            path: Dotted path like "compartment.glucose"

        Returns:
            The entity at the given path

        Raises:
            KeyError: If path not found
        """
        if not path:
            return self

        parts = path.split(".", 1)
        name = parts[0]

        if name not in self._children:
            raise KeyError(f"No child named {name!r} in {self._local_name!r}")

        child = self._children[name]
        if len(parts) == 1:
            return child
        return child.lookup(parts[1])

    def add_child(self, child: Entity) -> Entity:
        """Add a child entity.

        Sets this entity as the child's parent.

        Args:
            child: Entity to add as child

        Returns:
            The child entity (for chaining)

        Raises:
            ValueError: If child name already exists
        """
        child.set_parent(self)
        return child

    def remove_child(self, name: str) -> Optional[Entity]:
        """Remove a child entity by name.

        Args:
            name: Local name of child to remove

        Returns:
            The removed child, or None if not found
        """
        child = self._children.get(name)
        if child is not None:
            child._parent = None
            del self._children[name]
        return child

    def root(self) -> Entity:
        """Get the root entity (topmost ancestor)."""
        if self._parent is None:
            return self
        return self._parent.root()

    def ancestors(self) -> Iterator[Entity]:
        """Iterate over ancestors from parent to root."""
        current = self._parent
        while current is not None:
            yield current
            current = current._parent

    def descendants(self) -> Iterator[Entity]:
        """Iterate over all descendants (depth-first)."""
        for child in self._children.values():
            yield child
            yield from child.descendants()

    def find_dat_anchor(self) -> Optional[Dat]:
        """Find the nearest DAT anchor walking up the tree."""
        if self._dat is not None:
            return self._dat
        if self._parent is not None:
            return self._parent.find_dat_anchor()
        return None

    def __repr__(self) -> str:
        """Full reconstructible representation."""
        parts = [f"name={self._local_name!r}"]
        if self.description:
            parts.append(f"description={self.description!r}")
        if self._dat is not None:
            parts.append(f"dat={self._dat.get_path_name()!r}")
        if self._parent is not None:
            parts.append(f"parent={self._parent._local_name!r}")
        if self._children:
            parts.append(f"children={list(self._children.keys())}")
        return f"Entity({', '.join(parts)})"

    def __str__(self) -> str:
        """Short display form using qualified name."""
        try:
            return self.qualified_name
        except ValueError:
            return f"<Entity:{self._local_name}>"
