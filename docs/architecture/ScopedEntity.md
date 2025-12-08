# ScopedEntity
**Subsystem**: [[infra]] > Entities
Entity named relative to containing World or Harness.

## Description
ScopedEntity extends Entity for runtime instances that are named relative to their containing scope. These represent specific instances like "the glucose in compartment A" rather than "glucose" as a molecule type.

| Properties | Type | Description |
|----------|------|-------------|
| scope | World | The containing World or Harness |
| qualified_name | str | Full path like "world1.compartmentA.glucose" |

## Protocol Definition
```python
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .world import World

class ScopedEntity(Entity, Protocol):
    """Entity scoped to a containing World or Harness."""

    scope: "World"

    @property
    def qualified_name(self) -> str:
        """Full name including scope path."""
        ...
```

## Naming
Scoped entities use qualified names that include their full path:
- `world1.cytoplasm.glucose` - glucose instance in world1's cytoplasm
- `experiment3.organism.mitochondria.atp` - ATP in a specific compartment

## See Also
- [[Entity]] - Base protocol
- [[PersistentEntity]] - Reusable definitions
- [[World]] - The scope container
