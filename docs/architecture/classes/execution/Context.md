 [[Architecture Docs]] → [[ABIO execution]]

# Context

Runtime pegboard containing all major subsystems.

## Overview
Context is the root object graph for alienbio runtime. It serves as a pegboard where all major subsystems are attached as attributes. A single Context instance is held in a context variable, accessible globally via `Context.current()`.

| Property | Type | Description |
|----------|------|-------------|
| `config` | Config | System configuration and settings |
| `io` | IO | Entity I/O: prefixes, formatting, persistence |
| `simulator` | Simulator \| None | Rust or Python simulation engine |
| `world` | World \| None | Currently loaded world |
| `harness` | TestHarness \| None | Test execution runner |

| Method | Returns | Description |
|--------|---------|-------------|
| `current()` | Context | Get the active context (static) |
| `child(**overrides)` | Context | Create derived context with overrides |
| `create(config_path)` | Context | Standard initialization sequence |

## Discussion

### Usage Example
```python
# Create and enter context
with Context.create("config.yaml") as ctx:
    # Bind prefixes for convenient entity display
    ctx.io.bind_prefix("W", ctx.world)
    ctx.io.bind_prefix("M", ctx.world.molecules)

    # Entities use Context.current().io for printing
    print(some_molecule)  # -> M:glucose

    # Load/save via io
    dat = ctx.io.load("runs/exp1")
    ctx.io.save(results, "runs/exp1/output")

    # Run tests
    ctx.harness = TestHarness(experiments=[...])
    ctx.harness.run()
```

### Initialization Order
Standard initialization follows a defined sequence:

```python
@classmethod
def create(cls, config_path: Path | None = None) -> Context:
    # 1. Load config
    config = Config.load(config_path) if config_path else Config()

    # 2. Create context with config
    ctx = cls(config=config)

    # 3. Initialize data store
    ctx.data_store = DataStore(config.data_path)

    # 4. Connect simulator if available
    if config.use_rust_simulator:
        ctx.simulator = Simulator.connect()

    return ctx
```

### Thread/Async Safety
Uses Python's `contextvars` module, which provides proper isolation for threads and async tasks. Each thread/task can have its own active Context.

## Method Details

### `current() -> Context`
Get the active context.

**Returns:** The currently active Context

**Raises:**
- `RuntimeError`: If no context is active

### `child(**overrides) -> Context`
Create derived context with some values changed.

**Args:**
- `**overrides`: Attributes to override in the new context

**Returns:** New Context with specified overrides

## Protocol
```python
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Protocol, Optional

_context: ContextVar[Context | None] = ContextVar('context', default=None)

@dataclass
class Context:
    """Runtime pegboard for alienbio."""

    config: Config
    io: IO = field(default_factory=IO)
    simulator: Simulator | None = None
    world: World | None = None
    harness: TestHarness | None = None
    _token: Token | None = field(default=None, repr=False)

    @staticmethod
    def current() -> Context:
        """Get the active context. Raises if none active."""
        ctx = _context.get()
        if ctx is None:
            raise RuntimeError("No active Context")
        return ctx

    def __enter__(self) -> Context:
        self._token = _context.set(self)
        return self

    def __exit__(self, *args) -> None:
        _context.reset(self._token)

    def child(self, **overrides) -> Context:
        """Create derived context with some values changed."""
        ...
```

## See Also
- [[IO]] - Entity I/O component
- [[TestHarness]] - Test execution component
- [[ABIO execution]] - Parent subsystem
