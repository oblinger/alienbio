# IO
**Subsystem**: [[ABIO infra]]
Entity I/O: prefix bindings, printing, parsing, and persistence.

## Description

IO handles all external representation concerns for entities:
- **Prefix bindings** - Maps short prefixes (R:, W:) to DAT anchors
- **Formatting** - Converts entities to PREFIX:path strings
- **Parsing** - Converts PREFIX:path strings back to entities
- **Persistence** - Load/save entities via DAT

IO is accessed through [[Context]] and provides the implementation for top-level `load`, `save`, and `parse` functions.

| Properties | Type | Description |
|----------|------|-------------|
| _prefixes | Dict[str, Entity] | Prefix -> target entity/DAT bindings |

| Methods | Description |
|---------|-------------|
| bind_prefix | Bind a prefix to a target entity |
| resolve_prefix | Get the entity bound to a prefix |
| format | Convert entity to PREFIX:path string |
| parse | Convert PREFIX:path string to entity |
| load | Load entity from data path |
| save | Save entity to data path |

## Protocol Definition

```python
from typing import Protocol, Dict, Any, Optional

class IO(Protocol):
    """Entity I/O: naming, printing, parsing, persistence."""

    _prefixes: Dict[str, "Entity"]

    def bind_prefix(self, prefix: str, target: "Entity") -> None:
        """Bind a prefix to a target entity/DAT.

        Example:
            io.bind_prefix("R", current_run_dat)
            io.bind_prefix("W", world)
        """
        ...

    def resolve_prefix(self, prefix: str) -> "Entity":
        """Get the entity bound to a prefix.

        Raises KeyError if prefix not bound.
        """
        ...

    def format(self, entity: "Entity") -> str:
        """Format entity as PREFIX:path string.

        Walks up entity's parent chain to find nearest DAT anchor,
        then finds shortest prefix that matches.

        Example:
            io.format(glucose)  # -> "W:compartment.glucose"
        """
        ...

    def parse(self, string: str) -> "Entity":
        """Parse PREFIX:path string to entity.

        Resolves prefix, then walks down path to find entity.

        Example:
            io.parse("W:compartment.glucose")  # -> glucose entity
        """
        ...

    def load(self, path: str) -> "Dat":
        """Load a Dat from data path.

        Path can be absolute or relative to data root.
        """
        ...

    def save(self, obj: Any, path: str) -> "Dat":
        """Save object as Dat to data path.

        If obj is a dict, uses it as spec.
        Otherwise wraps in {"value": obj}.
        """
        ...
```

## Default Prefix

The `D:` prefix is always bound to the data root. This provides an escape hatch for naming any DAT-backed entity:

```python
# D: always works, even with no other prefixes bound
io.format(some_entity)  # -> "D:runs/exp1.world1.compartment.glucose"

# With shortcuts bound
io.bind_prefix("R", run_dat)
io.bind_prefix("W", world)
io.format(some_entity)  # -> "W:compartment.glucose"
```

## Usage

```python
# Access via context
ctx().io.bind_prefix("W", world)
print(ctx().io.format(glucose))  # W:cytoplasm.glucose

# Or via top-level functions (which delegate to ctx().io)
from alienbio import parse, load, save

molecule = parse("W:cytoplasm.glucose")
dat = load("runs/exp1")
save({"name": "result"}, "runs/exp1/results")
```

## Integration with Entity

Entities use IO for their string representation:

```python
class Entity:
    def __str__(self) -> str:
        """Uses Context.current().io.format(self)"""
        from alienbio import ctx
        return ctx().io.format(self)
```

## See Also

- [[Context]] - Parent container for IO
- [[Entity-naming]] - Naming scheme and prefix system
- [[Entity]] - Base protocol using IO for display
- [[ABIO DAT]] - Underlying DAT persistence
