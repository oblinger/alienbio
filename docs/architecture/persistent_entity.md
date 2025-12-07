# PersistentEntity

Entity that is saved to data/ and loadable by name.

**Subsystem**: [[infra|Infra]] > Entities

## Description

PersistentEntity extends Entity for objects that are saved to the `data/` folder and can be loaded by name via dvc_dat. These represent reusable definitions like molecule types, reaction templates, and organism blueprints.

## Protocol Definition

```python
from typing import Protocol, TypeVar

T = TypeVar("T", bound="PersistentEntity")

class PersistentEntity(Entity, Protocol):
    """Entity saved to data/ folder, loadable by name."""

    @classmethod
    def load(cls: type[T], name: str) -> T:
        """Load entity by name from data/ folder."""
        ...

    def save(self) -> None:
        """Save entity to data/ folder."""
        ...
```

## Methods

### load(name: str) -> PersistentEntity
Class method that loads an entity from the data/ folder by name.

### save() -> None
Saves the entity to the data/ folder using its name.

## Storage

Persistent entities are stored as YAML files in `data/`:
```
data/
  molecules/
    glucose.yaml
    atp.yaml
  reactions/
    glycolysis_step1.yaml
```

## See Also

- [[entity|Entity]] - Base protocol
- [[scoped_entity|ScopedEntity]] - Runtime instance entities
