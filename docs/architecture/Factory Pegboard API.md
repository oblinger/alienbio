# Factory Pegboard API

**Status**: PROPOSED — awaiting approval before implementation

Bio serves as the pegboard for active component instances. The factory creates instances; Python assignment sets them.

---

## Overview

```python
from alienbio import bio, Bio

# Create and assign to pegboard
bio.sim = bio.create(Simulator, spec=chemistry)
bio.io = bio.create(IO)

# Ensure pattern (only create if not set)
bio.sim = bio.sim or bio.create(Simulator, spec=chemistry)

# Replace with different implementation
bio.sim = bio.create(Simulator, name="fast", spec=chemistry)
```

**Key principle**: `bio.create()` just creates and returns. No side effects. Assignment is explicit Python.

---

## Bio Component Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `bio.io` | `IO` | Entity I/O: prefixes, formatting, persistence |
| `bio.sim` | `Simulator` | Active simulation engine |
| `bio.agent` | `Agent` | Active agent for scenarios |
| `bio.chem` | `Chemistry` | Active chemistry definition |

These are simple properties with getters/setters. No lazy initialization magic.

---

## `bio.create()` — Factory Method

```python
bio.create(protocol, name=None, spec=None) -> instance
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `protocol` | `type` | Protocol class (Simulator, IO, Agent, etc.) |
| `name` | `str \| None` | Implementation name. If None, uses config default. |
| `spec` | `Any \| None` | Data/configuration for the instance. |

**Returns**: New instance of the specified implementation.

**Raises**: `KeyError` if no implementation found for name/protocol.

### Resolution Order

When determining which implementation to use:

1. `name` parameter — explicit choice
2. Config default — `~/.config/alienbio/defaults.yaml`
3. Error — no silent fallback

---

## `@factory` Decorator

Registers an implementation for a protocol:

```python
@factory(name="reference", protocol=Simulator)
class ReferenceSimulatorImpl(Simulator):
    """Reference implementation - accurate but slow."""

    def __init__(self, spec):
        self.chemistry = spec
        ...

@factory(name="fast", protocol=Simulator)
class FastSimulatorImpl(Simulator):
    """Optimized implementation."""
    ...
```

See [[Decorators]] for full `@factory` documentation.

---

## Usage Patterns

### Initialization

```python
from alienbio import bio

# At startup, initialize the pegboard
bio.io = bio.create(IO)
bio.sim = bio.create(Simulator, spec=chemistry)
```

### Ensure (create if not set)

```python
# Only create if not already set
bio.sim = bio.sim or bio.create(Simulator, spec=chemistry)
```

### Replace

```python
# Switch implementations
bio.sim = bio.create(Simulator, name="fast", spec=chemistry)
```

### Multiple Instances (no pegboard)

```python
# Create without assigning to pegboard
sim1 = bio.create(Simulator, spec=chem1)
sim2 = bio.create(Simulator, spec=chem2)

results1 = sim1.run(1000)
results2 = sim2.run(1000)
```

### Isolated Sandbox

```python
# Fresh Bio instance for isolation
sandbox = Bio()
sandbox.io = sandbox.create(IO)
sandbox.sim = sandbox.create(Simulator, spec=test_chemistry)
```

---

## Implementation Notes

### Bio Class Changes

```python
class Bio:
    def __init__(self):
        self._io: IO | None = None
        self._sim: Simulator | None = None
        self._agent: Agent | None = None
        self._chem: Chemistry | None = None

    @property
    def io(self) -> IO | None:
        return self._io

    @io.setter
    def io(self, value: IO) -> None:
        self._io = value

    # Similar for sim, agent, chem...

    def create(
        self,
        protocol: type[T],
        name: str | None = None,
        spec: Any = None,
    ) -> T:
        """Create instance from factory."""
        impl_class = _resolve_factory(protocol, name)
        return impl_class(spec) if spec else impl_class()
```

### Removal of io() Singleton

Once Bio manages IO, remove from `io.py`:
- `io()` function
- `set_io()` function
- `_io_var` ContextVar

Code changes: `io()` → `bio.io`

---

## See Also

- [[Decorators]] — `@factory` decorator
- [[Bio]] — Bio class API
