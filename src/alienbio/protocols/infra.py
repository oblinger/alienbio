"""Infrastructure protocol definitions.

Protocols for the infrastructure subsystem:
- Entity: Base class for all biology objects
- IO: Entity I/O operations
- Expr: Simple functional expressions
- Context: Runtime pegboard

These protocols will be implemented as the infrastructure matures.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class Entity(Protocol):
    """Protocol for entity base class.

    All biology objects inherit from Entity. Entities have:
    - A local name within their parent
    - Optional parent/child relationships forming a tree
    - Optional DAT anchor for persistence
    """

    @property
    def local_name(self) -> str:
        """The entity's local name within its parent."""
        ...

    @property
    def parent(self) -> Optional[Entity]:
        """The parent entity, or None if root."""
        ...

    @property
    def children(self) -> Dict[str, Entity]:
        """Child entities by name."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description."""
        ...

    def root(self) -> Entity:
        """Get the root of the entity tree."""
        ...

    def dat(self) -> Any:
        """Get the DAT anchor (from root)."""
        ...

    def to_dict(self, recursive: bool = False) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        ...


# IO and Expr protocols to be defined as those subsystems mature
