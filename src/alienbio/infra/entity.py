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
    - _dat: optional anchor to filesystem (DAT)

    Names are derived by walking up the parent chain until a DAT anchor
    is found, then building the qualified path.
    """

    __slots__ = ("_local_name", "_parent", "_children", "_dat", "description")

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
        self._dat: Optional[Dat] = dat
        self.description = description

        # Set parent (which also registers us as a child)
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
    def full_name(self) -> str:
        """Full path from DAT anchor (e.g., 'runs/exp1.cytoplasm.glucose').

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
        return f"{self._parent.full_name}.{self._local_name}"

    def to_dict(self, recursive: bool = False, _root_dat: Optional[Dat] = None) -> Dict[str, Any]:
        """Convert entity to dictionary representation for serialization.

        Args:
            recursive: If True, include children recursively
            _root_dat: Internal - the DAT we're serializing from (to detect
                       children with different DATs that need absolute refs)

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
            # Track the root DAT for this serialization
            if _root_dat is None:
                _root_dat = self.find_dat_anchor()

            children_dict: Dict[str, Any] = {}
            for name, child in self._children.items():
                child_dat = child.find_dat_anchor()
                if child_dat is not None and child_dat is not _root_dat:
                    # Child belongs to a different DAT - use absolute ref
                    # Import here to avoid circular import
                    from . import context
                    children_dict[name] = context.ctx().io.ref(child, absolute=True)
                else:
                    # Same DAT - inline the child
                    children_dict[name] = child.to_dict(recursive=True, _root_dat=_root_dat)
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

    def save(self) -> None:
        """Save this entity's DAT to disk.

        Finds the nearest DAT anchor, then serializes the entire entity tree
        rooted at that DAT to entities.yaml.

        Raises:
            ValueError: If entity has no DAT anchor
        """
        import yaml
        from pathlib import Path

        dat = self.find_dat_anchor()
        if dat is None:
            raise ValueError(
                f"Entity {self._local_name!r} has no DAT anchor to save"
            )

        # Find the root entity that owns this DAT
        root_entity = self._find_dat_root_entity(dat)

        # Serialize the entity tree
        entity_data = root_entity.to_dict(recursive=True)

        # Write to entities.yaml in DAT folder
        dat_path = Path(dat.get_path())
        entities_file = dat_path / "entities.yaml"
        with open(entities_file, "w") as f:
            yaml.dump(entity_data, f, default_flow_style=False, sort_keys=False)

        # Also save the DAT's spec
        dat.save()

    def _find_dat_root_entity(self, dat: Dat) -> Entity:
        """Find the entity that directly owns the given DAT.

        Walks up the tree to find the entity where entity.dat is dat.
        """
        current: Optional[Entity] = self
        while current is not None:
            if current._dat is dat:
                return current
            current = current._parent
        # Should not happen if dat came from find_dat_anchor
        return self

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
