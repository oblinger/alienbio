 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# bio.build()

Build a spec into a DAT folder or an in-memory object.

---

## Synopsis

```bash
bio build <name> [options]
```

```python
result = bio.build("name", seed=42)
```

---

## Options

| Option | Description |
|--------|-------------|
| `--seed N` | Random seed for generation |
| `--output PATH` | Override output path (DAT specs only) |

---

## Call Chain

When given a string, `build()` calls `fetch()` first:

```
build(string) → fetch(string) → template expansion
build(dict)   → template expansion directly
```

This is part of the implicit chaining: `run → build → fetch`.

---

## Build Example

See [[Catalog Naming Scheme]] for the full directory structure and naming conventions.

### ```catalog/mute/org/```         Organism template
```
└── krel.yaml           # Organism definition
```

#### `catalog/mute/org/krel.yaml`
```yaml
org.krel:
  _type: organism
  prefix: K
  metabolism: photosynthesis
  reproduction_rate: !ev "uniform(0.05, 0.15)"
  initial_population: !ev "poisson(20)"
```
An organism template with `!ev` expressions for statistical variation.

### ```catalog/mute/scenario/two_species/```         The source template used to build the runnable DAT folder
```
├── _spec_.yaml         # DAT spec: path template, build rules, run commands
└── index.yaml          # Scenario template referencing org templates
```

#### `catalog/mute/scenario/two_species/_spec_.yaml`
```yaml
dat:
  kind: Dat
  path: data/mute/scenario/two_species_{seed}

build:
  index.yaml: .

run:
  - run . --agent claude
  - report -t tabular
```
Defines where to build, what files to generate, and what commands to run.

#### `catalog/mute/scenario/two_species/index.yaml`
```yaml
scenario.two_species:
  _type: scenario
  organisms:
    producer: !ref mute.org.krel
    consumer: !ref mute.org.kova
  initial_state:
    energy: !ev "uniform(80, 120)"
  scoring:
    passing_score: 0.5
```
Scenario referencing organism templates from the `mute` universe. During build, `!ref` and `!ev` get expanded.

### Build Command
```
% bio build mute.scenario.two_species --seed 42
```

### ```data/mute/scenario/two_species_42/```    Generated runnable DAT folder
```
├── _spec_.yaml         # Spec with build parameters recorded
├── index.yaml          # Instantiated scenario (concrete values)
└── _result_.yaml       # Created by run, not build
```

#### `data/mute/scenario/two_species_42/_spec_.yaml`
```yaml
dat:
  kind: Dat
  path: data/mute/scenario/two_species_{seed}
build:
  index.yaml: .
run:
  - run . --agent claude
  - report -t tabular
_built_with:
  seed: 42
  timestamp: 2026-01-15T16:45:23
```
Source spec plus build parameters (`seed`, `timestamp`) recorded for reproducibility.

#### `data/mute/scenario/two_species_42/index.yaml`
```yaml
scenario.two_species:
  _type: scenario
  organisms:
    producer:
      _type: organism
      prefix: K
      metabolism: photosynthesis
      reproduction_rate: 0.12
      initial_population: 23
    consumer:
      _type: organism
      prefix: V
      metabolism: heterotroph
      reproduction_rate: 0.08
      initial_population: 18
  initial_state:
    energy: 97.3
  scoring:
    passing_score: 0.5
```
All `!ev` expressions evaluated with seed=42. `!ref` expanded inline. Ready to run.

#### `data/mute/scenario/two_species_42/_result_.yaml`
Not created by `build` — only created after `run` executes.

---

## What Gets Built

The behavior depends on what the dotted name refers to:

### DAT Spec → DAT Folder

If the name refers to a DAT spec (has `path:` and `build:` fields):

1. Creates the folder using the `path:` template (variables like `{seed}` are substituted)
2. Copies the spec to `_spec_.yaml` in the new folder
3. For each entry in `build:`:
   - The key is the output filename (e.g., `index.yaml`)
   - The value is a Bio generator name (e.g., `generators.baseline`)
   - Calls `bio.build()` on the generator to produce content
   - Writes the generated content to the output file
4. Returns the path to the created DAT folder

```bash
bio build scenarios.baseline --seed 42
# → Created: data/scenarios/baseline_42/
```

**Example `build:` section:**
```yaml
scenarios.baseline:
  path: data/scenarios/baseline_{seed}/
  build:
    index.yaml: generators.baseline    # generates scenario content
    config.yaml: generators.config     # generates config (optional)
```

Each generator is a Bio spec that produces content when built. The generator has access to the seed and other parameters.

### Biological Object → In-Memory Structure

If the name refers to a biological object (scenario, generator, etc.):

1. Performs template expansion
2. Returns an in-memory dictionary structure

```python
scenario = bio.build("scenarios.mutualism")   # in-memory dict
sim = bio.sim(scenario)                        # run simulator on it
```

This is how scenarios get built for direct simulation without creating a DAT folder.

---

## Examples

```bash
# Build a scenario with seed
bio build scenarios.baseline --seed 42
# → Created: data/scenarios/baseline_42/

# Build an experiment (creates folder structure, no execution)
bio build experiments.mutualism
# → Created: data/experiments/mutualism_2026-01-10_001/

# Build with custom output path
bio build scenarios.baseline --seed 42 --output ./my_test/
# → Created: ./my_test/
```

---

## Comparison with Run

| Command | Build | Execute |
|---------|-------|---------|
| `bio build scenarios.baseline` | Yes | No |
| `bio run scenarios.baseline` | Yes | Yes |
| `bio run data/scenarios/baseline_42/` | No | Yes |

Use `build` when you want to inspect or modify the generated content before running.

---

## See Also

- [[ABIO Run|run]] — build and run in one step
- [[Execution Guide#New Execution Model]] — execution model overview
- [[Catalog Naming Scheme]] — directory structure and naming conventions for templates
