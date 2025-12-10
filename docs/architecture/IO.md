# IO
**Subsystem**: [[ABIO infra]] > Entities
Entity I/O: prefix bindings, formatting, lookup, and persistence.

## Overview
IO handles all external representation concerns for entities: prefix bindings for short names, formatting to strings, lookup by reference, and persistence via DAT. It is accessed through Context and provides the implementation for top-level `load`, `save`, `lookup`, and `create_root` functions.

| Property | Type | Description |
|----------|------|-------------|
| `_prefixes` | Dict[str, Entity \| str] | Prefix -> target entity or path |
| `_dat_entity_cache` | Dict[str, Entity] | Cache for loaded DAT entities |

| Method | Returns | Description |
|--------|---------|-------------|
| `bind_prefix(prefix, target)` | None | Bind prefix to entity or path |
| `unbind_prefix(prefix)` | Entity \| str \| None | Remove prefix binding |
| `resolve_prefix(prefix)` | Entity | Get entity bound to prefix |
| `ref(entity, prefer_short, absolute)` | str | Get reference string for entity |
| `lookup(string)` | Entity | Find entity by reference string |
| `resolve_refs(obj)` | Any | Replace `<PREFIX:path>` with entities |
| `insert_refs(obj)` | Any | Replace entities with `<PREFIX:path>` |
| `load(path)` | Dat | Load Dat from data path |
| `save(obj, path)` | Dat | Save object as Dat |

## Discussion

### Prefix Conventions
Single-letter prefixes for common entity types:

| Prefix | Binds To | Example |
|--------|----------|---------|
| D | Data root (always available) | `D:runs/exp1.world` |
| R | Current run DAT | `R:world.compartment` |
| W | Current world | `W:compartment.glucose` |
| E | Current experiment | `E:run1.world` |
| ORPHAN | Orphan root (auto-bound) | `ORPHAN:detached_entity` |

### Reference Formats

**Prefix-Relative Format:** `PREFIX:path`
```python
io.bind_prefix("W", world)
io.ref(glucose)              # "W:cytoplasm.glucose"
io.lookup("W:cytoplasm")     # -> cytoplasm entity
```

**Absolute Format:** `</dat/path.entity.path>`
```python
io.ref(glucose, absolute=True)   # "</runs/exp1.cytoplasm.glucose>"
io.lookup("</runs/exp1.cytoplasm>")  # -> cytoplasm entity
```

### Ref / Lookup Roundtrip
`ref` and `lookup` are inverses:

```python
io.bind_prefix("W", world)
ref_str = io.ref(glucose)    # "W:cytoplasm.glucose"
found = io.lookup(ref_str)   # glucose entity
assert found is glucose

# Shortest prefix is used
io.bind_prefix("C", cytoplasm)
io.ref(glucose)  # "C:glucose" (shorter than "W:cytoplasm.glucose")
```

### Entity Loading with Type Dispatch
When loading entities from `entities.yaml`, IO uses the type registry:

```yaml
type: Entity
name: world
children:
  glucose:
    type: M
    name: glucose
    formula: C6H12O6
```

### YAML Serialization
Entity references use `<PREFIX:path>` format:

```yaml
molecules:
  - name: glucose
    location: <W:cytoplasm>
```

Use `resolve_refs` and `insert_refs` to convert between YAML and in-memory.

### Creating Entity Trees
Use `create_root` to create a new DAT with its root entity:

```python
from alienbio import create_root

world = create_root("runs/exp1", World, description="My experiment")
cytoplasm = Compartment("cytoplasm", parent=world, volume=1.5)
world.save()  # Creates runs/exp1/entities.yaml
```

## Method Details

### `bind_prefix(prefix: str, target: Entity | str) -> None`
Bind a prefix to a target entity or path string.

**Args:**
- `prefix`: Short prefix string (e.g., "W", "R")
- `target`: Entity or path string to bind

### `ref(entity: Entity, prefer_short: bool = True, absolute: bool = False) -> str`
Get reference string for entity.

**Args:**
- `entity`: Entity to get reference for
- `prefer_short`: If True, uses shortest matching prefix
- `absolute`: If True, returns `</dat/path.entity.path>` format

**Returns:** Reference string

### `lookup(string: str) -> Entity`
Look up entity by reference string.

**Args:**
- `string`: Either `PREFIX:path` or `</dat/path.entity.path>`

**Returns:** The entity

**Raises:**
- `KeyError`: If prefix not bound or entity not found

## Protocol
```python
from typing import Dict, Any, Optional, Protocol

class IO(Protocol):
    """Entity I/O: naming, formatting, lookup, persistence."""

    _prefixes: Dict[str, "Entity" | str]
    _dat_entity_cache: Dict[str, "Entity"]

    def bind_prefix(self, prefix: str, target: "Entity" | str) -> None:
        """Bind a prefix to a target entity or path string."""
        ...

    def unbind_prefix(self, prefix: str) -> Optional["Entity" | str]:
        """Remove a prefix binding."""
        ...

    def resolve_prefix(self, prefix: str) -> "Entity":
        """Get the entity bound to a prefix."""
        ...

    def ref(
        self, entity: "Entity", prefer_short: bool = True, absolute: bool = False
    ) -> str:
        """Get reference string for entity."""
        ...

    def lookup(self, string: str) -> "Entity":
        """Look up entity by reference string."""
        ...

    def resolve_refs(self, obj: Any) -> Any:
        """Replace <PREFIX:path> strings with Entity objects."""
        ...

    def insert_refs(self, obj: Any) -> Any:
        """Replace Entity objects with <PREFIX:path> strings."""
        ...

    def load(self, path: str) -> "Dat":
        """Load a Dat from data path."""
        ...

    def save(self, obj: Any, path: str) -> "Dat":
        """Save object as Dat to data path."""
        ...
```

## See Also
- [[Context]] - Parent container for IO
- [[Entity]] - Base class, tree invariants, serialization
- [[ABIO DAT]] - Underlying DAT persistence
