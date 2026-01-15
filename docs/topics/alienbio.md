# alienbio
**Topic**: [[ABIO Topics]]
Top-level module providing access to the alienbio runtime.

## Public API

The `alienbio` module exports a curated set of symbols via `__all__`:

```python
__all__ = [
    "bio", "Bio",
    "hydrate", "dehydrate",
    "Entity", "Scenario", "Chemistry", "Simulator", "State",
]
```

### Main API

| Export | Type | Description |
|--------|------|-------------|
| `bio` | `Bio` | Module-level singleton for CLI and simple scripts |
| `Bio` | class | Environment class for sandboxes and testing |

### Module-level Functions

| Export | Description |
|--------|-------------|
| `hydrate(data)` | Convert dict with `_type` to typed object (advanced) |
| `dehydrate(obj)` | Convert typed object to dict with `_type` (advanced) |

### Core Protocols

| Export | Description |
|--------|-------------|
| `Entity` | Base class for all hydratable types |
| `Scenario` | Main runnable unit |
| `Chemistry` | Molecule and reaction definitions |
| `Simulator` | Simulation engine protocol |
| `State` | Simulation state protocol |

## Usage

### Simple Usage (Singleton)

```python
from alienbio import bio

# Fetch and run
scenario = bio.fetch("catalog/scenarios/mutualism")
result = bio.run("scenarios.baseline", seed=42)

# Build without running
built = bio.build("scenarios.test")
```

### Sandbox Usage (Instance)

```python
from alienbio import Bio

# Create isolated environment
sandbox = Bio()
scenario = sandbox.fetch("catalog/scenarios/test")
result = sandbox.run(scenario)
```

### Type Hints

```python
from alienbio import Entity, Scenario, Chemistry

class MyEntity(Entity):
    """Custom entity type."""
    ...

def process_scenario(s: Scenario) -> dict:
    """Type-hinted function."""
    ...
```

### Advanced: Implementation Classes

Implementation classes are importable but NOT in `__all__`:

```python
from alienbio import ReferenceSimulatorImpl  # works
from alienbio import *  # does NOT include ReferenceSimulatorImpl
```

## Star Import

`from alienbio import *` imports only the curated public API — not implementation classes or internal utilities.

## See Also

- [[Bio]] — Bio class API and methods
- [[Entity]] — Base class for hydratable types
- [[Decorators]] — `@factory` and other decorators
- [[ABIO DAT]] — dvc_dat integration for data storage
