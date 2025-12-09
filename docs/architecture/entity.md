# Entity
**Subsystem**: [[ABIO infra]] > Entities
Base protocol for all biology objects.

## Description
Entity is the root of the type hierarchy for all biology objects. It provides consistent serialization, identity, and naming patterns.

| Properties | Type | Description |
|----------|------|-------------|
| _local_name | str | Name within parent's children dict |
| _parent | Entity? | Link to containing entity |
| _children | Dict[str, Entity] | Child entities by local name |
| _dat | Dat? | Optional anchor to filesystem |
| description | str | Human-readable description |

| Methods | Description |
|---------|-------------|
| qualified_name | Full path computed by walking up to DAT anchor |
| serialize | Convert to YAML string representation |
| deserialize | Reconstruct from YAML string |
| lookup | Find child entity by relative path |

## Protocol Definition
```python
from typing import Protocol, Optional, Dict

class Entity(Protocol):
    """Base protocol for all biology objects."""

    _local_name: str
    _parent: Optional["Entity"]
    _children: Dict[str, "Entity"]
    _dat: Optional["Dat"]
    description: str

    @property
    def qualified_name(self) -> str:
        """Full name including path to DAT anchor."""
        ...

    def lookup(self, path: str) -> "Entity":
        """Find child by relative dotted path."""
        ...

    def serialize(self) -> str:
        """Convert to YAML string representation."""
        ...

    @classmethod
    def deserialize(cls, data: str) -> "Entity":
        """Reconstruct from YAML string."""
        ...
```

## Naming

Entities derive their names from their position in the containment hierarchy. See [[Entity-naming]] for full details on:
- Name resolution algorithm
- DAT anchors
- Prefix system (PREFIX:name format)
- Display conventions

## Methods

### qualified_name -> str
Property that computes the full path by walking up parent links until a DAT anchor is found.

### lookup(path) -> Entity
Finds a child entity by relative dotted path (e.g., `"compartment.glucose"`).

### serialize() -> str
Converts the entity to a YAML string representation suitable for storage or transmission.

### deserialize(data: str) -> Entity
Class method that reconstructs an entity from its YAML representation.

## See Also
- [[Entity-naming]] - Naming scheme, prefixes, display format
- [[ABIO DAT]] - DAT storage integration
