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

Note: For data path, use `Dat.manager.sync_folder` (single source of truth).

| Methods | Description |
|---------|-------------|
| bind_prefix | Bind a prefix to a target entity |
| unbind_prefix | Remove a prefix binding |
| resolve_prefix | Get the entity bound to a prefix |
| ref | Get reference string for entity (PREFIX:path) |
| lookup | Find entity by PREFIX:path string |
| resolve_refs | Replace `<PREFIX:path>` strings with entities in a structure |
| insert_refs | Replace entities with `<PREFIX:path>` strings in a structure |
| load | Load Dat from data path |
| save | Save object as Dat to data path |

## Protocol Definition

```python
from typing import Dict, Any, Optional

class IO:
    """Entity I/O: naming, formatting, lookup, persistence.

    Note: For data path, use Dat.manager.sync_folder (single source of truth).
    """

    _prefixes: Dict[str, "Entity"]

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

    def ref(self, entity: "Entity") -> str:
        """Get reference string for entity.

        Finds the shortest prefix that matches entity's ancestry,
        then builds the path from there.

        Example:
            io.ref(glucose)  # -> "W:cytoplasm.glucose"
        """
        ...

    def lookup(self, string: str) -> "Entity":
        """Look up entity by PREFIX:path string.

        Resolves prefix, then walks down path to find entity.

        Example:
            io.lookup("W:cytoplasm.glucose")  # -> glucose entity
        """
        ...

    def resolve_refs(self, obj: Any) -> Any:
        """Replace <PREFIX:path> strings with Entity objects in a structure.

        Recursively walks dicts and lists, replacing matching strings.

        Example:
            data = yaml.safe_load(file)
            data = io.resolve_refs(data)  # <W:glucose> → Entity
        """
        ...

    def insert_refs(self, obj: Any) -> Any:
        """Replace Entity objects with <PREFIX:path> strings in a structure.

        Recursively walks dicts and lists, replacing entities.

        Example:
            output = io.insert_refs(data)  # Entity → <W:glucose>
            yaml.dump(output, file)
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
print(ctx().io.ref(glucose))  # W:cytoplasm.glucose

# Or via top-level functions (which delegate to ctx().io)
from alienbio import lookup, load, save

molecule = lookup("W:cytoplasm.glucose")
dat = load("runs/exp1")
save({"name": "result"}, "runs/exp1/results")
```

## Ref / Lookup Roundtrip

`ref` and `lookup` are inverses:

```python
io.bind_prefix("W", world)

# ref -> lookup roundtrip
ref_str = io.ref(glucose)           # "W:cytoplasm.glucose"
found = io.lookup(ref_str)          # glucose entity
assert found is glucose

# Shortest prefix is used
io.bind_prefix("C", cytoplasm)
io.ref(glucose)  # "C:glucose" (shorter than "W:cytoplasm.glucose")
```

## YAML Serialization

Entity references in YAML use `<PREFIX:path>` format. The angle brackets allow
entity references to be distinguished from plain strings without requiring quotes:

```yaml
molecules:
  - name: glucose
    location: <W:cytoplasm>
    reactants:
      - <W:cytoplasm.ATP>
      - <W:cytoplasm.glucose>
```

Use `resolve_refs` and `insert_refs` to convert between YAML and in-memory structures:

```python
import yaml

# Load YAML and resolve entity references
with open("data.yaml") as f:
    data = yaml.safe_load(f)
data = io.resolve_refs(data)  # <W:cytoplasm> → Entity objects

# ... work with entities ...

# Serialize back to YAML
output = io.insert_refs(data)  # Entity → <W:cytoplasm>
with open("output.yaml", "w") as f:
    yaml.dump(output, f)
```

## See Also

- [[Context]] - Parent container for IO
- [[Entity-naming]] - Naming scheme and prefix system
- [[Entity]] - Base class with to_dict() for serialization
- [[ABIO DAT]] - Underlying DAT persistence
