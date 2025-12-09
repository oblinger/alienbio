# IO
**Subsystem**: [[ABIO infra]]
Entity I/O: prefix bindings, formatting, lookup, and persistence.

## Description

IO handles all external representation concerns for entities:
- **Prefix bindings** - Maps short prefixes (R:, W:) to Entity anchors
- **Formatting** - Converts entities to PREFIX:path strings
- **Lookup** - Finds entities by PREFIX:path or absolute strings
- **Persistence** - Load/save entities via DAT
- **Type dispatch** - Creates correct Entity subclasses when loading
- **Entity creation** - Create new DAT-anchored entity trees via `create_root`

IO is accessed through [[Context]] and provides the implementation for top-level `load`, `save`, `lookup`, and `create_root` functions.

| Properties | Type | Description |
|----------|------|-------------|
| _prefixes | Dict[str, Entity \| str] | Prefix -> target entity or path bindings |
| _dat_entity_cache | Dict[str, Entity] | Cache for loaded DAT entities |

Note: For data path, use `Dat.manager.sync_folder` (single source of truth).

| Methods | Description |
|---------|-------------|
| bind_prefix | Bind a prefix to a target entity or path |
| unbind_prefix | Remove a prefix binding |
| resolve_prefix | Get the entity bound to a prefix |
| ref | Get reference string for entity (PREFIX:path or absolute) |
| lookup | Find entity by PREFIX:path or absolute string |
| resolve_refs | Replace `<PREFIX:path>` strings with entities in a structure |
| insert_refs | Replace entities with `<PREFIX:path>` strings in a structure |
| load | Load Dat from data path |
| save | Save object as Dat to data path |

## Reference Formats

IO supports two reference formats:

### Prefix-Relative Format
`PREFIX:path` - Uses bound prefixes for short references.

```python
io.bind_prefix("W", world)
io.ref(glucose)              # "W:cytoplasm.glucose"
io.lookup("W:cytoplasm")     # -> cytoplasm entity
```

### Absolute Format
`</dat/path.entity.path>` - Global reference independent of prefix bindings.

```python
io.ref(glucose, absolute=True)   # "</runs/exp1.cytoplasm.glucose>"
io.lookup("</runs/exp1.cytoplasm>")  # -> cytoplasm entity
```

The absolute format:
- Starts with `</` and ends with `>`
- First component is the DAT path (slash-separated)
- Remaining components are the entity path (dot-separated)
- Loads the DAT if not already cached

## Protocol Definition

```python
from typing import Dict, Any, Optional

class IO:
    """Entity I/O: naming, formatting, lookup, persistence.

    Note: For data path, use Dat.manager.sync_folder (single source of truth).
    """

    _prefixes: Dict[str, "Entity" | str]
    _dat_entity_cache: Dict[str, "Entity"]

    def bind_prefix(self, prefix: str, target: "Entity" | str) -> None:
        """Bind a prefix to a target entity or path string.

        Example:
            io.bind_prefix("R", current_run)      # entity
            io.bind_prefix("W", "runs/exp1")      # path string
        """
        ...

    def unbind_prefix(self, prefix: str) -> Optional["Entity" | str]:
        """Remove a prefix binding. Returns the previously bound target."""
        ...

    def resolve_prefix(self, prefix: str) -> "Entity":
        """Get the entity bound to a prefix.

        The special prefix 'D' always resolves to the data root.
        Raises KeyError if prefix not bound.
        """
        ...

    def ref(
        self, entity: "Entity", prefer_short: bool = True, absolute: bool = False
    ) -> str:
        """Get reference string for entity.

        Args:
            entity: Entity to get reference for
            prefer_short: If True, uses shortest matching prefix
            absolute: If True, returns </dat/path.entity.path> format

        Example:
            io.ref(glucose)                # "W:cytoplasm.glucose"
            io.ref(glucose, absolute=True) # "</runs/exp1.cytoplasm.glucose>"
        """
        ...

    def lookup(self, string: str) -> "Entity":
        """Look up entity by reference string.

        Supports two formats:
        - PREFIX:path (e.g., "W:cytoplasm.glucose") - prefix-relative
        - </dat/path.entity.path> (e.g., "</runs/exp1.cytoplasm>") - absolute

        For absolute format, loads the DAT if not already cached.

        Example:
            io.lookup("W:cytoplasm.glucose")      # prefix-relative
            io.lookup("</runs/exp1.cytoplasm>")   # absolute
        """
        ...

    def resolve_refs(self, obj: Any) -> Any:
        """Replace <PREFIX:path> strings with Entity objects in a structure.

        Recursively walks dicts and lists, replacing matching strings.

        Example:
            data = yaml.safe_load(file)
            data = io.resolve_refs(data)  # <W:glucose> -> Entity
        """
        ...

    def insert_refs(self, obj: Any) -> Any:
        """Replace Entity objects with <PREFIX:path> strings in a structure.

        Recursively walks dicts and lists, replacing entities.

        Example:
            output = io.insert_refs(data)  # Entity -> <W:glucose>
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

# Absolute references
print(ctx().io.ref(glucose, absolute=True))  # </runs/exp1.cytoplasm.glucose>

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

# Absolute roundtrip (no prefix binding needed)
abs_ref = io.ref(glucose, absolute=True)  # "</runs/exp1.cytoplasm.glucose>"
found = io.lookup(abs_ref)                 # glucose entity
```

## Entity Loading with Type Dispatch

When loading entities from `entities.yaml`, IO uses the type registry to create the correct Entity subclass:

```yaml
# entities.yaml
type: Entity
name: world
children:
  cytoplasm:
    type: C
    name: cytoplasm
    volume: 1.5
  glucose:
    type: M
    name: glucose
    formula: C6H12O6
```

The `type` field maps to registered Entity subclasses via `get_entity_type()`.

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
data = io.resolve_refs(data)  # <W:cytoplasm> -> Entity objects

# ... work with entities ...

# Serialize back to YAML
output = io.insert_refs(data)  # Entity -> <W:cytoplasm>
with open("output.yaml", "w") as f:
    yaml.dump(output, f)
```

## Creating Entity Trees

Use `create_root` to create a new DAT with its root entity:

```python
from alienbio import create_root, Entity

# Create a new entity tree anchored to a DAT
world = create_root("runs/exp1", World, description="My experiment")

# Add children using normal constructors
cytoplasm = Compartment("cytoplasm", parent=world, volume=1.5)
glucose = Molecule("glucose", parent=cytoplasm)

# Save persists the entire tree
world.save()  # Creates runs/exp1/entities.yaml
```

The `create_root` function:
- Creates a DAT at the specified path
- Creates the root entity attached to that DAT
- Returns the root entity (with `entity._dat` set)

Children are created with normal constructors, passing `parent=`. See [[Entity]] for the tree/DAT invariants.

## Prefix Conventions

Single-letter prefixes for common entity types:

| Prefix | Binds To | Example |
|--------|----------|---------|
| D | Data root (always available) | `D:runs/exp1.world` |
| R | Current run DAT | `R:world.compartment` |
| W | Current world | `W:compartment.glucose` |
| E | Current experiment | `E:run1.world` |

The `D:` prefix is always bound to the data root - every entity can be named with `D:` as an escape hatch.

Keep prefixes few - too many creates confusion.

## See Also

- [[Context]] - Parent container for IO
- [[Entity]] - Base class, tree invariants, serialization
- [[ABIO DAT]] - Underlying DAT persistence
