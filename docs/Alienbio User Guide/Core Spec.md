 [[ABIO docs]] → [[Alienbio User Guide]]

# Core Spec

YAML foundations: tags, scoping, inheritance, and evaluation.

**Contents**
- [[#Typed Named Elements]]
- [[#Processing Flow]]
- [[#YAML Tags]]
- [[#Reusable Values]]
- [[#Scope and Inheritance]]
- [[#Variables]]
- [[#File Structure]]

---

## Typed Named Elements

Use `type.name:` syntax to declare typed objects:

```yaml
world.my_world:                    # type=world, name=my_world
  molecules: ...
  reactions: ...
  containers: ...

scenario.mutualism.test1:          # type=scenario, name=mutualism.test1
  extends: my_world
  interface: ...

scope.my_tests:                    # type=scope, name=my_tests
  extends: mutualism.test1
  scenario.baseline:               # type=scenario, name=baseline
    briefing: "Standard conditions"
  scenario.stressed:               # type=scenario, name=stressed
    briefing: "Resource scarcity"
```

**Parsing rules:**
- First segment before `.` is looked up in type registry
- If registered type: `scenario.foo.bar` → creates typed object with name=`foo.bar`
- If not a type: `config.timeout` → nested dict `{"config": {"timeout": ...}}`

**Built-in types:**

| Type | Purpose |
|------|---------|
| `world` | Physical substrate (molecules, reactions, containers) |
| `scenario` | Runnable unit with all simulation and evaluation fields |
| `scope` | Container for grouping scenarios with shared inheritance |

Custom types registered via `@biotype` decorator. See [[Decorators]].

---

## Processing Flow

Specs go through stages before execution: <span style="white-space: nowrap">name → <b>.fetch()</b> → dict → <b>.hydrate()</b> → entity → <b>.build()</b> → expanded → <b>.eval()</b> → result</span>

1. **Fetch**: Load YAML from source tree (returns raw dict)
2. **Hydrate**: Resolve `!ref` and `!include` placeholders, build scope tree, instantiate types
3. **Build**: Template expansion
4. **Eval**: Execute `!ev` expressions in scope context

See [[Spec Language Reference]] for complete pipeline and hydration phases.

---

## YAML Tags

| Tag | When Resolved | Description |
|-----|---------------|-------------|
| `!ref` | Hydration | Copy referenced structure into place |
| `!include` | Hydration | Include external file content |
| `!ev` | Eval | Evaluate Python expression |
| `!_` | Later | Preserve for contextual evaluation (rates, scoring) |

**Examples:**
```yaml
high_permeability: 0.8
standard_interface:
  actions: [add_feedstock, adjust_temp]

scenario.example:
  permeability: !ref high_permeability       # copies 0.8 here
  interface: !ref standard_interface         # copies structure here
  count: !ev normal(50, 10)                  # evaluated at eval time
  rate: !_ k * S / (Km + S)                  # preserved for simulation
  constitution: !include safety.md           # file content embedded
```

**Key points:**
- `!ref`, `!include` are resolved early (during hydration) — structure is copied
- `!ev` creates a placeholder, executed at eval time
- `!_` preserves the expression string for later contextual evaluation

---

## Reusable Values

Define reusable values at the top level of a spec:

```yaml
permeability.high: 0.8                         # dotted names group related values
permeability.low: 0.1
environment.standard:
  temp: 25
  pH: 7.0

scenario.example:
  containers:
    membrane:
      permeability: !ref permeability.high     # substitutes 0.8
      environment: !ref environment.standard   # substitutes entire dict
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

See [[modules/Scope|Scope]] for details on lexical scoping.

---

## Variables

All processing uses a nested lexical scope for variable resolution. Variables are looked up from innermost to outermost scope until found.

### Implicit Scope Hierarchy

```
cli             # Command-line --name value pairs (highest priority)
  └── config        # User configuration (~/.config/alienbio/config.yaml)
        └── experiment  # Experiment-level variables
              └── scenario  # Scenario-level variables
                    └── simulator  # Runtime variables during execution
```

Inner scopes override outer scopes. CLI always wins.

### Predefined Variables

These variables are defined at the config scope with default values:

| Variable | Default | Description |
|----------|---------|-------------|
| `agent` | `random` | Agent to use for experiments |
| `seed` | `null` | Random seed (null = generate) |
| `verbosity` | `1` | Output verbosity level |

### Setting Variables

**Via CLI** (outermost — sets background context):
```bash
bio run scenario --agent claude-opus      # set default agent for this run
bio run scenario --seed 42                # set seed
bio run scenario --my_custom_var foo      # any variable
```

**In config file** (`~/.config/alienbio/config.yaml`):
```yaml
variables:
  agent: claude-opus
  seed: 42
```

**In experiment spec:**
```yaml
experiment.my_battery:
  agent: gpt-4           # overrides CLI/config
  scenarios: [example]   # references scenario below

scenario.example:
  agent: oracle          # overrides experiment's gpt-4
  ...
```

Inner scopes override outer scopes. A scenario setting overrides an experiment setting, which overrides config, which overrides CLI defaults. First match wins; missing variable with no default raises an error.

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

See [[modules/Scope|Scope]] for the module pattern and inheritance chains.

---

## See Also

- [[commands/ABIO Scenario|Scenario]] — Scenarios, interface, scoring
- [[Generator Spec]] — Template-based scenario generation
- [[Execution Guide]] — CLI, agents, running experiments
- [[Spec Language Reference]] — Complete language specification (architecture)
