"""IO module: entity naming, formatting, parsing, and persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from dvc_dat import Dat

if TYPE_CHECKING:
    from .entity import Entity


class IO:
    """Entity I/O: naming, formatting, parsing, and persistence.

    IO handles all external representation concerns for entities:
    - Prefix bindings: Maps short prefixes (R:, W:) to Entity/DAT anchors
    - Formatting: Converts entities to PREFIX:path strings
    - Parsing: Converts PREFIX:path strings back to entities
    - Persistence: Load/save entities via DAT

    The 'D:' prefix is always bound to the data root as an escape hatch.
    """

    def __init__(self, data_path: Optional[Path] = None) -> None:
        """Initialize IO.

        Args:
            data_path: Root path for data storage. Defaults to 'data'.
        """
        self._prefixes: Dict[str, Entity] = {}
        self._data_path = data_path or Path("data")

    @property
    def data_path(self) -> Path:
        """Root path for data storage."""
        return self._data_path

    @property
    def prefixes(self) -> Dict[str, Entity]:
        """Current prefix bindings (read-only copy)."""
        return self._prefixes.copy()

    def bind_prefix(self, prefix: str, target: Entity) -> None:
        """Bind a prefix to a target entity.

        Args:
            prefix: Short prefix string (e.g., "R", "W", "M")
            target: Entity to bind as the prefix root

        Example:
            io.bind_prefix("R", current_run)
            io.bind_prefix("W", world)
        """
        self._prefixes[prefix] = target

    def unbind_prefix(self, prefix: str) -> Optional[Entity]:
        """Remove a prefix binding.

        Args:
            prefix: Prefix to unbind

        Returns:
            The previously bound entity, or None if not bound
        """
        return self._prefixes.pop(prefix, None)

    def resolve_prefix(self, prefix: str) -> Entity:
        """Get the entity bound to a prefix.

        Args:
            prefix: Prefix to resolve

        Returns:
            The entity bound to this prefix

        Raises:
            KeyError: If prefix is not bound
        """
        if prefix not in self._prefixes:
            raise KeyError(f"Prefix {prefix!r} is not bound")
        return self._prefixes[prefix]

    def format(self, entity: Entity, prefer_short: bool = True) -> str:
        """Format entity as PREFIX:path string.

        Finds the shortest prefix that reaches this entity's ancestry,
        then builds the path from there.

        Args:
            entity: Entity to format
            prefer_short: If True, uses shortest matching prefix

        Returns:
            String in PREFIX:path format (e.g., "W:cytoplasm.glucose")

        Example:
            io.format(glucose)  # -> "W:cytoplasm.glucose"
        """
        if not self._prefixes:
            # No prefixes bound, use full name directly
            return entity.full_name

        # Find which prefixes match this entity's ancestry
        matches: list[tuple[str, str]] = []  # (prefix, remaining_path)

        for prefix, target in self._prefixes.items():
            path = self._relative_path(entity, target)
            if path is not None:
                matches.append((prefix, path))

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

    def _relative_path(self, entity: Entity, ancestor: Entity) -> Optional[str]:
        """Compute relative path from ancestor to entity.

        Returns None if ancestor is not in entity's ancestry.
        Returns "" if entity is the ancestor.
        Returns dotted path otherwise.
        """
        if entity is ancestor:
            return ""

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

    def parse(self, string: str) -> Entity:
        """Parse PREFIX:path string to entity.

        Resolves prefix, then walks down path to find entity.

        Args:
            string: String in PREFIX:path format

        Returns:
            The entity at the specified path

        Raises:
            ValueError: If string format is invalid
            KeyError: If prefix is not bound or path not found

        Example:
            io.parse("W:cytoplasm.glucose")  # -> glucose entity
        """
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

        return target.lookup(path)

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
            path: Path relative to data root

        Returns:
            The created Dat
        """
        full_path = self._data_path / path
        if isinstance(obj, Dat):
            obj.save()
            return obj
        # Create a new Dat with the object as spec
        spec = obj if isinstance(obj, dict) else {"value": obj}
        return Dat.create(path=str(full_path), spec=spec)
