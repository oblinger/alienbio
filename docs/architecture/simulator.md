# Simulator
**Subsystem**: [[ABIO execution]] > Simulation
Execution engine for biology dynamics.

## Overview

Simulator is the protocol for execution engines that advance biological state through time. The primary implementation uses **JAX for GPU acceleration**. For multi-compartment simulations, use WorldSimulator.

| Property | Type | Description |
|----------|------|-------------|
| `chemistry` | Chemistry | The chemistry being simulated |
| `dt` | float | Time step size |

| Method | Returns | Description |
|--------|---------|-------------|
| `step(state)` | State | Advance state by one timestep |
| `run(state, steps)` | List[State] | Run simulation for multiple steps |

---

## Implementation Strategy: JAX

### Why JAX?

| Backend | Parallelism | Overhead | Use Case |
|---------|-------------|----------|----------|
| **JAX on GPU** | Thousands of cores | Compile once at sim creation | Large simulations (primary) |
| Python/NumPy | Vectorized | Per-step interpreter | Debugging, small systems |
| Rust | SIMD (8-16 lanes) | None | Future option if needed |

For large-scale simulation (millions of compartments, thousands of reactions):
- **JAX on GPU is the fastest option** — massive parallelism, no per-step Python overhead
- Rust might win for small simulations or CPU-only environments
- Pure Python/NumPy is sufficient for debugging and development

### Generated Python Module Approach

At simulator creation time (`Bio.sim(scenario)`), we generate a Python module containing all rate functions:

```python
# Generated module (created at Bio.sim() time)
import jax.numpy as jnp

# Constants (baked in from spec scope)
Vmax = 10.0
Km = 5.0
k1 = 0.1
k2 = 0.05

# Rate functions (one per reaction)
def rate_glycolysis(S1, S2):
    """Glucose + ATP → G6P + ADP"""
    return k1 * S1 * S2

def rate_michaelis(S):
    """Michaelis-Menten kinetics"""
    return Vmax * S / (Km + S)

def rate_synthesis(S1, S2):
    """Product synthesis"""
    return k2 * S1 * S2

# ... one function per reaction in the scenario
```

**Flow:**
```
Scenario (with rate expression strings)
    ↓ Bio.sim()
Generate Python module string
    ↓ exec() or write to temp file
Python module with rate functions
    ↓ JAX traces all functions
XLA-compiled GPU kernels
    ↓ sim.step() / sim.run()
Efficient GPU execution
```

**Benefits:**
1. **No per-step Python overhead** — JAX compiles everything at sim creation
2. **Human-readable** — Generated module can be inspected for debugging
3. **Constants baked in** — No runtime lookup, optimal performance
4. **Full Python expressiveness** — Rate expressions can use any Python syntax

---

## Rate Expression Compilation

### The Problem

Rate expressions like `k * S1 * S2` or `Vmax * S / (Km + S)` contain:
- **Constants**: `Vmax`, `Km`, `k` — known from the spec
- **Runtime variables**: `S`, `S1`, `S2` — substrate concentrations, change each step

### Compilation Process

```python
# At Bio.sim() time:
def compile_scenario(scenario: Scenario) -> CompiledSimulator:
    """Generate Python module and compile with JAX."""

    # Collect all rate expressions
    rate_functions = []
    for reaction in scenario.reactions:
        rate_source = reaction.rate  # e.g., "Vmax * S / (Km + S)"

        # Identify constants vs runtime variables
        constants = resolve_constants(rate_source, scenario.scope)
        runtime_vars = identify_substrates(rate_source, reaction)

        # Generate function with constants baked in
        rate_functions.append(generate_rate_function(
            name=f"rate_{reaction.name}",
            source=rate_source,
            constants=constants,
            params=runtime_vars
        ))

    # Generate complete module
    module_source = generate_module(
        constants=scenario.scope,
        rate_functions=rate_functions
    )

    # Execute module and let JAX trace it
    module = exec_module(module_source)
    return JAXSimulator(module, scenario)
```

### Substrate Variable Conventions

The simulator provides standard variable names for rate expressions:

| Variable | Meaning |
|----------|---------|
| `S` | First substrate concentration |
| `S1`, `S2`, ... | Substrates by position |
| `P` | First product concentration |
| `P1`, `P2`, ... | Products by position |

Example:
```yaml
reaction.glycolysis:
  substrates: [Glucose, ATP]
  products: [G6P, ADP]
  rate: !quote k * S1 * S2  # k * [Glucose] * [ATP]
```

---

## Usage Example

```python
from alienbio import Bio

# Load scenario
scenario = Bio.load("ecosystem.yaml", "experiments.baseline")

# Create simulator (generates Python module, JAX compiles)
sim = Bio.sim(scenario)

# Initial state
state = sim.initial_state()

# Run simulation
history = sim.run(state, steps=1000)

# Or step-by-step with actions
for _ in range(100):
    state = sim.step(state)
    if state['population_A'] < 1.0:
        sim.action("add_feedstock", "container_1", "nutrient", 5.0)
```

---

## Relationship to WorldSimulator

- **Simulator**: Single-compartment, uses Chemistry
- **WorldSimulator**: Multi-compartment, uses CompartmentTree + Flows

Both use the same JAX compilation approach for rate expressions.

---

## Protocol

```python
from typing import Protocol, List

class Simulator(Protocol):
    """Execution engine protocol."""

    @property
    def chemistry(self) -> Chemistry:
        """The Chemistry being simulated."""
        ...

    @property
    def dt(self) -> float:
        """Time step size."""
        ...

    def step(self, state: State) -> State:
        """Advance state by one timestep."""
        ...

    def run(self, state: State, steps: int) -> List[State]:
        """Run simulation for specified steps."""
        ...

    def action(self, name: str, *args) -> None:
        """Execute named action (effects unfold over subsequent steps)."""
        ...

    def measure(self, name: str, *args) -> float:
        """Take named measurement from current state."""
        ...
```

---

## Design Decisions

### Why JAX over Rust?

1. **GPU parallelism**: Millions of compartments map perfectly to GPU cores
2. **No Python↔Rust boundary overhead**: Everything stays in Python/JAX
3. **Same language**: Macros, functions, and rate expressions all in Python
4. **Debugging**: Generated modules are inspectable Python code

### Why Generated Module over eval()?

1. **JAX tracing**: JAX can trace real Python functions, not eval'd bytecode
2. **Inspectable**: Humans can read the generated code
3. **Cacheable**: Module can be saved and reused

### When Rust Might Be Better

- Small simulations where GPU overhead dominates
- CPU-only environments
- Complex control flow (GPUs dislike branching)

If Rust is needed later, we can:
1. Parse Python expression strings
2. Derive Expr trees as internal IR
3. Send to Rust via PyO3
4. Interpret with SIMD

See [[Expr]] for the deferred structured format.

---

## Relationship to Spec Evaluation

Rate expressions use `!quote` to preserve them through evaluation:

```yaml
reaction.example:
  rate: !quote Vmax * S / (Km + S)   # Preserved as string
```

```
Spec Processing (see [[Spec Evaluation]]):
  YAML →.hydrate→ Quoted(source="Vmax * S / (Km + S)")
       →.macro_expand→ Quoted node preserved
       →.eval→ Scenario with rate string "Vmax * S / (Km + S)"

Simulator Creation (Bio.sim):
  Scenario → generate Python module → JAX compile → GPU kernels

Runtime (sim.step):
  GPU kernels execute rate calculations in parallel
```

---

## See Also

- [[Spec Evaluation]] - How rate expressions are preserved through evaluation
- [[WorldSimulator]] - Multi-compartment simulator
- [[State]] - What gets simulated
- [[Chemistry]] - Molecules and reactions
- [[Expr]] - Deferred structured expression format (for future Rust backend)
- [[ABIO execution]] - Parent subsystem
