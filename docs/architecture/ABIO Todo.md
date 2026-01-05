
# ABIO Todo
**Parent**: [[ABIO Sys]]

Current tasks and open questions for the Alien Biology system.

---

## Tasks

### B9 Spec Language Implementation

- [ ] **Create Bio class** — `load()`, `save()`, `sim()` static methods. See [[Bio]]
- [ ] **Create spec_lang module** — `alienbio/spec_lang` with YAML tags and decorators
- [ ] **Implement YAML tags** — `!ev` (evaluate), `!ref` (reference), `!include` (file inclusion)
- [ ] **Create function decorators** — `@biotype`, `@fn`, `@scoring`, `@action`, `@measurement`, `@rate`
- [ ] **Implement typed named elements** — `world.name`, `suite.name`, `scenario.name` YAML parsing with `_type` field
- [ ] **Implement defaults inheritance** — Deep merge for suite/scenario hierarchy
- [ ] **Enhance Simulator class** — Add `action()`, `measure()`, `results()` methods
- [ ] **Implement quiescence detection** — `run(quiet=..., delta=..., span=...)` for settling detection
- [ ] **Add feedstock concept** — Molecules the agent can add, with limits
- [ ] **Create action/measurement registry** — Dynamic registration via decorators

---

## Questions

### Architecture

1. ~~**Loader vs current IO**~~ — **Resolved**: Keep both. Spec handles filesystem/storage (specifiers like `catalog/worlds/mutualism`). IO handles runtime references within loaded data (`W:Lora.cytoplasm.glucose`). Orthogonal concerns.

2. ~~**World definition**~~ — **Resolved**: Three distinct classes: `WorldSpec` (declarative description from YAML), `WorldSimulator` (execution engine), `WorldState` (runtime snapshot). Flow: `world.name:` → WorldSpec → WorldSimulator → WorldState.

3. ~~**Simulator class**~~ — **Resolved**: Use WorldSimulator. B9's "Simulator" is the same as existing WorldSimulator.

### Implementation Details

4. ~~**Runtime expressions (`=`)**~~ — **Resolved**: Build Python reference simulator first, then JAX-accelerated simulator as drop-in replacement (Milestone 12). No Rust needed—JAX compiles Python to XLA/GPU code directly. Rate functions must be pure functional for JAX tracing.

5. ~~**YAML custom tags**~~ — **Resolved**: Use three YAML tags: `!ev` (evaluate expression), `!ref` (reference constant/object), `!include` (include file). No `$` or `=` prefix syntax.

6. ~~**Decorator module location**~~ — **Resolved**: Create `alienbio/spec_lang` module containing all decorators (`@biotype`, `@fn`, `@scoring`, `@action`, `@measurement`, `@rate`) and YAML tag implementations.

7. ~~**Action/Measurement registration**~~ — **Resolved**: Global singleton registries. `@action` and `@measurement` decorators register functions at decoration time (module load). Called via `sim.action(name, ...)` and `sim.measure(name, ...)`. See [[Decorators]].

### Terminology Mapping

8. ~~**Terminology alignment**~~ — **Resolved**:

| B9 Term | Current Code | Notes |
|---------|--------------|-------|
| `world` | `WorldSpec` | Declarative description from YAML |
| — | `WorldSimulator` | Execution engine |
| — | `WorldState` | Runtime snapshot |
| `molecules` | Molecule class | Exists |
| `reactions` | Reaction class | Exists |
| `containers` | Compartment + CompartmentTree | Exists |
| `feedstock` | — | New concept |
| `actions` | — | New (decorator-defined via `@action`) |
| `measurements` | — | New (decorator-defined via `@measurement`) |

---

## B10 Example Details

Key patterns from the mutualism example specification:

### Naming Conventions
| Prefix | Type | Examples |
|--------|------|----------|
| M | Molecules | ME (energy), MS (structural), MW (waste), MB (buffer), MC (catalyst) |
| K | Organisms | Krel, Kova, Kesh |
| L | Locations | Lora, Lesh, Lika |
| R | Reactions | R_energy_1, R_krel_1 |
| !ref | Constants | `!ref high_permeability` |

### Container Hierarchy
`ecosystems > regions > organisms > compartments > organelles`
- `outflows:` define transport FROM container to named targets
- `^` means parent container
- Target resolution: children first, then siblings, then up the tree

### Equation Syntax
- ASCII arrow: `2 ME1 -> ME2`
- Coefficient 0 = catalyst: `0 MC_krel + 2 ME1 -> ME2` (MC_krel required but not consumed)

### Organism Properties
- `maintained:` — molecules kept at constant concentration (enzymes)
- `operating_envelope:` — required ranges for survival
- `reproduction_threshold:` — molecule levels needed to reproduce
- `predation:` — predation rates on other species

### Additional Tasks from B10

- [ ] **Implement container hierarchy** — ecosystems > regions > organisms > compartments > organelles
- [ ] **Implement outflow/inflow system** — outflows define transport; inflows are implied
- [ ] **Add maintained molecules** — enzymes kept at constant concentration in organisms
- [ ] **Add operating envelope** — survival ranges for pH, temp, molecule concentrations
- [ ] **Add reproduction threshold** — molecule levels required for reproduction
- [ ] **Add predation mechanics** — species predation on other species
- [ ] **Implement template instantiation** — `contains: [{template: Krel, count: 80}]`
- [ ] **Add catalyst coefficient (0)** — required-but-not-consumed in reactions

---

## DAT Typed Key Extension

### Flat vs Nested: Pros and Cons

**Input YAML:**
```yaml
world.mutualism_ecosystem:
  molecules: {ME1: {...}}

suite.mutualism:
  defaults:
    world: !ref mutualism_ecosystem
  scenario.baseline:
    framing: "..."
  scenario.hidden:
    framing: "..."
```

**Option A: Flat (preserve dotted names)**
```python
{
    "world.mutualism_ecosystem": {"_type": "world", "molecules": {...}},
    "suite.mutualism": {"_type": "suite", "defaults": {...}},
    "suite.mutualism.scenario.baseline": {"_type": "scenario", "framing": "..."},
    "suite.mutualism.scenario.hidden": {"_type": "scenario", "framing": "..."},
}
```

| Pros | Cons |
|------|------|
| Simple to implement | Lookup requires knowing full path |
| Easy to serialize back to original | Parent-child relationship implicit |
| No ambiguity between children and properties | Iteration order matters |
| Direct iteration over all entries | |

**Option B: Nested (recursive structure)**
```python
{
    "mutualism_ecosystem": {"_type": "world", "molecules": {...}},
    "mutualism": {
        "_type": "suite",
        "defaults": {...},
        "baseline": {"_type": "scenario", "framing": "..."},
        "hidden": {"_type": "scenario", "framing": "..."},
    },
}
```

| Pros | Cons |
|------|------|
| Natural tree traversal | `_type` mixed with child keys |
| Inheritance walks up naturally | Hard to distinguish children from properties |
| Matches conceptual hierarchy | Harder to serialize back |
| `spec.mutualism.baseline` access | Need convention for reserved keys |

### Code Snippets

**Core transformation function:**
```python
def transform_typed_keys(data: dict, in_place: bool = False) -> dict:
    """Transform type.name keys to nested structure with _type field.

    Assumes first dotted segment is always a type.
    Example: "world.foo" -> {"foo": {"_type": "world", ...}}
    """
    result = {} if not in_place else data
    keys_to_remove = []

    for key, value in list(data.items()):
        if '.' in key and isinstance(value, dict):
            type_name, rest = key.split('.', 1)

            # Recursively transform nested typed keys in value
            if isinstance(value, dict):
                value = transform_typed_keys(value)

            # Add _type field
            value = {"_type": type_name, **value}

            # Store under the rest of the name
            result[rest] = value
            keys_to_remove.append(key)
        elif isinstance(value, dict):
            # Recurse into non-typed dicts
            result[key] = transform_typed_keys(value)
        else:
            result[key] = value

    if in_place:
        for key in keys_to_remove:
            del data[key]

    return result
```

**Inverse for serialization:**
```python
def restore_typed_keys(data: dict) -> dict:
    """Restore type.name keys from _type field for YAML output."""
    result = {}

    for key, value in data.items():
        if isinstance(value, dict) and "_type" in value:
            type_name = value.pop("_type")
            new_key = f"{type_name}.{key}"
            result[new_key] = restore_typed_keys(value)
        elif isinstance(value, dict):
            result[key] = restore_typed_keys(value)
        else:
            result[key] = value

    return result
```

**DAT integration hook:**
```python
# In DAT config or load call
def load_yaml(path, typed_keys=False):
    """Load YAML with optional typed key transformation."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if typed_keys:
        data = transform_typed_keys(data)

    return data
```

**Usage:**
```python
# Without typed keys (standard DAT)
spec = dat.load("mutualism.yaml")
# Returns: {"world.mutualism_ecosystem": {...}, "suite.mutualism": {...}}

# With typed keys
spec = dat.load("mutualism.yaml", typed_keys=True)
# Returns: {"mutualism_ecosystem": {"_type": "world", ...}, ...}
```

### Recommendation

Lean toward **nested** because:
1. B9 spec explicitly shows nested output format
2. Inheritance via `defaults:` is easier to implement with tree structure
3. Natural attribute access: `spec.mutualism.baseline`
4. Can add reserved key convention: keys starting with `_` are metadata, others are children
