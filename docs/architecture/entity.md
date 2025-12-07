# Entity

Base protocol for all biology objects.

**Subsystem**: [[infra|Infra]] > Entities

## Description

Entity is the root of the type hierarchy for all biology objects. It provides consistent serialization, identity, and naming patterns.

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

## Properties

| Property | Type | Description |
|----------|------|-------------|
| name | str | Unique identifier within scope |
| description | str | Human-readable description |

## Methods

### serialize() -> str
Converts the entity to a YAML string representation suitable for storage or transmission.

### deserialize(data: str) -> Entity
Class method that reconstructs an entity from its YAML representation.

## See Also

- [[persistent_entity|PersistentEntity]] - Entities saved to data/
- [[scoped_entity|ScopedEntity]] - Entities scoped to a World
