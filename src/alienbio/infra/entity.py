"""Entity module: base class for all biology objects."""

from __future__ import annotations

from typing import Any, ClassVar, Dict, Iterator, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from dvc_dat import Dat


# Type registry for Entity subclasses
_entity_registry: Dict[str, Type["Entity"]] = {}


def register_entity_type(name: str, cls: Type["Entity"]) -> None:
    """Register an entity type by name.

    Called automatically by Entity subclasses via __init_subclass__.
    Can also be called manually for dynamic registration.

    Args:
        name: Short name for the type (used in serialization)
        cls: The Entity subclass to register
    """
    _entity_registry[name] = cls


def get_entity_type(name: str) -> Type["Entity"]:
    """Look up entity type by name.

    Args:
        name: Registered type name

    Returns:
        The Entity subclass

    Raises:
        KeyError: If type name not registered
    """
    if name not in _entity_registry:
        raise KeyError(f"Unknown entity type: {name!r}")
    return _entity_registry[name]


def get_entity_types() -> Dict[str, Type["Entity"]]:
    """Get all registered entity types (read-only copy)."""
    return _entity_registry.copy()


def _get_type_name(cls: Type["Entity"]) -> str:
    """Get the registered type name for an Entity class.

    Searches the registry for the class and returns its registered name.
    Falls back to __name__ if not found (shouldn't happen).
    """
    for name, registered_cls in _entity_registry.items():
        if registered_cls is cls:
            return name
    return cls.__name__


class Entity:
    """Base class for all biology objects.

    Entities form a tree structure with bidirectional links:
    - _parent: link to containing entity
    - _children: dict of child entities by local name
    - _top: either a Dat (for root entities) or the root Entity (for non-roots)

    The _top field enables O(1) access to both root() and dat().
    Names are derived by walking up the parent chain until a DAT anchor
    is found, then building the qualified path.
    """

    __slots__ = ("_local_name", "_parent", "_children", "_top", "description")

    def __init_subclass__(cls, type_name: Optional[str] = None, **kwargs) -> None:
        """Auto-register subclasses in the type registry.

        Args:
            type_name: Optional short name for serialization.
                       If not provided, uses the class name.

        Example:
            class Molecule(Entity):  # registers as "Molecule"
                pass

            class Molecule(Entity, type_name="M"):  # registers as "M"
                pass
        """
        super().__init_subclass__(**kwargs)
        name = type_name if type_name else cls.__name__
        register_entity_type(name, cls)

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
            ValueError: If name contains spaces
        """
        if parent is None and dat is None:
            raise ValueError(
                f"Entity {name!r} must have either a parent or a DAT anchor"
            )

        if " " in name:
            raise ValueError(
                f"Entity name {name!r} contains spaces; names must be valid identifiers"
            )

        self._local_name = name
        self._parent: Optional[Entity] = None
        self._children: Dict[str, Entity] = {}
        self.description = description

        # Set _top: Dat for root entities, root Entity for non-roots
        if dat is not None:
            self._top: Entity | Dat = dat
        else:
            # Will be set properly in set_parent()
            self._top = parent.root()  # type: ignore[union-attr]

        # Set parent (which also registers us as a child and updates _top)
        if parent is not None:
            self.set_parent(parent)

    @property
    def local_name(self) -> str:
        """Name within parent's children dict."""
        return self._local_name

    @property
    def parent(self) -> Optional[Entity]:
        """Link to containing entity."""
        return self._parent

    @property
    def children(self) -> Dict[str, Entity]:
        """Child entities by local name (read-only view)."""
        return self._children.copy()

    def dat(self) -> Dat:
        """Get the DAT anchor for this entity's tree.

        O(1) operation using the _top field.
        """
        if not isinstance(self._top, Entity):
            return self._top  # I am the root (_top is a Dat)
        # _top is the root Entity, get its DAT
        return self._top._top  # type: ignore[return-value]

    def root(self) -> Entity:
        """Get the root entity (the ancestor with the DAT anchor).

        O(1) operation using the _top field.
        """
        if not isinstance(self._top, Entity):
            return self  # I am the root (_top is a Dat)
        return self._top  # Direct pointer to root

    def set_parent(self, parent: Optional[Entity]) -> None:
        """Set the parent entity.

        Handles registration/deregistration in parent's children dict.
        Updates _top for this entity and all descendants.

        If parent is None, reparents to orphan root (entities are never invalid).
        """
        # Remove from old parent's children
        if self._parent is not None:
            self._parent._children.pop(self._local_name, None)

        # If parent is None, reparent to orphan root instead
        if parent is None:
            from .context import ctx
            parent = ctx().io.orphan_root

        self._parent = parent

        # Add to new parent's children and update _top
        if self._local_name in parent._children:
            raise ValueError(
                f"Parent already has child named {self._local_name!r}"
            )
        parent._children[self._local_name] = self
        # Update _top for this subtree to point to new root
        self._update_top(parent.root())

    def detach(self) -> None:
        """Detach this entity from its parent.

        The entity is reparented to the orphan root and remains fully valid.
        It can be re-attached later using set_parent().

        Prints as ORPHAN:name after detaching.
        """
        from .context import ctx
        self.set_parent(ctx().io.orphan_root)

    def _update_top(self, new_root: Entity) -> None:
        """Update _top for this entity and all descendants.

        Called when reparenting to maintain the _top invariant.
        """
        # Don't update if this entity has its own DAT (is a sub-root)
        if not isinstance(self._top, Entity):
            return

        self._top = new_root
        for child in self._children.values():
            child._update_top(new_root)

    @property
    def full_name(self) -> str:
        """Full path from DAT anchor (e.g., 'runs/exp1.cytoplasm.glucose').

        Walks up the parent chain until a DAT anchor is found,
        then builds the path from there.
        """
        if not isinstance(self._top, Entity):
            return self._top.get_path_name()  # I am root, _top is Dat
        return f"{self._parent.full_name}.{self._local_name}"

    def to_dict(self, recursive: bool = False, _root: Optional[Entity] = None) -> Dict[str, Any]:
        """Convert entity to dictionary representation for serialization.

        Args:
            recursive: If True, include children recursively
            _root: Internal - the root entity we're serializing from (to detect
                   children with different roots that need absolute refs)

        Returns:
            Dict with entity fields suitable for YAML/JSON serialization.
        """
        result: Dict[str, Any] = {
            "type": _get_type_name(type(self)),
            "name": self._local_name,
        }
        if self.description:
            result["description"] = self.description

        if recursive and self._children:
            # Track the root entity for this serialization
            if _root is None:
                _root = self.root()

            children_dict: Dict[str, Any] = {}
            for name, child in self._children.items():
                child_root = child.root()
                if child_root is not _root:
                    # Child belongs to a different DAT - use absolute ref
                    # Import here to avoid circular import
                    from . import context
                    children_dict[name] = context.ctx().io.ref(child, absolute=True)
                else:
                    # Same DAT - inline the child
                    children_dict[name] = child.to_dict(recursive=True, _root=_root)
            result["children"] = children_dict

        # Subclasses should override to add their own fields
        return result

    def to_str(self, depth: int = -1) -> str:
        """String representation of entity tree.

        Returns a function-call style representation showing the entity
        and optionally its children.

        Args:
            depth: How deep to recurse into children.
                   -1 = unlimited, 0 = just this entity,
                   1 = include immediate children, etc.

        Returns:
            String like "World(Cytoplasm(Glucose, ATP), Nucleus)"

        Example:
            entity.to_str()      # full tree
            entity.to_str(0)     # just "World"
            entity.to_str(1)     # "World(Cytoplasm, Nucleus)"
        """
        if not self._children or depth == 0:
            return self._local_name

        next_depth = -1 if depth == -1 else depth - 1
        children_str = ", ".join(
            child.to_str(next_depth) for child in self._children.values()
        )
        return f"{self._local_name}({children_str})"

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

    def save(self) -> None:
        """Save this entity tree to disk.

        Must be called on the root entity (the one with the DAT anchor).
        Serializes the entire entity tree to entities.yaml in the DAT folder.

        Raises:
            ValueError: If not called on a root entity
        """
        import yaml
        from pathlib import Path

        if isinstance(self._top, Entity) or self._top is None:
            raise ValueError(
                f"save() must be called on root entity. "
                f"Use self.root().save() instead."
            )

        dat = self._top

        # Serialize the entity tree
        entity_data = self.to_dict(recursive=True)

        # Write to entities.yaml in DAT folder
        dat_path = Path(dat.get_path())
        entities_file = dat_path / "entities.yaml"
        with open(entities_file, "w") as f:
            yaml.dump(entity_data, f, default_flow_style=False, sort_keys=False)

        # Also save the DAT's spec
        dat.save()

    def __repr__(self) -> str:
        """Full reconstructible representation."""
        parts = [f"name={self._local_name!r}"]
        if self.description:
            parts.append(f"description={self.description!r}")
        if not isinstance(self._top, Entity) and self._top is not None:
            parts.append(f"dat={self._top.get_path_name()!r}")
        if self._parent is not None:
            parts.append(f"parent={self._parent._local_name!r}")
        if self._children:
            parts.append(f"children={list(self._children.keys())}")
        return f"Entity({', '.join(parts)})"

    def __str__(self) -> str:
        """Short display form using PREFIX:path if context available.

        Falls back to full_name if no context or prefix matches.
        """
        try:
            from .context import ctx

            return ctx().io.ref(self)
        except Exception:
            # Fall back to full_name if context not available
            try:
                return self.full_name
            except ValueError:
                return f"<Entity:{self._local_name}>"


# Register the base Entity class (since __init_subclass__ only fires for subclasses)
register_entity_type("Entity", Entity)
