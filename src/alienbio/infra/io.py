"""IO module: entity naming, formatting, parsing, and persistence."""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from dvc_dat import Dat

if TYPE_CHECKING:
    from .entity import Entity


# Module-level IO singleton via ContextVar for thread/async safety
_io_var: ContextVar[Optional["IO"]] = ContextVar("alienbio_io", default=None)


def io() -> "IO":
    """Get the current IO instance.

    Returns the IO from the ContextVar, creating a default instance if needed.
    This is the primary way to access entity I/O functionality.

    Returns:
        The current IO instance
    """
    instance = _io_var.get()
    if instance is None:
        instance = IO()
        _io_var.set(instance)
    return instance


def set_io(instance: Optional["IO"]) -> None:
    """Set the current IO instance.

    Use this in tests to inject a fresh IO instance.

    Args:
        instance: IO instance to set, or None to clear
    """
    _io_var.set(instance)


class _RootEntity:
    """Virtual entity representing the data root.

    This allows the 'D:' prefix to work without requiring a _spec_.yaml
    at the data root. Children are loaded from DAT paths on demand.
    """

    def __init__(self) -> None:
        self._local_name = ""
        self._parent = None
        self._dat = None
        self._children: Dict[str, Entity] = {}

    @property
    def local_name(self) -> str:
        return self._local_name

    @property
    def full_name(self) -> str:
        return Dat.manager.sync_folder.rstrip("/")

    @property
    def parent(self) -> None:
        return None

    @property
    def children(self) -> Dict[str, Entity]:
        return self._children.copy()


class _OrphanDat:
    """Virtual DAT for orphaned entities.

    Orphaned entities are detached from their original tree but remain
    fully functional. They can be inspected, printed (showing ORPHAN:path),
    and re-attached to another tree later.

    This DAT cannot be saved - it exists only to keep orphaned entities valid.
    """

    def get_path_name(self) -> str:
        return "<orphans>"

    def get_path(self) -> str:
        return "<orphans>"

    def save(self) -> None:
        raise ValueError("Cannot save orphan entities - re-attach them first")


class IO:
    """Entity I/O: naming, formatting, lookup, and persistence.

    IO handles all external representation concerns for entities:
    - Prefix bindings: Maps short prefixes (R:, W:) to Entity or path string
    - Formatting: Converts entities to PREFIX:path strings
    - Lookup: Converts PREFIX:path strings back to entities
    - Persistence: Load/save entities via DAT

    The 'D:' prefix is always bound to the data root as an escape hatch.

    Note: For data path, use Dat.manager.sync_folder (single source of truth).
    """

    def __init__(self) -> None:
        """Initialize IO."""
        self._prefixes: Dict[str, Entity | str] = {}
        self._path_entity_cache: Dict[str, Entity] = {}
        self._dat_entity_cache: Dict[str, Entity] = {}  # DAT path -> root entity
        self._root_entity: Optional[_RootEntity] = None
        self._orphan_dat: Optional[_OrphanDat] = None
        self._orphan_root: Optional[Entity] = None

    @property
    def _data_root(self) -> _RootEntity:
        """Lazy-initialized root entity for D: prefix."""
        if self._root_entity is None:
            self._root_entity = _RootEntity()
        return self._root_entity

    @property
    def orphan_root(self) -> Entity:
        """Lazy-initialized root entity for orphaned entities.

        Detached entities are re-parented here instead of becoming invalid.
        The ORPHAN: prefix is automatically bound to this root.
        """
        if self._orphan_root is None:
            from .entity import Entity
            self._orphan_dat = _OrphanDat()
            self._orphan_root = Entity("orphans", dat=self._orphan_dat)
            self._prefixes["ORPHAN"] = self._orphan_root
        return self._orphan_root

    @property
    def prefixes(self) -> Dict[str, Entity | str]:
        """Current prefix bindings (read-only copy)."""
        return self._prefixes.copy()

    def bind_prefix(self, prefix: str, target: Entity | str) -> None:
        """Bind a prefix to an entity or path string.

        Args:
            prefix: Short prefix string (e.g., "R", "W", "M")
            target: Entity to bind, or path string to DAT location

        Example:
            io.bind_prefix("W", world_entity)       # bind to Entity
            io.bind_prefix("R", "runs/experiment1") # bind to path
        """
        self._prefixes[prefix] = target

    def unbind_prefix(self, prefix: str) -> Optional[Entity | str]:
        """Remove a prefix binding.

        Args:
            prefix: Prefix to unbind

        Returns:
            The previously bound target, or None if not bound
        """
        return self._prefixes.pop(prefix, None)

    def resolve_prefix(self, prefix: str) -> Entity:
        """Get the entity bound to a prefix.

        If prefix is bound to a path string, loads/creates an Entity for it.
        The special prefix 'D' always resolves to the data root.

        Args:
            prefix: Prefix to resolve

        Returns:
            The entity bound to this prefix

        Raises:
            KeyError: If prefix is not bound
        """
        # Special case: D always resolves to data root
        if prefix == "D":
            return self._data_root

        if prefix not in self._prefixes:
            raise KeyError(f"Prefix {prefix!r} is not bound")

        target = self._prefixes[prefix]

        if isinstance(target, str):
            return self._resolve_path_to_entity(target)

        return target

    def _resolve_path_to_entity(self, path: str) -> Entity:
        """Resolve a path string to an Entity, caching the result.

        Args:
            path: Path to DAT location

        Returns:
            Entity wrapping the DAT at that path
        """
        if path in self._path_entity_cache:
            return self._path_entity_cache[path]

        # Import here to avoid circular import
        from .entity import Entity

        # Load the DAT and create an Entity wrapper
        dat = Dat.load(path)
        # Use the last path component as the entity name
        name = Path(path).name
        entity = Entity(name, dat=dat)

        self._path_entity_cache[path] = entity
        return entity

    def ref(
        self, entity: Entity, prefer_short: bool = True, absolute: bool = False
    ) -> str:
        """Get reference string for entity.

        Args:
            entity: Entity to get reference for
            prefer_short: If True, uses shortest matching prefix (ignored if absolute)
            absolute: If True, returns absolute format </dat/path.entity.path>

        Returns:
            String in PREFIX:path format (e.g., "W:cytoplasm.glucose")
            or absolute format (e.g., "</runs/exp1.cytoplasm.glucose>")

        Example:
            io.ref(glucose)                # -> "W:cytoplasm.glucose"
            io.ref(glucose, absolute=True) # -> "</runs/exp1.cytoplasm.glucose>"
        """
        if absolute:
            return self._absolute_ref(entity)

        # Find which prefixes match this entity's ancestry
        matches: list[tuple[str, str]] = []  # (prefix, remaining_path)

        # Check user-bound prefixes
        for prefix, target in self._prefixes.items():
            resolved = self.resolve_prefix(prefix)
            path = self._relative_path(entity, resolved)
            if path is not None:
                matches.append((prefix, path))

        # Always check D: prefix (data root) as fallback
        d_path = self._relative_path(entity, self._data_root)
        if d_path is not None:
            matches.append(("D", d_path))

        if not matches:
            # No prefix matches, use full name
            return entity.full_name

        if prefer_short:
            # Sort by path length (shortest first)
            matches.sort(key=lambda x: len(x[1]))

        prefix, path = matches[0]
        if path:
            return f"{prefix}:{path}"
        return f"{prefix}:"

    def _absolute_ref(self, entity: Entity) -> str:
        """Get absolute reference string for entity.

        Format: </dat/path.entity.path>
        - dat/path is the filesystem path to the DAT
        - entity.path is the dotted path from DAT root to entity

        Example: </runs/exp1.cytoplasm.glucose>
        """
        # Get the root entity and its DAT (both O(1))
        root = entity.root()
        dat = root.dat()
        if dat is None:
            raise ValueError(
                f"Entity {entity.local_name!r} has no DAT anchor for absolute ref"
            )

        dat_path = dat.get_path_name()

        # Build entity path from root to this entity
        entity_parts: list[str] = []
        current: Optional[Entity] = entity

        while current is not None and current is not root:
            entity_parts.append(current.local_name)
            current = current.parent

        entity_parts.reverse()
        entity_path = ".".join(entity_parts)

        if entity_path:
            return f"</{dat_path}.{entity_path}>"
        return f"</{dat_path}>"

    def _relative_path(self, entity: Entity, ancestor: Entity) -> Optional[str]:
        """Compute relative path from ancestor to entity.

        Returns None if ancestor is not in entity's ancestry.
        Returns "" if entity is the ancestor.
        Returns dotted path otherwise.

        Special handling for _RootEntity: matches based on full_name prefix.
        """
        if entity is ancestor:
            return ""

        # Special handling for _RootEntity (virtual data root)
        if isinstance(ancestor, _RootEntity):
            try:
                entity_path = entity.full_name
                root_path = ancestor.full_name
                if entity_path.startswith(root_path):
                    # Strip root path and leading separator
                    relative = entity_path[len(root_path):].lstrip("/")
                    # Convert slashes to dots for consistency
                    return relative.replace("/", ".")
            except (ValueError, AttributeError):
                pass
            return None

        # Walk up from entity, building path segments
        path_parts: list[str] = []
        current: Optional[Entity] = entity

        while current is not None:
            if current is ancestor:
                # Found the ancestor, return path
                path_parts.reverse()
                return ".".join(path_parts)
            path_parts.append(current.local_name)
            current = current.parent

        # Ancestor not found in entity's ancestry
        return None

    def lookup(self, string: str) -> Entity:
        """Look up entity by reference string.

        Supports two formats:
        - PREFIX:path (e.g., "W:cytoplasm.glucose") - prefix-relative
        - </dat/path.entity.path> (e.g., "</runs/exp1.cytoplasm>") - absolute

        For absolute format, loads the DAT if not already loaded.

        Args:
            string: Reference string in either format

        Returns:
            The entity at the specified path

        Raises:
            ValueError: If string format is invalid
            KeyError: If prefix is not bound or path not found

        Example:
            io.lookup("W:cytoplasm.glucose")       # prefix-relative
            io.lookup("</runs/exp1.cytoplasm>")   # absolute
        """
        # Check for absolute format: </dat/path.entity.path>
        if string.startswith("</") and string.endswith(">"):
            return self._absolute_lookup(string)

        # Prefix-relative format: PREFIX:path
        if ":" not in string:
            raise ValueError(
                f"Invalid entity reference {string!r}: missing prefix separator ':'"
            )

        prefix, path = string.split(":", 1)

        if not prefix:
            raise ValueError(f"Invalid entity reference {string!r}: empty prefix")

        target = self.resolve_prefix(prefix)

        if not path:
            return target

        return self._walk_path(target, path)

    def _absolute_lookup(self, string: str) -> Entity:
        """Look up entity by absolute reference.

        Format: </dat/path.entity.path>
        - dat/path is the filesystem path to the DAT
        - entity.path is the dotted path from DAT root to entity

        Loads the DAT if not already cached.
        """
        # Strip </ and >
        inner = string[2:-1]

        # Find first dot to split DAT path from entity path
        dot_idx = inner.find(".")
        if dot_idx == -1:
            # No entity path, just DAT path
            dat_path = inner
            entity_path = ""
        else:
            dat_path = inner[:dot_idx]
            entity_path = inner[dot_idx + 1:]

        # Load or retrieve cached DAT entity
        root_entity = self._load_dat_entity(dat_path)

        if not entity_path:
            return root_entity

        return self._walk_path(root_entity, entity_path)

    def _load_dat_entity(self, dat_path: str) -> Entity:
        """Load a DAT and return its root entity, with caching.

        If the DAT has already been loaded, returns the cached entity.
        Otherwise loads from filesystem and caches.

        If entities.yaml exists in the DAT folder, loads the entity tree
        from it, recursively creating children.
        """
        # Check cache first
        if dat_path in self._dat_entity_cache:
            return self._dat_entity_cache[dat_path]

        # Import here to avoid circular import
        from .entity import Entity

        # Load the DAT
        dat = Dat.load(dat_path)

        # Check for entities.yaml
        dat_folder = Path(dat.get_path())
        entities_file = dat_folder / "entities.yaml"

        if entities_file.exists():
            import yaml

            with open(entities_file) as f:
                entity_data = yaml.safe_load(f)

            # Create root entity from loaded data
            entity = self._create_entity_from_dict(entity_data, dat=dat)
        else:
            # Create root entity from DAT
            # Use the last path component as the entity name
            name = Path(dat_path).name
            entity = Entity(name, dat=dat)

        # Cache and return
        self._dat_entity_cache[dat_path] = entity
        return entity

    def _create_entity_from_dict(
        self,
        data: Dict[str, Any],
        *,
        dat: Optional[Dat] = None,
        parent: Optional[Entity] = None,
    ) -> Entity:
        """Create an entity and its children from a dict.

        Uses type dispatch: looks up 'type' field in the entity registry
        to instantiate the correct Entity subclass.

        Args:
            data: Dict with 'type', 'name', optional 'description', optional 'children'
            dat: DAT anchor (required if no parent)
            parent: Parent entity (required if no dat)

        Returns:
            The created entity (may be a subclass based on 'head' field)
        """
        from .entity import Entity, get_entity_class

        # Get the entity class from head field (default to Entity)
        head_name = data.get("head", "Entity")
        try:
            entity_cls = get_entity_class(head_name)
        except KeyError:
            # Unknown head - fall back to base Entity
            entity_cls = Entity

        name = data.get("name", "unnamed")
        description = data.get("description", "")

        # Create entity using the resolved class
        entity = entity_cls(name, parent=parent, dat=dat, description=description)

        # Recursively create children (args)
        args_data = data.get("args", {})
        for child_name, child_data in args_data.items():
            if isinstance(child_data, str) and child_data.startswith("</"):
                # Absolute ref - load from another DAT
                child = self._absolute_lookup(child_data)
                # Reparent to this entity
                child.set_parent(entity)
            elif isinstance(child_data, dict):
                # Inline child definition
                self._create_entity_from_dict(child_data, parent=entity)
            # else: skip invalid entries

        return entity

    def _walk_path(self, entity: Entity, path: str) -> Entity:
        """Walk down a dotted path from an entity.

        Args:
            entity: Starting entity
            path: Dotted path like "compartment.glucose"

        Returns:
            The entity at the given path

        Raises:
            KeyError: If path not found
        """
        if not path:
            return entity

        parts = path.split(".", 1)
        name = parts[0]

        children = entity.children
        if name not in children:
            raise KeyError(f"No child named {name!r} in {entity.local_name!r}")

        child = children[name]
        if len(parts) == 1:
            return child
        return self._walk_path(child, parts[1])

    def resolve_refs(self, obj: Any) -> Any:
        """Recursively replace <PREFIX:path> strings with Entity objects.

        Walks a data structure (dict, list, or scalar) and replaces any
        strings matching the <PREFIX:path> pattern with the corresponding
        Entity objects.

        Args:
            obj: Data structure to process (dict, list, or scalar)

        Returns:
            New structure with entity references resolved

        Example:
            data = yaml.safe_load(file)
            data = io.resolve_refs(data)  # <W:glucose> → Entity
        """
        if isinstance(obj, str):
            if obj.startswith("<") and obj.endswith(">") and len(obj) > 2:
                return self.lookup(obj[1:-1])  # strip < >
            return obj
        elif isinstance(obj, dict):
            return {k: self.resolve_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.resolve_refs(item) for item in obj]
        else:
            return obj

    def insert_refs(self, obj: Any) -> Any:
        """Recursively replace Entity objects with <PREFIX:path> strings.

        Walks a data structure (dict, list, or scalar) and replaces any
        Entity objects with their <PREFIX:path> string representation.

        Args:
            obj: Data structure to process (dict, list, or scalar)

        Returns:
            New structure with entities replaced by reference strings

        Example:
            output = io.insert_refs(data)  # Entity → <W:glucose>
            yaml.dump(output, file)
        """
        # Import here to avoid circular import
        from .entity import Entity

        if isinstance(obj, Entity):
            return f"<{self.ref(obj)}>"
        elif isinstance(obj, dict):
            return {k: self.insert_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.insert_refs(item) for item in obj]
        else:
            return obj

    def load(self, path: str | Path) -> Dat:
        """Load a Dat from data path.

        Args:
            path: Path relative to data root, or absolute path

        Returns:
            The loaded Dat
        """
        return Dat.load(str(path))

    def save(self, obj: Any, path: str | Path) -> Dat:
        """Save object as Dat to data path.

        Args:
            obj: Object to save. If dict, uses as spec. Otherwise wraps in {"value": obj}.
            path: Path relative to Dat.manager.sync_folder

        Returns:
            The created Dat
        """
        if isinstance(obj, Dat):
            obj.save()
            return obj
        # Create a new Dat with the object as spec
        # Dat.create handles path resolution via Dat.manager.sync_folder
        spec = obj if isinstance(obj, dict) else {"value": obj}
        return Dat.create(path=str(path), spec=spec)
