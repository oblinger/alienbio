# Factory Pattern

The factory pattern allows multiple implementations of a protocol to be registered and selected at runtime.

## Overview

Protocols define interfaces (e.g., `Simulator`, `Chemistry`). Multiple implementations can exist for each protocol (e.g., `ReferenceSimulatorImpl`, `FastSimulatorImpl`). The factory pattern enables:

- Registration of implementations via `@factory` decorator
- Selection of implementation at runtime via `bio.create()`
- Default implementation configuration

## Usage

### Registering Implementations

```python
from alienbio.spec_lang.decorators import factory

@factory(name="reference", protocol=Simulator)
class ReferenceSimulatorImpl(Simulator):
    """Reference implementation - accurate but slow."""
    def __init__(self, spec=None):
        ...

@factory(name="fast", protocol=Simulator, default=True)
class FastSimulatorImpl(Simulator):
    """Optimized implementation - faster with approximations."""
    ...
```

### Creating Instances

```python
from alienbio import bio

# Use default implementation
sim = bio.create(Simulator, spec=chemistry)

# Use specific implementation
sim = bio.create(Simulator, name="reference", spec=chemistry)
```

## Implementation Resolution Order

When creating an instance, the implementation is selected in this order:

1. **`name` parameter** — Explicit selection via `bio.create(..., name="fast")`
2. **Spec field** — `impl` field in the spec dict
3. **Default registration** — Implementation registered with `default=True`
4. **Error** — If no implementation can be resolved

## Registry

The factory registry is maintained on the `Bio` class:

- `_factories: dict[type, dict[str, type]]` — Protocol → {name → impl_class}
- `_factory_defaults: dict[type, str]` — Protocol → default_name

## Currently Registered Factories

| Protocol | Implementations | Default |
|----------|-----------------|---------|
| `Simulator` | `reference` | `reference` |

## See Also

- [[Bio]] — Main API class
- [[Simulator]] — Simulator protocol
