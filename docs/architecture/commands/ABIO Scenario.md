 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Scenario

A Scenario defines an alien biology world — its unique molecules, reactions, containers, and interfaces — that an agent can explore and manipulate. Run with `bio run scenarios.<name>`.

**Contents**
- [[#Spec Format]]
- [[#Interface]]
- [[#Sim]]
- [[#Scoring]]

---

## Spec Format

```yaml
scenarios.mutualism:
  molecules: ...        # defines the molecules in this world
  reactions: ...        # defines how molecules interact
  containers: ...       # hierarchy of containers (regions, vessels)
  interface: ...        # actions, measurements, feedstock available to agent
  initial_state: ...    # starting concentrations of molecules and organisms
  constitution: ...     # normative objectives (natural language)
  briefing: ...         # what the agent knows about the scenario
  scoring: ...          # evaluation functions (see [[#Scoring]])
  passing_score: 0.5    # threshold for success (default: 0.5)
  verify: ...           # assertions on final state
  sim: ...              # simulation config (see [[#Sim]])
```

Scenarios inherit from their parent scope. Use `extends:` to specify explicit inheritance.

**Runtime flow:** Scenario → `Bio.sim(scenario)` → Simulator → State

### Briefing Structure

The `briefing` field is English narrative in markdown format, describing what the agent knows. Recommended sections (all optional):

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
scenario = Bio.build("scenarios.mutualism")   # build in-memory scenario
sim = Bio.sim(scenario)                        # create simulator

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
  simulator: SimpleSimulator    # simulator class (default)
  terminate: !ev "lambda state: state['population'] <= 0"  # early stop
```

(See [[ABIO Sim|sim]] for full details.)

---

## Scoring

Scoring functions evaluate scenario outcomes. Each function receives the simulation trace and returns a numeric value (typically 0.0 to 1.0).

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

### Declaring Scoring Functions

Each scoring function must be registered with the `@scoring` decorator:

```python
from alienbio import scoring

@scoring(range=(0.0, 1.0), description="Combined efficiency and survival")
def aggregate_score(trace: SimulationTrace) -> float:
    # trace.final - final state dict
    # trace.timeline - list of states at each step
    # trace.steps - number of steps run
    efficiency = trace.final['C'] / 10.0
    survival = min(trace.final['A'], trace.final['B']) / 10.0
    return 0.6 * efficiency + 0.4 * survival
```

### Result Structure

When a scenario is run, the return value is a dictionary of scoring results:

```python
result = Bio.run("scenarios.mutualism")
result["scores"]     # {"score": 0.72, "efficiency": 0.85, "stability": 0.92}
result["success"]    # True (if score >= passing_score)
result["final_state"] # {"A": 1.2, "B": 0.8, "C": 8.5}
result["timeline"]   # list of states at each step
```

---

## See Also

- [[ABIO Run|run]] — running scenarios
- [[ABIO Experiment|experiment]] — multi-run experiments
- [[Core Spec]] — YAML tags, scoping, inheritance
- [[Generator Spec]] — template-based scenario generation
