# Spec Language
**Parent**: [[ABIO Topics]]

YAML syntax extensions for writing spec files.

---

## Typed Named Elements

Use `type.name:` syntax to declare typed objects:

```yaml
world.mutualism_ecosystem:
  molecules: ...
  reactions: ...

suite.mutualism:
  defaults:
    world: !ref mutualism_ecosystem
  scenario.baseline:
    framing: "Standard conditions"
  scenario.stressed:
    framing: "Resource scarcity"
```

**Parsing rules:**
- First segment before `.` is looked up in type registry
- If registered type: `suite.foo.bar` → type=`suite`, name=`foo.bar`
- If not a type: treated as regular dotted key

**Internal representation:**
```python
# world.mutualism_ecosystem: {...}
# becomes:
{"mutualism_ecosystem": {"_type": "world", ...}}
```

**Built-in types:**

| Type | Hydrates To | Purpose |
|------|-------------|---------|
| `scenario` | `Scenario` | Runnable unit (chemistry, containers, interface, briefing, constitution, scoring) |
| `suite` | `Suite` | Container for scenarios or nested suites |
| `chemistry` | `Chemistry` | Molecules and reactions |

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
constants:
  high_permeability: 0.8
  standard_diffusion: {default: 0.1, membrane: 0.01}

molecules: !ev energy_ring(size=6)         # evaluate → list of molecules
rate: !ev mass_action(k=0.1)               # evaluate → rate function
rate: !ev lambda c: c["ME1"] * 0.1         # evaluate → rate function (inline)
outflows: !ref standard_diffusion          # reference constant
constitution: !include safety.md           # include file content
```

**Notes:**
- `!ev` evaluates once at load/expansion time; result is used directly
- For rate functions, the expression must produce a callable
- No special `$` or `=` prefix syntax—everything uses YAML tags

---

## Constants

Define reusable values at the top of a spec:

```yaml
constants:
  high_permeability: 0.8
  low_permeability: 0.1
  standard_environment:
    temp: 25
    pH: 7.0

world.example:
  containers:
    membrane:
      permeability: !ref high_permeability     # substitutes 0.8
      environment: !ref standard_environment   # substitutes entire dict
```

Constants are substituted during expansion, before hydration.

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
      framing: "Urgent situation"          # adds to inherited

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
spec.mutualism:
  include:
    - functions.py                         # load Python decorators
    - chemistry.yaml                       # load additional YAML

  constants:
    high_permeability: 0.8

  world.mutualism_ecosystem:
    molecules: ...
    reactions: ...
    containers: ...
    feedstock: {ME1: 10.0}
    actions: [add_feedstock, adjust_temp]
    measurements: [sample_substrate, population_count]

  suite.mutualism:
    defaults:
      world: !ref mutualism_ecosystem
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
| `chemistry` | Molecules and reactions |
| `containers` | Hierarchy of ecosystems, regions, organisms |
| `interface` | Actions, measurements, feedstock available to agent |
| `constitution` | Normative objectives (natural language) |
| `briefing` | Agent's knowledge about the scenario |
| `framing` | Situational context |
| `scoring` | Evaluation metrics (optional) |

Scenarios can extend other scenarios via prototype inheritance (deep merge through `defaults:`).

**Runtime flow:** Scenario → `Bio.sim(scenario)` → WorldSimulator → WorldState

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

The `alienbio.run` function is a standard runner for bio DATs. By default it looks for `index.yaml` in the DAT folder and executes the scenario or suite found there.

### Convention: `index.yaml`

```yaml
# index.yaml - bio data for alienbio.run
scenario.hardcoded_test:
  chemistry:
    molecules:
      A: {name: "Molecule A", bdepth: 0}
      B: {name: "Molecule B", bdepth: 0}
    reactions:
      combine:
        reactants: [A, B]
        products: [C]
        rate: !ev "lambda state: 0.1 * state['A'] * state['B']"

  initial_state:
    A: 10.0
    B: 10.0

  run:
    steps: 100

  verify:
    - assert: "state['C'] > 5.0"
      message: "C should accumulate"

  scoring:
    efficiency: !ev "lambda state: state['C'] / 10.0"
```

### Scenario Fields

| Field | Description |
|-------|-------------|
| `chemistry` | Molecules and reactions |
| `initial_state` | Starting concentrations |
| `run` | Execution parameters (steps, until_quiet) |
| `verify` | Assertions on final state (Python expressions) |
| `scoring` | Scoring functions to evaluate |

### Result Structure

The runner returns `(success, result)` where result contains:

- **Scenario** → `{final_state, timeline, scores, verify_results, success}`
- **Suite** → `{scenario_name: scenario_result, ...}`

---

## See Also

- [[Bio]] — Loading and hydration (`Bio.fetch()`, `Bio.store()`)
- [[Scenario]] — The main runnable unit
- [[WorldSimulator]] — Execution engine
- [[Decorators]] — `@biotype` for custom types, `@scoring`/`@action`/`@measurement` for functions
- [[DAT]] — Data artifact system (for job storage and resolution)
