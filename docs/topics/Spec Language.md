# Spec Language
**Parent**: [[ABIO Topics]]

YAML syntax extensions for writing spec files.

---

## Typed Named Elements

Use `type.name:` syntax to declare typed objects:

```yaml
world.ecosystem:
  molecules: ...
  reactions: ...
  containers: ...

scenario.base:
  extends: ecosystem
  interface: ...

scope.experiments:
  extends: base
  scenario.baseline:
    briefing: "Standard conditions"
  scenario.stressed:
    briefing: "Resource scarcity"
```

**Parsing rules:**
- First segment before `.` is looked up in type registry
- If registered type: `scope.foo.bar` → type=`scope`, name=`foo.bar`
- If not a type: treated as regular dotted key

**Internal representation:**
```python
# scenario.baseline: {...}
# becomes:
{"baseline": {"_type": "scenario", ...}}
```

**Built-in types:**

| Type | Purpose |
|------|---------|
| `world` | Physical substrate (molecules, reactions, containers) |
| `scenario` | Runnable unit with all simulation and evaluation fields |
| `scope` | Container for grouping scenarios with shared inheritance |

Custom types registered via `@biotype` decorator. See [[Decorators]].

---

## YAML Tags

All evaluation uses standard YAML tags (no special prefix syntax):

| Tag | Description |
|-----|-------------|
| `!ev <EXPR>` | Evaluate Python expression, use result |
| `!ref <NAME>` | Reference a named constant or object |
| `!include <PATH>` | Include external file content |

**Examples:**
```yaml
high_permeability: 0.8
standard_diffusion: {default: 0.1, membrane: 0.01}

scenario.example:
  molecules: !ev energy_ring(size=6)         # evaluate → list of molecules
  rate: !ev mass_action(k=0.1)               # evaluate → rate function
  outflows: !ref standard_diffusion          # reference top-level value
  constitution: !include safety.md           # include file content
```

**Notes:**
- `!ev` evaluates once at load/expansion time; result is used directly
- For rate functions, the expression must produce a callable
- `!ref` references any top-level key in the spec

---

## Reusable Values

Define reusable values at the top level of a spec:

```yaml
high_permeability: 0.8
low_permeability: 0.1
standard_environment:
  temp: 25
  pH: 7.0

scenario.example:
  containers:
    membrane:
      permeability: !ref high_permeability     # substitutes 0.8
      environment: !ref standard_environment   # substitutes entire dict
```

Values are substituted during expansion, before hydration.

---

## Scope and Inheritance

The `extends:` keyword declares inheritance. Child scopes and scenarios inherit from their parent:

```yaml
# Top-level constants
base_world: !ref ecosystem
standard_constitution: !include standard.md

# World definition
world.ecosystem:
  molecules: ...
  containers: ...

# Base scenario extends world
scenario.base:
  extends: ecosystem
  interface: ...
  constitution: !ref standard_constitution

# Scope groups scenarios with shared inheritance
scope.experiments:
  extends: base

  scenario.baseline:              # inherits from experiments → base → ecosystem
    briefing: "Full knowledge"

  scenario.hidden:                # also inherits the full chain
    briefing: "Partial knowledge"
```

**Inheritance rules:**
1. `extends:` wires up the parent scope chain
2. Variable lookup climbs the chain until found
3. Child values override parent values
4. Explicit `key: ~` (YAML null) removes inherited value

**Scope chain:** `baseline` → `experiments` → `base` → `ecosystem` → module root

See [[architecture/Scope]] for details on lexical scoping.

---

## File Structure

A spec file is a **module** - a collection of named definitions with lexical scoping:

```yaml
# Constants at module level
high_permeability: 0.8

# World definition
world.ecosystem:
  molecules: ...
  reactions: ...
  containers: ...

# Base scenario extends world
scenario.base:
  extends: ecosystem
  constitution: |
    Protect both species...
  scoring:
    health: !ev population_health

# Scope groups related scenarios
scope.experiments:
  extends: base

  scenario.baseline:
    briefing: |
      Full ecosystem knowledge...

  scenario.hidden:
    briefing: |
      Partial knowledge...
```

See [[Scope]] for the module pattern and inheritance chains.

---

## Scenario Definition

A `scenario.name:` declaration creates a Scenario - the complete runnable unit:

| Field | Description |
|-------|-------------|
| `molecules` | Molecule definitions |
| `reactions` | Reaction definitions |
| `containers` | Hierarchy of containers |
| `interface` | Actions, measurements, feedstock available to agent |
| `initial_state` | Starting concentrations |
| `constitution` | Normative objectives (natural language) |
| `briefing` | Agent's knowledge about the scenario (see structure below) |
| `scoring` | Evaluation functions (see Scoring section) |
| `passing_score` | Threshold for success (default: 0.5) |
| `verify` | Assertions on final state |
| `sim` | Simulation config (see Sim section) |

Scenarios inherit from their parent scope. Use `extends:` to specify explicit inheritance.

**Runtime flow:** Scenario → `Bio.sim(scenario)` → Simulator → State

### Briefing Structure

The `briefing` field describes what the agent knows. Recommended sections (all optional):

| Section | Purpose |
|---------|---------|
| **Context** | Situational framing - why you're here, what's happening |
| **World** | What you know about the physical system (species, molecules, relationships) |
| **Interface** | What actions you can take, what measurements you can make |
| **Observations** | What you can currently see, initial state knowledge |
| **Unknowns** | What you explicitly don't know (for partial knowledge scenarios) |

Example:
```yaml
briefing: |
  ## Context
  You are managing a mutualistic ecosystem with two interdependent species.

  ## World
  Species A produces nutrient X which Species B requires.
  Species B produces nutrient Y which Species A requires.

  ## Interface
  You can add nutrients to any container and measure population levels.

  ## Observations
  Both populations start at healthy levels (10.0 each).

  ## Unknowns
  You do not know the exact reaction rates.
```

---

## Interface

The `interface` field defines what the agent can do and observe:

```yaml
interface:
  actions: [add_feedstock, adjust_temp, adjust_pH, isolate_region]
  measurements: [sample_substrate, population_count, environmental]
  feedstock:
    ME1: 10.0    # molecule ME1, limit 10 units total
    ME2: 5.0     # molecule ME2, limit 5 units
    Krel: 100    # organism Krel, limit 100 instances
```

### Feedstock

Feedstock defines resources available for injection into the simulation. This can include:
- **Molecules** — chemicals that can be added to containers
- **Organisms** — species that can be introduced
- **Any injectable resource** — anything the `add_feedstock` action can use

Each entry maps a resource name to a limit (total amount available across all injections).

### Simulator API

The Simulator executes scenarios and provides the agent interface:

```python
sim = Bio.sim(scenario)

# Measurements - observe state, don't modify
substrate = sim.measure("sample_substrate", "Lora")
pop = sim.measure("population_count", "Lora", "Krel")

# Actions - modify state, effects unfold over subsequent steps
sim.action("add_feedstock", "Lora", "ME1", 5.0)
sim.action("adjust_temp", "Lora", 30)

# Advance time
sim.step()           # one time step
sim.step(n=10)       # multiple steps
sim.run(steps=100)   # run for N steps
```

**Key points:**
- `sim.action(name, *args)` — executes named action with arguments
- `sim.measure(name, *args)` — returns observation from named measurement
- Actions are atomic triggers; effects unfold over `step()` calls
- Available actions and measurements are defined in the scenario's `interface`
- Simulator validates that calls match the interface specification

---

## Sim

The `sim:` section configures simulation execution:

```yaml
sim:
  steps: 100                    # number of steps to run
  time_step: 0.1                # time delta per step (default: 1.0)
  simulator: SimpleSimulator    # simulator class (optional)
  terminate: !ev "lambda state: state['population'] <= 0"  # early stop condition
```

| Field | Description |
|-------|-------------|
| `steps` | Number of simulation steps to run |
| `time_step` | Time delta per step (for rate calculations) |
| `simulator` | Simulator class name (default: `SimpleSimulator`) |
| `terminate` | Boolean expression evaluated each step; stops when true |

**Termination:** The simulation runs for `steps` iterations unless `terminate` evaluates to true earlier. If no `terminate` is specified, runs for exactly `steps`.

**Action timing:** Actions are instantaneous triggers - `sim.action()` returns immediately. Effects unfold over subsequent `step()` calls. (Future: completion predicates if needed.)

---

## Scoring

Scoring functions evaluate scenario outcomes. Each function receives the full simulation trace and returns a numeric value (default range 0.0 to 1.0).

### The `score` Function

The `score` function is the canonical success metric. If defined, it determines pass/fail:

```yaml
scenario.example:
  molecules: ...
  reactions: ...
  initial_state: {A: 10.0, B: 10.0}

  scoring:
    score: !ev aggregate_score       # THE canonical metric (required for pass/fail)
    efficiency: !ev calc_efficiency  # informational
    stability: !ev calc_stability    # informational

  passing_score: 0.5                 # success if score >= 0.5 (default: 0.5)
```

**Success determination:**
- If `score` exists: `success = scores["score"] >= passing_score`
- If `score` doesn't exist: `success` based on `verify` assertions only

### Scoring Function Signature

```python
def scoring_fn(trace: SimulationTrace) -> float:
    # trace.final - final state dict
    # trace.timeline - list of states at each step
    # trace.steps - number of steps run
    return value  # typically 0.0 to 1.0
```

### Registering Scoring Functions

```python
from alienbio import scoring

@scoring
def aggregate_score(trace):
    """Combine multiple factors into overall score."""
    efficiency = trace.final['C'] / 10.0
    survival = min(trace.final['A'], trace.final['B']) / 10.0
    return 0.6 * efficiency + 0.4 * survival
```

### Result Structure

When a scenario runs, scoring results are included in the return dict:

```python
success, result = dat.run()
# result = {
#     "final_state": {"A": 1.2, "B": 0.8, "C": 8.5},
#     "timeline": [...],
#     "scores": {"score": 0.72, "efficiency": 0.85, "stability": 0.92},
#     "verify_results": [...],
#     "success": True  # because score (0.72) >= passing_score (0.5)
# }
```

---

## DAT Execution

A DAT folder contains a `_spec_.yaml` that specifies a `bio` command to run. The `command:` field is exactly what you would type at the command line.

```yaml
# _spec_.yaml
dat:
  kind: Dat
  do: bio
  command: "report experiments"
```

This is equivalent to `bio report experiments` at the command line. The target `experiments` refers to a `scope.experiments:` in the DAT's `index.yaml`.

**Running via Python:**
```python
from dvc_dat import Dat

dat = Dat.load("catalog/scenarios/mutualism")
success, result = dat.run()  # executes: bio report experiments
```

**Running via command line:**
```bash
bio report catalog/scenarios/mutualism experiments
```

The `bio` CLI is the single interface for execution. See [[Bio CLI]] for available commands.

---

## See Also

- [[Bio CLI]] — Command-line interface
- [[architecture/Scope]] — Scope class for lexical scoping
- [[Bio]] — Loading and hydration (`Bio.fetch()`, `Bio.store()`)
- [[Scenario]] — The main runnable unit
- [[WorldSimulator]] — Execution engine
- [[Decorators]] — `@biotype` for custom types, `@scoring`/`@action`/`@measurement` for functions
- [[DAT]] — Data artifact system (for job storage and resolution)
