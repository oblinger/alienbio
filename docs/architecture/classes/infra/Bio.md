 [[Architecture Docs]] → [[ABIO infra]]

# Bio

Environment class for fetching, hydration, and persistence of alien biology objects stored in DAT folders. For YAML syntax, see [[Spec Language Reference]]. For the command-line interface, see [Commands](../../ABIO Commands.md).

---

## Implementation Notes

**READ THIS FIRST** if implementing or refactoring Bio.

### Current State → Target State

The current code has `_BioCompat` with static method wrappers. The target is:

1. **Bio as instance class** — `Bio()` creates fresh environment with its own DAT context and scope chain
2. **Module singleton** — `from alienbio import bio` provides a pre-created singleton for CLI
3. **No static wrappers** — All methods are instance methods; `_BioCompat` goes away

### Refactoring Steps (M1.5)

1. Add `_current_dat: Path | None` and `_scope: Scope` instance variables to `Bio.__init__()`
2. Convert all `_BioCompat` static methods to delegate to a module-level `_singleton` instance
3. Create `bio = Bio()` singleton in `alienbio/__init__.py`
4. Update CLI commands to use `from alienbio import bio` then call `bio.method()`
5. Remove `_BioCompat` class once all callers use instance or singleton pattern

### Hydration Consolidation

There are currently two hydrate paths (`eval.hydrate()` and `decorators.hydrate()`). Target:

- `Bio.hydrate(data)` is the single entry point
- It orchestrates three phases: (1) resolve `!include`, (2) resolve `!ref`, (3) bottom-up type construction
- Remove `eval.hydrate()` or make it private

See [[ABIO Roadmap#M1.5 — Refactoring & Cleanup]] for full task list.

---

## Overview

Bio is an environment class that can be instantiated for isolated sandboxes or used via the module-level singleton for CLI commands.

### Dual-Use Pattern

**Instance pattern** — Create isolated environments in your code:
```python
bio = Bio()                    # fresh environment, anonymous DAT
scenario = bio.fetch("catalog/scenarios/mutualism")
bio.run("catalog/jobs/test")

bio2 = Bio(dat="experiments/baseline")  # environment wrapping specific DAT
bio2.fetch("scenarios/test")
```

**Singleton pattern** — Use the module-level singleton for CLI and simple scripts:
```python
from alienbio import bio      # the singleton
bio.run("catalog/jobs/test")
```

Each Bio instance owns its own DAT context and scope chain, enabling:
- **Testability** — Create isolated Bio instances for tests
- **Sandboxing** — Multiple independent environments in same process
- **CLI simplicity** — Singleton "just works" for command line

### Methods

See [Commands](../../ABIO Commands.md) for detailed documentation on each method.

| Method | Returns | Description |
|--------|---------|-------------|
| [fetch(specifier)](../../commands/ABIO Fetch.md) | `Any` | Load, expand, and **hydrate** → typed object |
| [lookup(name)](../../commands/ABIO Lookup.md) | `Any` | Resolve dotted name (Python modules → cwd) |
| [build(target)](../../commands/ABIO Build.md) | `Any` | Template instantiation → built scenario |
| [run(target)](../../commands/ABIO Run.md) | `Result` | Execute a runnable → result |
| [report(results, ...)](../../commands/ABIO Report.md) | `None` | Generate formatted report from results |
| `store(specifier, obj)` | `None` | Dehydrate and store object |
| `cd(path=None)` | `Path` | Get/set current DAT context |
| [create_simulator(...)](../../commands/ABIO Sim.md) | `Simulator` | Create Simulator from Chemistry |
| [register_agent(...)](../../commands/ABIO Agent.md) | `None` | Register an agent implementation |
| [create_agent(...)](../../commands/ABIO Agent.md) | `Agent` | Create agent instance for scenario |
| [hydrate(data)](../../commands/ABIO Hydrate.md) | `Any` | Convert dict with `_type` to typed object (advanced) |
| [dehydrate(obj)](../../commands/ABIO Dehydrate.md) | `dict` | Convert typed object to dict with `_type` (advanced) |

### Implicit Chaining

When passed a string, each method implicitly calls the previous stage:

```
run(string) → build(string) → fetch(string) → load file
     ↓              ↓              ↓
  execute    template expand    hydrate
```

- `bio.fetch("path")` — loads and hydrates to typed object
- `bio.build("path")` — fetches first, then does template instantiation
- `bio.run("path")` — builds first (which fetches), then executes

When passed an already-loaded object, the method operates on it directly:
- `bio.build(scenario_dict)` — instantiates without fetching
- `bio.run(scenario)` — executes without building

**Note:** `hydrate()` and `dehydrate()` are advanced methods. Most users should use `fetch()` and `store()` which handle the full pipeline.

## Discussion

### Specifier Syntax

A **specifier** identifies a fetchable object. Two styles:

| Style | Example | Routing |
|-------|---------|---------|
| **Path** (has `/`) | `catalog/scenarios/mutualism` | Direct DAT load |
| **Dotted** (no `/`) | `x1.results.summary` | [Bio.lookup()](../../commands/ABIO Lookup.md) |

```python
# Path-style: direct DAT load
bio.fetch("catalog/scenarios/mutualism")
# → loads catalog/scenarios/mutualism/index.yaml

# Dotted-style: calls Bio.lookup()
bio.fetch("x1.results.summary")
# → Python modules first, then cwd filesystem
```

See [Bio.lookup()](../../commands/ABIO Lookup.md) for full resolution rules.

### Scope-Aware Fetching
See [[Scope]] for details on lexical scoping and the module pattern.

```python
bio = Bio()

# Fetch specific scenario through specifier
scenario = bio.fetch("catalog/scenarios/mutualism/experiments.baseline")

# Or load module and navigate manually
module = bio.fetch("catalog/scenarios/mutualism", as_scope=True)
scenario = module["experiments"]["baseline"]
```

### Hydration
When fetching, Bio uses the `@biotype` registry to hydrate YAML into typed Python objects:

```yaml
# In file: spec.yaml
scenario.mutualism:
  chemistry:
    molecules: {...}
    reactions: {...}
  containers: {...}
  interface:
    actions: [add_feedstock, adjust_temp]
    measurements: [sample_substrate, population_count]
```

```python
bio = Bio()
scenario = bio.fetch("catalog/scenarios/mutualism")
print(type(scenario))  # <class 'Scenario'>
print(scenario.chemistry.molecules)  # typed access
```

### Usage Examples

**Fetching and running a scenario:**
```python
bio = Bio()
scenario = bio.fetch("catalog/scenarios/mutualism")
sim = bio.create_simulator(scenario.chemistry)
while not sim.terminated:
    substrate = sim.measure("sample_substrate", "Lora")
    if substrate["ME1"] < 0.5:
        sim.action("add_feedstock", "Lora", "ME1", 2.0)
    sim.step()
result = sim.results()
```

**Storing objects:**
```python
bio = Bio()
bio.store("catalog/scenarios/custom", my_scenario)
bio.store("catalog/chemistries/custom", my_chemistry)
```

## Method Details

### `bio.fetch(specifier, raw=False)`
Fetch and hydrate an object by specifier.

**Args:**
- `specifier`: A specifier string — either dotted name or path (see below)
- `raw`: If True, return raw dict without hydration

**Returns:** Hydrated object, or dict if `raw=True`

**Specifier routing:**
- **Dots before first slash** → calls `lookup()` for dotted name resolution
- **No dots before slash** → DAT load from filesystem path

```python
bio.fetch("catalog.scenarios.mutualism")  # dotted → lookup()
bio.fetch("catalog/scenarios/mutualism")  # path → DAT load
```

**Behavior (DAT load):**
1. Parse specifier into DAT path and name within module
2. Load the DAT's `index.yaml`
3. Resolve includes, transform typed keys, resolve refs, expand defaults
4. Wire up scope parent chains (from `extends:` declarations)
5. If `raw=True`: return the expanded dict
6. Hydrate based on `_type` field via `@biotype` registry

**Raises:**
- `ValueError`: If specifier has no name and module has 0 or 2+ top-level objects
- `KeyError`: If name in specifier doesn't exist in module
- `FileNotFoundError`: If path doesn't exist

### `bio.store(specifier, obj, raw=False)`
Dehydrate and store an object by specifier.

**Args:**
- `specifier`: A specifier string for storage location
- `obj`: Object to store
- `raw`: If True, write obj directly without dehydration

**Behavior:**
1. If `raw=True`, write obj directly to YAML
2. Otherwise, dehydrate object to dict (add `_type` field)
3. Write to `index.yaml` in the DAT path

### `bio.cd(path=None)`
Get or set the current DAT context.

**Args:**
- `path`: DAT path to change to, or None to query current

**Returns:** Current DAT path (after any change)

**Behavior:**
- `bio.cd()` — returns current DAT path
- `bio.cd("catalog/scenarios")` — sets current DAT and returns the new path
- Relative specifiers in `fetch()`, `store()`, etc. resolve against current DAT

### `bio.register_agent(name, agent_class)`
Register an agent implementation.

**Args:**
- `name`: Name for the agent (e.g., "random", "llm", "human")
- `agent_class`: Agent class (must implement Agent protocol)

### `bio.create_agent(name, scenario, **kwargs)`
Create an agent instance for a scenario.

**Args:**
- `name`: Name of registered agent
- `scenario`: Scenario the agent will interact with
- `**kwargs`: Additional arguments passed to agent constructor

**Returns:** Configured Agent instance

### `bio.build(target, seed=None, registry=None, params=None)`
Template instantiation — expand templates into a concrete scenario.

**Args:**
- `target`: Specifier string or already-fetched object
- `seed`: Random seed for reproducibility
- `registry`: Optional template registry for resolving template references
- `params`: Optional parameter overrides

**Returns:** Built scenario with all templates expanded

**Behavior:**
1. If `target` is a string, fetch it first
2. Perform template instantiation (expand `contains:`, `template:` references)
3. Return the fully instantiated scenario

### `bio.create_simulator(chemistry, name="reference", **kwargs)`
Create a Simulator from Chemistry using the registered factory.

**Args:**
- `chemistry`: Chemistry object to simulate
- `name`: Name of registered simulator factory (default: "reference")
- `**kwargs`: Additional arguments passed to simulator factory

**Returns:** Configured Simulator instance

### `bio.run(target, seed=None, registry=None, params=None)`
Execute a runnable and return results.

**Args:**
- `target`: Specifier string or loaded object to execute
- `seed`: Random seed for reproducibility
- `registry`: Optional custom registry overrides
- `params`: Optional parameter overrides

**Returns:** Result tuple `(success: bool, metadata: dict)`

### `bio.report(results, format="table", output=None)`
Generate formatted report from experiment results.

**Args:**
- `results`: List of result dictionaries from `run()` (typically from running an Experiment)
- `format`: Output format — `"table"` (default), `"csv"`, `"excel"`, `"json"`
- `output`: Output path (optional). If None, prints to stdout (table) or temp file (excel)

**Behavior:**

1. Takes the list of result dictionaries from an Experiment run
2. Formats according to the specified format:
   - `table`: ASCII table to stdout with scenario, axis values, and scores
   - `csv`: CSV file with all result fields
   - `excel`: Excel workbook with summary and detail sheets
   - `json`: JSON array of result dictionaries
3. Writes to output path if specified, otherwise uses temp file (for excel) or stdout

**Example:**
```python
bio = Bio()

# Run experiment (returns list of result dicts)
experiment = bio.fetch("catalog/experiments/sweep")
results = bio.run(experiment)

# Generate reports
bio.report(results)                           # table to stdout
bio.report(results, format="csv", output="results.csv")
bio.report(results, format="excel")           # opens in spreadsheet app
```

**Result dict fields used:**
- `scenario`: Scenario name/identifier
- `scores`: Dict of computed scores
- `success`: Boolean pass/fail
- Axis values (e.g., `temperature`, `initial_ME1`)
- Metadata (`seed`, `steps`, etc.)

See [Experiment](../execution/experiment.md) for how results are generated.

## Protocol
```python
class Bio:
    """Environment class for fetching, hydrating, and storing bio objects.

    Instantiate for isolated sandboxes, or use the module-level `bio` singleton.
    """

    def __init__(self, dat: str | DAT | None = None) -> None:
        """Create a new Bio environment.

        Args:
            dat: Optional DAT name (string) or DAT object. If None, anonymous DAT
                 created lazily on first access via bio.dat property.
        """
        ...

    def fetch(self, specifier: str, raw: bool = False) -> Any:
        """Fetch and hydrate object by specifier."""
        ...

    def store(self, specifier: str, obj: Any, raw: bool = False) -> None:
        """Dehydrate and store object by specifier."""
        ...

    def cd(self, path: str | None = None) -> Path:
        """Get/set current DAT context."""
        ...

    def register_agent(self, name: str, agent_class: type) -> None:
        """Register an agent implementation."""
        ...

    def create_agent(self, name: str, scenario: Any, **kwargs) -> Agent:
        """Create agent instance for scenario."""
        ...

    def build(self, target: str | Any, seed: int = None, registry: dict = None, params: dict = None) -> Any:
        """Template instantiation. If target is string, fetches first."""
        ...

    def run(self, target: str | Any, seed: int = None, registry: dict = None, params: dict = None) -> Result:
        """Execute a runnable. If target is string, builds first (which fetches)."""
        ...

    def report(self, results: list[dict], format: str = "table", output: str = None) -> None:
        """Generate formatted report from experiment results."""
        ...

    def create_simulator(self, chemistry: Chemistry, name: str = "reference", **kwargs) -> Simulator:
        """Create Simulator from Chemistry using registered factory."""
        ...

    def hydrate(self, data: dict) -> Any:
        """Convert dict with _type to typed object."""
        ...

    def dehydrate(self, obj: Any) -> dict:
        """Convert typed object to dict with _type."""
        ...

    @property
    def dat(self) -> DAT:
        """Current DAT. Creates anonymous DAT on first access if none specified."""
        ...


# Module-level singleton for CLI and simple scripts
bio: Bio = Bio()
```

## See Also
- [[Bio CLI]] — Command-line interface
- [[Spec Language]] — YAML syntax (`!ev`, `!ref`, `!include`, typed elements)
- [[Scope]] — Scope class for lexical scoping
- [[Decorators]] — `@factory` decorator and type registration
- [[Scenario]] — The main runnable unit
- [[ABIO DAT]] — DAT system integration
