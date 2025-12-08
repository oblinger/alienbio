# Entity
**Subsystem**: [[infra]] > Entities
Base protocol for all biology objects.

## Description
Entity is the root of the type hierarchy for all biology objects. It provides consistent serialization, identity, and naming patterns.

| Properties | Type | Description |
|----------|------|-------------|
| name | str | Unique identifier within scope |
| description | str | Human-readable description |

| Methods | Description |
|---------|-------------|
| serialize | Convert to YAML string representation |
| deserialize | Reconstruct from YAML string |

## Protocol Definition
```python
from typing import Protocol

class Entity(Protocol):
    """Base protocol for all biology objects."""

    name: str
    description: str

    def serialize(self) -> str:
        """Convert to YAML string representation."""
        ...

    @classmethod
    def deserialize(cls, data: str) -> "Entity":
        """Reconstruct from YAML string."""
        ...
```

## Methods
### serialize() -> str
Converts the entity to a YAML string representation suitable for storage or transmission.

### deserialize(data: str) -> Entity
Class method that reconstructs an entity from its YAML representation.

## See Also
- [[PersistentEntity]] - Entities saved to data/
- [[ScopedEntity]] - Entities scoped to a World
