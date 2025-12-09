# IO
**Subsystem**: [[ABIO infra]]
Entity I/O: prefix bindings, formatting, lookup, and persistence.

## Description

IO handles all external representation concerns for entities:
- **Prefix bindings** - Maps short prefixes (R:, W:) to Entity anchors
- **Formatting** - Converts entities to PREFIX:path strings
- **Lookup** - Finds entities by PREFIX:path strings
- **Persistence** - Load/save entities via DAT

IO is accessed through [[Context]] and provides the implementation for top-level `load`, `save`, and `lookup` functions.

| Properties | Type | Description |
|----------|------|-------------|
| _prefixes | Dict[str, Entity] | Prefix -> target entity bindings |
| data_path | Path | Root path for data storage |

| Methods | Description |
|---------|-------------|
| bind_prefix | Bind a prefix to a target entity |
| unbind_prefix | Remove a prefix binding |
| resolve_prefix | Get the entity bound to a prefix |
| format | Convert entity to PREFIX:path string |
| lookup | Find entity by PREFIX:path string |
| load | Load Dat from data path |
| save | Save object as Dat to data path |

## Protocol Definition

```python
from typing import Dict, Any, Optional
from pathlib import Path

class IO:
    """Entity I/O: naming, formatting, lookup, persistence."""

    _prefixes: Dict[str, "Entity"]
    _data_path: Path

    def bind_prefix(self, prefix: str, target: "Entity") -> None:
        """Bind a prefix to a target entity.

        Example:
            io.bind_prefix("R", current_run)
            io.bind_prefix("W", world)
        """
        ...

    def unbind_prefix(self, prefix: str) -> Optional["Entity"]:
        """Remove a prefix binding. Returns the previously bound entity."""
        ...

    def resolve_prefix(self, prefix: str) -> "Entity":
        """Get the entity bound to a prefix.

        Raises KeyError if prefix not bound.
        """
        ...

    def format(self, entity: "Entity") -> str:
        """Format entity as PREFIX:path string.

        Finds the shortest prefix that matches entity's ancestry,
        then builds the path from there.

        Example:
            io.format(glucose)  # -> "W:cytoplasm.glucose"
        """
        ...

    def lookup(self, string: str) -> "Entity":
        """Look up entity by PREFIX:path string.

        Resolves prefix, then walks down path to find entity.

        Example:
            io.lookup("W:cytoplasm.glucose")  # -> glucose entity
        """
        ...

    def load(self, path: str) -> "Dat":
        """Load a Dat from data path."""
        ...

    def save(self, obj: Any, path: str) -> "Dat":
        """Save object as Dat to data path.

        If obj is a dict, uses it as spec.
        Otherwise wraps in {"value": obj}.
        """
        ...
```

## Usage

```python
# Access via context
ctx().io.bind_prefix("W", world)
print(ctx().io.format(glucose))  # W:cytoplasm.glucose

# Or via top-level functions (which delegate to ctx().io)
from alienbio import lookup, load, save

molecule = lookup("W:cytoplasm.glucose")
dat = load("runs/exp1")
save({"name": "result"}, "runs/exp1/results")
```

## Format / Lookup Roundtrip

`format` and `lookup` are inverses:

```python
io.bind_prefix("W", world)

# format -> lookup roundtrip
formatted = io.format(glucose)      # "W:cytoplasm.glucose"
found = io.lookup(formatted)        # glucose entity
assert found is glucose

# Shortest prefix is used
io.bind_prefix("C", cytoplasm)
io.format(glucose)  # "C:glucose" (shorter than "W:cytoplasm.glucose")
```

## See Also

- [[Context]] - Parent container for IO
- [[Entity-naming]] - Naming scheme and prefix system
- [[Entity]] - Base class with to_dict() for serialization
- [[ABIO DAT]] - Underlying DAT persistence
