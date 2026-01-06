# Spec Language
**Parent**: [[ABIO Topics]]

YAML syntax extensions for writing spec files.

---

## Typed Named Elements

Use `type.name:` syntax to declare typed objects:

```yaml
suite.mutualism:
  defaults:
    molecules: ...
    reactions: ...
  scenario.baseline:
    briefing: "Standard conditions"
  scenario.stressed:
    briefing: "Resource scarcity"
```

**Parsing rules:**
- First segment before `.` is looked up in type registry
- If registered type: `suite.foo.bar` → type=`suite`, name=`foo.bar`
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
| `scenario` | Runnable unit with all simulation and evaluation fields |
| `suite` | Container for scenarios or nested suites |

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

## Defaults and Inheritance

Suites define `defaults:` that cascade to children:

```yaml
suite.experiments:
  defaults:
    world: !ref base_world
    constitution: !include standard.md

  suite.high_knowledge:
    defaults:
      briefing: !ev full_briefing()        # adds to parent defaults

    scenario.baseline: {}                   # inherits all defaults
    scenario.time_pressure:
      briefing: "Urgent situation"         # adds to inherited

  suite.low_knowledge:
    defaults:
      briefing: !ev minimal_briefing()     # different briefing branch

    scenario.baseline: {}
```

**Merge rules:**
1. Child `defaults:` deep-merges with parent `defaults:`
2. Scenario content deep-merges with accumulated defaults
3. Scalars replace (no append)
4. Explicit `key: ~` (YAML null) removes inherited value

---

## File Structure

A typical spec file:

```yaml
high_permeability: 0.8

suite.mutualism:
  defaults:
    molecules: ...
    reactions: ...
    containers: ...
    constitution: |
      Protect both species...
    scoring:
      health: !ev population_health

  scenario.baseline:
    briefing: |
      Full ecosystem knowledge...

  scenario.hidden:
    briefing: |
      Partial knowledge...
```

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
| `run` | Execution config (steps, etc.) |

Scenarios can extend other scenarios via `extends:` or through suite `defaults:`.

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

## Jobs

A Job is simply a DAT with a `do:` function that executes bio simulations. See [[ABIO DAT]] for the DAT format.

```yaml
# _spec_.yaml
dat:
  kind: Dat
  do: alienbio.run
```

```python
from dvc_dat import Dat

dat = Dat.load("catalog/jobs/hardcoded_test")
success, result = dat.run()
```

---

## Standard Runner: `alienbio.run`

The `alienbio.run` function is a standard runner for bio DATs. By default it looks for `index.yaml` in the DAT folder and runs what it finds there (scenario, suite, or report).

Returns `(success, result)` as expected by DAT. See [[Scenario]] for scenario fields and structure.

---

## See Also

- [[Bio]] — Loading and hydration (`Bio.fetch()`, `Bio.store()`)
- [[Scenario]] — The main runnable unit
- [[WorldSimulator]] — Execution engine
- [[Decorators]] — `@biotype` for custom types, `@scoring`/`@action`/`@measurement` for functions
- [[DAT]] — Data artifact system (for job storage and resolution)
