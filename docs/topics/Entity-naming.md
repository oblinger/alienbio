# Entity-naming
**Topic**: [[ABIO Topics]]
Entity naming, qualified paths, DAT anchors, and display format.

## Overview

Entities in alienbio have hierarchical names derived from their position in the containment tree. Names are resolved by walking up the parent chain until a DAT anchor is found, then building the path from there.

## Entity Structure

Every entity has these naming-related fields:

| Field | Type | Description |
|-------|------|-------------|
| `_local_name` | str | Name within parent's children dict |
| `_parent` | Entity? | Link to containing entity |
| `_children` | Dict[str, Entity] | Child entities by local name |
| `_dat` | Dat? | Optional anchor to filesystem |

Properties:
- `local_name` - Name within parent's children dict
- `full_name` - Full path from DAT anchor (e.g., `runs/exp1.cytoplasm.glucose`)

**Invariant**: An entity must have either `_dat` or `_parent` (or both). Orphan entities with neither are invalid.

## Name Resolution

Full names are computed by walking up the parent chain:

```python
def full_name(self) -> str:
    """Walk up until we hit a DAT anchor, then build path."""
    if self._dat is not None:
        return self._dat.get_path_name()
    if self._parent is None:
        raise ValueError("Entity has no DAT anchor and no parent")
    return f"{self._parent.full_name}.{self._local_name}"
```

When an entity has both `_parent` and `_dat`, it can be named two ways:
- From the DAT directly: `runs/exp1`
- From parent: `runs/experiment.world1`

When printing, the first DAT found walking up wins (most specific name).

## Prefix System

Prefixes provide shorthand for frequently-used DAT paths. The format is `PREFIX:name`.

### Conventional Prefixes

Single-letter prefixes for common entity types:

| Prefix | Binds To | Example |
|--------|----------|---------|
| D | Data root (always) | `D:runs/exp1.world1` |
| R | Current run DAT | `R:world1.compartment` |
| W | Current world | `W:compartment.glucose` |
| E | Current experiment | `E:run1.world1` |

Multi-letter prefixes for special cases:

| Prefix | Binds To | Description |
|--------|----------|-------------|
| dat | Same as D: | Explicit data reference |
| cfg | Configuration | Config and settings |
| tmp | Temporary | Transient/scratch entities |

### Prefix Bindings

Prefixes are bound via [[IO]] (accessed through [[Context]]). The `D:` prefix is always bound to the data root as an escape hatch - every entity can be named with `D:` even if no other prefix applies.

```python
# Example prefix bindings in a run
ctx.io.bind_prefix("R", current_run_dat)
ctx.io.bind_prefix("W", current_world_dat)

# Now these are equivalent:
# D:runs/exp1/world1.compartment.glucose
# R:world1.compartment.glucose
# W:compartment.glucose
```

Keep prefixes few - too many creates confusion about what's happening.

## Display Format

Entity references use prefix notation: `PREFIX:path.to.entity`

### String Representation

Every entity implements `__str__` and `__repr__`:
- `__str__`: Short prefix notation - `W:compartment.glucose`
- `__repr__`: Full reconstructible form with class and fields

### Examples

```
# Full paths from data root
D:chem/kegg1/2024.2              # A chemistry DAT
D:runs/exp1.world1.cytoplasm     # Compartment in experiment

# With prefix shortcuts
R:world1.cytoplasm.glucose       # R: bound to runs/exp1
W:cytoplasm.glucose              # W: bound to world1

# Entity type prefixes (conventional)
M:glucose                        # Molecule
R:glycolysis_1                   # Reaction
P:citric_acid                    # Pathway
```

## Serialization

Entities serialize to YAML for storage:

```yaml
name: glucose
atoms:
  C: 6
  H: 12
  O: 6
```

The `serialize()` and `deserialize()` methods on [[Entity]] handle conversion. See [[ABIO DAT]] for how entities integrate with DAT storage.

## See Also

- [[Entity]] - Base protocol with serialize/deserialize methods
- [[IO]] - Prefix bindings, formatting, parsing, persistence
- [[Context]] - Runtime pegboard containing IO
- [[ABIO DAT]] - DAT storage integration
