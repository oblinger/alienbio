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
| _dat | Dat? | Optional anchor to filesystem |
| description | str | Human-readable description |

| Methods | Description |
|---------|-------------|
| full_name | Full path computed by walking up to DAT anchor |
| to_dict | Convert to dictionary for serialization |
| to_str | Tree representation like `World(Cytoplasm(Glucose))` |
| save | Save entity tree to entities.yaml in DAT folder |
| add_child | Add a child entity |
| remove_child | Remove a child by name |
| root | Get the topmost ancestor |
| ancestors | Iterate over ancestors to root |
| descendants | Iterate over all descendants |
| find_dat_anchor | Find nearest DAT anchor walking up |

## Type Registry

Entity subclasses are automatically registered for serialization via `__init_subclass__`:

```python
# Registered as "Molecule" (class name)
class Molecule(Entity):
    pass

# Registered as "M" (short type_name)
class Molecule(Entity, type_name="M"):
    pass
```

Registry functions:
- `register_entity_type(name, cls)` - Register a type manually
- `get_entity_type(name)` - Look up type by name
- `get_entity_types()` - Get all registered types

## Protocol Definition

```python
from typing import Dict, Any, Optional, Iterator

class Entity:
    """Base class for all biology objects."""

    _local_name: str
    _parent: Optional["Entity"]
    _children: Dict[str, "Entity"]
    _dat: Optional["Dat"]
    description: str

    def __init_subclass__(cls, type_name: str = None, **kwargs) -> None:
        """Auto-register subclasses. Use type_name for short alias."""
        ...

    @property
    def full_name(self) -> str:
        """Full path from DAT anchor (e.g., 'runs/exp1.cytoplasm.glucose')."""
        ...

    def to_dict(self, recursive: bool = False) -> Dict[str, Any]:
        """Convert to dict. Includes 'type' field for subclass dispatch."""
        ...

    def to_str(self, depth: int = -1) -> str:
        """Tree representation like 'World(Cytoplasm(Glucose))'."""
        ...

    def save(self) -> None:
        """Save entity tree to entities.yaml in DAT folder."""
        ...

    def __str__(self) -> str:
        """Returns PREFIX:path via context, or full_name as fallback."""
        ...
```

## Serialization

### to_dict()

Converts entity to dictionary with type information:

```python
molecule.to_dict()
# {"type": "M", "name": "glucose", "formula": "C6H12O6"}

world.to_dict(recursive=True)
# {
#   "type": "Entity",
#   "name": "world",
#   "children": {
#     "cytoplasm": {"type": "C", "name": "cytoplasm", ...}
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

## Naming

Entities derive their names from their position in the containment hierarchy. See [[Entity-naming]] for full details on:
- Name resolution algorithm
- DAT anchors
- Prefix system (PREFIX:path format)
- Display conventions

## See Also

- [[Entity-naming]] - Naming scheme, prefixes, display format
- [[IO]] - Prefix bindings, formatting, lookup, persistence
- [[ABIO DAT]] - DAT storage integration
