# Entity
**Subsystem**: [[ABIO infra]] > Entities
Base class for all biology objects with tree structure and DAT anchoring.

## Overview
Entity is the root of the type hierarchy for all biology objects. It provides tree structure with parent/child relationships, DAT anchoring for filesystem persistence, type registry for subclass serialization, and context-aware string representation.

| Property | Type | Description |
|----------|------|-------------|
| `_local_name` | str | Name within parent's children dict |
| `_parent` | Entity? | Link to containing entity |
| `_children` | Dict[str, Entity] | Child entities by local name |
| `_top` | Entity \| Dat | Dat for root entities, root Entity for non-roots |
| `description` | str | Human-readable description |

| Method | Returns | Description |
|--------|---------|-------------|
| `head` | str | Type name for serialization (property) |
| `attributes()` | Dict | Semantic content (override in subclasses) |
| `dat()` | Dat | Get the DAT anchor for this entity's tree (O(1)) |
| `root()` | Entity | Get the root entity of this tree (O(1)) |
| `full_name` | str | Full path from DAT anchor |
| `to_dict(recursive)` | Dict | Convert to dictionary for serialization |
| `to_str(depth)` | str | Tree representation like `World(Cytoplasm(Glucose))` |
| `save()` | None | Save entity tree to entities.yaml (root only) |
| `detach()` | None | Detach from parent (moves to orphan root) |
| `set_parent(parent)` | None | Change parent (None → orphan root) |

## Discussion

### Three-Part Structure
Entities have a structure analogous to a function call:

| Part | Method/Property | Description |
|------|-----------------|-------------|
| **head** | `entity.head` | Type name: "Molecule", "Compartment" |
| **args** | `entity.children` | Child entities (nested content) |
| **attributes** | `entity.attributes()` | Semantic fields: name, description, custom |

### Head Registry
Entity subclasses are automatically registered for serialization via `__init_subclass__`:

```python
# Registered as "Molecule" (class name)
class Molecule(Entity):
    pass

# Registered as "Mol" (short head name)
class Molecule(Entity, head="Mol"):
    pass
```

Registry functions: `register_head()`, `get_entity_class()`, `get_registered_heads()`

### Entity Trees and DAT Boundaries
**Core Invariants:**
1. **Entities are always valid**: Every entity is attached to a tree with a DAT anchor
2. **Each DAT has exactly one root**: Root has `_top` pointing to Dat
3. **Parent chains stay within a DAT**: Walking up `_parent` reaches the DAT root
4. **Cross-DAT connections are references**: Stored as strings, not parent-child links

### The Orphan System
When detached, entities move to an orphan root instead of becoming invalid:

```python
child.detach()
print(child)  # "ORPHAN:child"
child.dat()   # Returns orphan DAT (valid but can't be saved)

child.set_parent(new_parent)  # Re-attach
print(child)  # "W:new_parent.child"
```

### Serialization

**to_dict():**
```python
molecule.to_dict()
# {"head": "M", "name": "glucose", "atoms": {"C": 6, "H": 12, "O": 6}}
```

**save():**
```python
world.save()  # Creates: dat_folder/entities.yaml
```

### String Representation
Uses context-aware formatting when available:

```python
ctx.io.bind_prefix("W", world)
print(glucose)  # "W:cytoplasm.glucose"
```

Falls back to `full_name` if no context or prefix.

**to_str(depth):**
```python
world.to_str()   # "World(Cytoplasm(Glucose, ATP))"
world.to_str(0)  # "World"
world.to_str(1)  # "World(Cytoplasm)"
```

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

## Method Details

### `attributes() -> Dict[str, Any]`
Semantic content of this entity. Override in subclasses.

**Returns:** Dict with 'name' and 'description'. Subclasses add their fields.

**Example:**
```python
class MoleculeImpl(Entity, head="Molecule"):
    def attributes(self) -> Dict[str, Any]:
        result = super().attributes()
        result["atoms"] = {atom.symbol: count for atom, count in self._atoms.items()}
        result["bdepth"] = self._bdepth
        return result
```

### `dat() -> Dat`
Get the DAT anchor for this entity's tree.

**Returns:** The Dat object anchoring this entity's tree (O(1) via `_top`)

### `full_name -> str`
Full path from DAT anchor.

**Returns:** Path like 'runs/exp1.cytoplasm.glucose'

## Protocol
```python
from typing import Dict, Any, Optional, Iterator, Protocol

class Entity(Protocol):
    """Base class for all biology objects."""

    _local_name: str
    _parent: Optional["Entity"]
    _children: Dict[str, "Entity"]
    _top: "Entity" | "Dat"
    description: str

    @property
    def head(self) -> str:
        """Type name for serialization."""
        ...

    def attributes(self) -> Dict[str, Any]:
        """Semantic content (override in subclasses)."""
        ...

    def dat(self) -> "Dat":
        """Get the DAT anchor for this entity's tree."""
        ...

    def root(self) -> "Entity":
        """Get the root entity of this tree."""
        ...

    @property
    def full_name(self) -> str:
        """Full path from DAT anchor."""
        ...

    def to_dict(self, recursive: bool = False) -> Dict[str, Any]:
        """Convert to dict with 'head' field for dispatch."""
        ...

    def to_str(self, depth: int = -1) -> str:
        """Tree representation."""
        ...

    def save(self) -> None:
        """Save entity tree to entities.yaml."""
        ...

    def detach(self) -> None:
        """Detach from parent (moves to orphan root)."""
        ...

    def set_parent(self, parent: Optional["Entity"]) -> None:
        """Change parent (None → orphan root)."""
        ...
```

## See Also
- [[IO]] - Prefix bindings, formatting, lookup, persistence
- [[ABIO DAT]] - DAT storage integration
- [[Context]] - Runtime context for entity display
