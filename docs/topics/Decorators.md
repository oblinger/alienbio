[[ABIO docs]] → [[ABIO Topics]]

# Decorators
**Module**: `alienbio.spec_lang`

Python decorators for registering functions and classes in the ABIO system. All decorators and YAML tag implementations live in the `spec_lang` module.

---

## Type Registration

Type registration is done via **Entity subclassing**, not decorators:

```python
from alienbio import Entity

class Chemistry(Entity):
    molecules: dict
    reactions: dict
```

- Subclassing `Entity` makes a class a biotype automatically
- Entity subclasses are hydratable/dehydratable via `to_dict()`/`from_dict()` methods
- On load: `{"_type": "Chemistry", ...}` → `Chemistry(...)`
- On save: `Chemistry(...)` → `{"_type": "Chemistry", ...}`

See [[Entity]] for details on the Entity base class.

---

## Function Decorators

All function decorators inherit from `@fn` and share common metadata.

### `@fn`

Base decorator for all functions. Stores metadata for documentation, plots, and tooling.

```python
@fn(summary="One-liner for plots/tables",
    range=(0.0, 1.0),
    category="scoring.process",        # arbitrary additional metadata
    reference="Author, Year")
def function_name(args):
    """Detailed docstring for documentation."""
    ...
```

| Metadata | Required | Description |
|----------|----------|-------------|
| `summary` | Yes | Short description for plots/tables |
| `range` | Yes* | Expected output range (*not required for actions) |
| (other) | No | Arbitrary kwargs stored as `fn.meta[key]` |

---

### `@scoring`

Evaluation metrics for scenarios. Used by `sim.results()` to compute final scores.

```python
@scoring(summary="Population health of protected species",
         range=(0.0, 1.0),
         higher_is_better=True)
def population_health(timeline, species):
    """Measures final population health."""
    ...
```

| Metadata | Description |
|----------|-------------|
| `higher_is_better` | Direction of optimization |

---

### `@action`

Agent actions that modify simulation state. Called via `sim.action(name, ...)`.

```python
@action(summary="Add feedstock molecules to a region",
        targets="regions",
        reversible=False,
        cost=1.0)
def add_feedstock(sim, region, molecule, amount):
    """Add molecules from feedstock to substrate."""
    ...
```

| Metadata | Description |
|----------|-------------|
| `targets` | What the action operates on (regions, organisms, etc.) |
| `reversible` | Whether effects can be undone |
| `cost` | Resource cost of taking this action |

---

### `@measurement`

Agent observations that read simulation state. Called via `sim.measure(name, ...)`.

```python
@measurement(summary="Sample substrate concentrations",
             targets="regions",
             cost="none")
def sample_substrate(sim, region):
    """Get molecule concentrations in a region."""
    return sim.get_concentrations(region)
```

| Metadata | Description |
|----------|-------------|
| `targets` | What can be observed (regions, organisms, etc.) |
| `returns` | Description of return value structure |
| `cost` | Resource cost of taking this measurement |

---

### `@rate`

Reaction rate laws for chemistry. Used in reaction definitions.

```python
@rate(summary="Mass action rate law",
      range=(0.0, float('inf')))
def mass_action(ctx, k=0.1):
    """Derives rate from equation using Law of Mass Action."""
    ...
```

**Future:** Rate functions will be JIT-compiled via JAX for GPU acceleration.

---

### `@factory`

Registers an implementation class for a protocol. Multiple implementations can exist for each protocol.

```python
@factory(name="reference", protocol=Simulator)
class ReferenceSimulatorImpl(Simulator):
    """Reference implementation - accurate but slow."""

    def __init__(self, spec=None):
        self.chemistry = spec
        ...

@factory(name="fast", protocol=Simulator)
class FastSimulatorImpl(Simulator):
    """Optimized implementation - faster but approximations."""
    ...
```

| Parameter | Description |
|-----------|-------------|
| `name` | Implementation name (e.g., "reference", "fast") |
| `protocol` | Protocol class this implements |

**Creating instances with `bio.create()`:**

```python
from alienbio import bio

# Create with default implementation
sim = bio.create(Simulator, spec=chemistry)

# Create with specific implementation
sim = bio.create(Simulator, name="fast", spec=chemistry)

# Assign to pegboard for global access
bio.sim = bio.create(Simulator, spec=chemistry)

# Ensure pattern (only create if not set)
bio.sim = bio.sim or bio.create(Simulator, spec=chemistry)
```

**Resolution order:**

1. `name` parameter — explicit programmatic choice
2. Config default — `~/.config/alienbio/defaults.yaml`
3. Error — no silent fallback

**Config defaults:**

```yaml
# ~/.config/alienbio/defaults.yaml
Simulator: reference
Chemistry: standard
```

See [[Factory Pegboard API]] for full documentation.

---

## Summary Table

| Decorator/Pattern | Purpose | Registration | Called via |
|-------------------|---------|--------------|------------|
| `Entity` subclass | Class hydration | automatic | `Bio.fetch()` |
| `@fn` | Base function | — | direct call |
| `@scoring` | Evaluation metrics | scoring registry | `sim.results()` |
| `@action` | Agent actions | action registry | `sim.action()` |
| `@measurement` | Agent observations | measurement registry | `sim.measure()` |
| `@rate` | Reaction rates | rate registry | reaction evaluation |
| `@factory` | Multiple implementations | factory registry | `bio.create()` |

---

## Implementation Notes

All decorators assume the decorated functions/classes are loaded into the environment before use. This happens via:
- `spec.include("functions.py")` — loads Python file, decorators register automatically
- Direct import in Python code

The registries are global singletons. Registration happens at decoration time (module load), not at call time.

---

## See Also

- [[Spec Language]] — YAML syntax and tags (`!ev`, `!ref`, `!include`)
- [[Bio]] — Loading and hydration
- [[Entity]] — Base class for hydratable types
- [[Factory Pegboard API]] — Factory pattern and Bio pegboard
