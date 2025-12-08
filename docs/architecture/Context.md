# Context
**Subsystem**: [[ABIO execution]]
Runtime pegboard containing all major subsystems.

## Description
Context is the root object graph for alienbio runtime. It serves as a pegboard where all major subsystems are attached as attributes. A single Context instance is held in a context variable, accessible globally via `Context.current()`.

| Properties | Type | Description |
|----------|------|-------------|
| config | Config | System configuration and settings |
| prefixes | dict[str, EntitySource] | Prefix bindings for entity display |
| simulator | Simulator \| None | Rust or Python simulation engine |
| data_store | DataStore \| None | Persistent entity storage |
| world | World \| None | Currently loaded world |
| harness | TestHarness \| None | Test execution runner |

| Methods | Description |
|---------|-------------|
| current | Get the active context (static) |
| child | Create derived context with overrides |

## Protocol Definition
```python
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Protocol

_context: ContextVar[Context | None] = ContextVar('context', default=None)

@dataclass
class Context:
    """Runtime pegboard for alienbio."""

    # Infrastructure (always present)
    config: Config
    prefixes: dict[str, EntitySource] = field(default_factory=dict)

    # Connections (initialized on demand)
    simulator: Simulator | None = None
    data_store: DataStore | None = None

    # Biology (loaded per-session)
    world: World | None = None

    # Execution (present during test runs)
    harness: TestHarness | None = None

    # Internal
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

## Methods
### current() -> Context
Get the active context. Raises RuntimeError if none active.

### child(**overrides) -> Context
Create derived context with some values changed.

## Initialization Order
Standard initialization follows a defined sequence:

```python
@classmethod
def create(cls, config_path: Path | None = None) -> Context:
    """Standard initialization sequence."""
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

## Usage
```python
# Create and enter context
with Context.create("config.yaml") as ctx:
    ctx.prefixes["M"] = ctx.world.molecules

    # Entities use Context.current() for printing
    print(some_molecule)  # -> M:glucose

    # Run tests
    ctx.harness = TestHarness(experiments=[...])
    ctx.harness.run()
```

## Thread/Async Safety
Uses Python's `contextvars` module, which provides proper isolation for threads and async tasks. Each thread/task can have its own active Context.

## See Also
- [[ABIO execution]] - Parent subsystem
- [[TestHarness]] - Test execution component
- [[Print-format]] - How prefixes are used for display
