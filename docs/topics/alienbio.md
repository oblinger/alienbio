# alienbio
**Topic**: [[ABIO Topics]]
Top-level module providing access to the alienbio runtime.

## Functions

| Function | Description |
|----------|-------------|
| `do(name)` | Resolve dotted name to object |
| `create(spec)` | Instantiate from prototype specification |
| `load(path)` | Load entity from data path |
| `save(obj, path)` | Save entity to data path |
| `parse(string)` | Reconstruct entity from string |
| `ctx()` | Access runtime context |
| `o` | Proxy for context attribute access |

## Usage

```python
from alienbio import do, load, save, create, parse, ctx, o

# Resolve named objects
molecule = do("catalog.kegg1.molecule_gen")
dataset = do("data.upstream.kegg.2024.1")

# Load and save entities
dataset = load("data/upstream/kegg/2024.1")
save(molecules, "data/derived/kegg1/molecules")

# Instantiate from prototypes
gen = create("catalog.kegg1.molecule_gen")
mol = create({"_proto": "catalog.kegg1.molecule_gen", "params": {...}})

# Parse string representations
mol = parse("M:glucose")

# Access context directly
config = ctx().config
simulator = ctx().simulator

# Access via proxy
o.simulator.step()
```

## Context Access

The runtime context is stored in a `ContextVar` for thread/async safety. Three access patterns:

1. **Wrapper functions** (`do`, `load`, `save`, `create`) - delegate to context, excellent IDE support
2. **Direct access** (`ctx()`) - returns full Context object
3. **Proxy object** (`o`) - attribute delegation for less common operations

## Implementation

All exports are defined in `alienbio/__init__.py`:

```python
from contextvars import ContextVar

_ctx: ContextVar["Context"] = ContextVar("alienbio_context")

def ctx() -> "Context":
    return _ctx.get()

def do(name: str):
    return _ctx.get().do(name)

def load(path: str):
    return _ctx.get().load(path)

def save(obj, path: str):
    return _ctx.get().save(obj, path)

def create(spec):
    return _ctx.get().create(spec)

def parse(string: str):
    return _ctx.get().parse(string)

class _ContextProxy:
    def __getattr__(self, name):
        return getattr(_ctx.get(), name)

o = _ContextProxy()
```

## See Also

- [[Context]] - Runtime pegboard protocol
- [[ABIO DAT]] - dvc_dat integration and data management
- [[Entity-naming]] - Entity naming and display format
