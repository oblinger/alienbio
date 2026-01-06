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

scenario.example:
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
constants:
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
| `briefing` | Agent's knowledge about the scenario |
| `framing` | Situational context |
| `scoring` | Evaluation functions |
| `verify` | Assertions on final state |
| `run` | Execution config (steps, etc.) |

Scenarios can extend other scenarios via prototype inheritance (deep merge through `defaults:`).

**Runtime flow:** Scenario → `Bio.sim(scenario)` → Simulator → State

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
