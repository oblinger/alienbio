# Entity
**Subsystem**: [[ABIO infra]] > Entities
Base class for all biology objects.

## Description

Entity is the root of the type hierarchy for all biology objects. It provides:
- Tree structure with parent/child relationships
- DAT anchoring for filesystem persistence
- Type registry for subclass serialization
- Context-aware string representation

| Properties | Type | Description |
|----------|------|-------------|
| _local_name | str | Name within parent's children dict |
| _parent | Entity? | Link to containing entity |
| _children | Dict[str, Entity] | Child entities by local name |
| _top | Entity \| Dat | Either Dat (root entities) or root Entity (non-roots) |
| description | str | Human-readable description |

| Methods      | Description                                          |
| ------------ | ---------------------------------------------------- |
| head         | Type name for serialization (property)               |
| attributes   | Semantic content dict (override in subclasses)       |
| dat          | Get the DAT anchor for this entity's tree (O(1))     |
| root         | Get the root entity of this tree (O(1))              |
| full_name    | Full path computed by walking up to DAT anchor       |
| to_dict      | Convert to dictionary for serialization              |
| to_str       | Tree representation like `World(Cytoplasm(Glucose))` |
| save         | Save entity tree to entities.yaml (root only)        |
| detach       | Detach from parent (moves to orphan root)            |
| set_parent   | Change parent (None → orphan root)                   |
| ancestors    | Iterate over ancestors to root                       |
| descendants  | Iterate over all descendants                         |

## Head Registry

Entity subclasses are automatically registered for serialization via `__init_subclass__`:

```python
# Registered as "Molecule" (class name)
class Molecule(Entity):
    pass

# Registered as "Mol" (short head name)
class Molecule(Entity, head="Mol"):
    pass
```

Registry functions:
- `register_head(name, cls)` - Register a head manually
- `get_entity_class(name)` - Look up class by head name
- `get_registered_heads()` - Get all registered heads

Legacy aliases (for compatibility):
- `register_entity_type()`, `get_entity_type()`, `get_entity_types()`

## Protocol Definition

```python
from typing import Dict, Any, Optional, Iterator

class Entity:
    """Base class for all biology objects."""

    _local_name: str
    _parent: Optional["Entity"]
    _children: Dict[str, "Entity"]
    _top: "Entity" | "Dat"  # Dat for root, root Entity for non-roots
    description: str

    def __init_subclass__(cls, head: str = None, **kwargs) -> None:
        """Auto-register subclasses. Use head for short alias."""
        ...

    @property
    def head(self) -> str:
        """Type name for serialization (from registry or class name)."""
        ...

    def attributes(self) -> Dict[str, Any]:
        """Semantic content of this entity (override in subclasses).

        Returns dict with 'name' and 'description'. Subclasses add their fields.
        """
        ...

    def dat(self) -> "Dat":
        """Get the DAT anchor for this entity's tree. O(1)."""
        ...

    def root(self) -> "Entity":
        """Get the root entity (ancestor with DAT). O(1)."""
        ...

    def full_name(self) -> str:
        """Full path from DAT anchor (e.g., 'runs/exp1.cytoplasm.glucose')."""
        ...

    def detach(self) -> None:
        """Detach from parent. Moves to orphan root (entity remains valid)."""
        ...

    def set_parent(self, parent: Optional["Entity"]) -> None:
        """Change parent. If None, moves to orphan root."""
        ...

    def to_dict(self, recursive: bool = False) -> Dict[str, Any]:
        """Convert to dict. Includes 'head' field for subclass dispatch."""
        ...

    def to_str(self, depth: int = -1) -> str:
        """Tree representation like 'World(Cytoplasm(Glucose))'."""
        ...

    def save(self) -> None:
        """Save entity tree to entities.yaml. Must be called on root."""
        ...

    def __str__(self) -> str:
        """Returns PREFIX:path via context, or full_name as fallback."""
        ...
```

## Three-Part Structure

Entities have a three-part structure analogous to a function call:

| Part | Method/Property | Description |
|------|-----------------|-------------|
| **head** | `entity.head` | Type name (like function name): "Molecule", "Compartment" |
| **args** | `entity.children` | Child entities (like positional args): nested content |
| **attributes** | `entity.attributes()` | Semantic fields (like kwargs): name, description, custom fields |

Subclasses override `attributes()` to include their specific fields:

```python
class MoleculeImpl(Entity, head="Molecule"):
    def attributes(self) -> Dict[str, Any]:
        result = super().attributes()  # Gets name, description
        result["atoms"] = {atom.symbol: count for atom, count in self._atoms.items()}
        result["bdepth"] = self._bdepth
        return result
```

This structure is reflected in serialization: `to_dict()` outputs `head`, `args`, and the attribute fields.

## Serialization

### to_dict()

Converts entity to dictionary with type information:

```python
molecule.to_dict()
# {"head": "M", "name": "glucose", "atoms": {"C": 6, "H": 12, "O": 6}}

world.to_dict(recursive=True)
# {
#   "head": "Entity",
#   "name": "world",
#   "args": {
#     "cytoplasm": {"head": "C", "name": "cytoplasm", ...}
#   }
# }
```

### save()

Saves the entity tree to `entities.yaml` in the DAT folder:

```python
world.save()
# Creates: dat_folder/entities.yaml
```

The YAML file contains the full tree with type information. Children with different DATs are stored as absolute references (`</dat/path.entity.path>`).

## String Representation

### __str__

Uses context-aware formatting when available:

```python
ctx.io.bind_prefix("W", world)
print(glucose)  # "W:cytoplasm.glucose"
```

Falls back to `full_name` if no context or no matching prefix.

### to_str(depth)

Tree representation for debugging:

```python
world.to_str()      # "World(Cytoplasm(Glucose, ATP))"
world.to_str(0)     # "World"
world.to_str(1)     # "World(Cytoplasm)"
```

## Entity Trees and DAT Boundaries

Entities form trees anchored to DATs. Understanding this relationship is key to working with alienbio.

### Core Invariants

1. **Entities are always valid**: Every entity is always attached to a tree with a DAT anchor. There are no "detached" or "invalid" entities.

2. **Each DAT has exactly one root entity**: The root has `_top` pointing to a Dat. All other entities have `_top` pointing to their root Entity.

3. **Parent chains stay within a DAT**: Walking up `_parent` from any entity eventually reaches the root of that DAT.

4. **Cross-DAT connections are references, not parent-child**: When an entity needs to reference another DAT's content (e.g., a World referencing a Chemistry), it stores a reference string, not a parent-child link.

### The Orphan System

When an entity is detached from its parent (via `detach()` or `set_parent(None)`), it moves to a special **orphan root** instead of becoming invalid:

```python
child.detach()
print(child)  # "ORPHAN:child"
child.dat()   # Returns the orphan DAT (valid but can't be saved)

# Can re-attach later
child.set_parent(new_parent)
print(child)  # "W:new_parent.child"
```

This ensures entities are always valid and can be inspected or re-attached. The `ORPHAN:` prefix makes it obvious when something is orphaned.

### Example Structure

```
DAT: runs/exp1
└── Run (root, _top=Dat)
    └── World (_parent=Run, _top=Run)
        ├── Cytoplasm (_parent=World, _top=Run)
        │   └── Glucose (_parent=Cytoplasm, _top=Run)
        └── chemistry: <D:chem/kegg1>  ← reference, NOT child

DAT: chem/kegg1
└── Chemistry (root, _top=Dat)
    ├── Molecule (_parent=Chemistry, _top=Chemistry)
    └── Reaction (_parent=Chemistry, _top=Chemistry)

ORPHAN DAT (virtual, not saved)
└── orphans (root)
    └── DetachedEntity (_parent=orphans, _top=orphans)
```

### Why This Matters

- **Always valid**: Entities can always be inspected, printed, and re-attached
- **Single parent**: An entity has exactly one parent, avoiding graph complexity
- **Independent loading**: Each DAT can be loaded independently
- **Shared references**: The same Chemistry can be referenced by multiple Worlds
- **Clear boundaries**: The DAT defines what gets saved together

### Name Resolution

Full names are computed by walking up the parent chain to the DAT anchor:

```python
def full_name(self) -> str:
    if not isinstance(self._top, Entity):  # I am root
        return self._top.get_path_name()  # e.g., "runs/exp1"
    return f"{self._parent.full_name}.{self._local_name}"
```

## See Also

- [[IO]] - Prefix bindings, formatting, lookup, persistence, create_root
- [[ABIO DAT]] - DAT storage integration
