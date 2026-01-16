 [[Architecture Docs]] → [[ABIO infra]]

# DAT

Data folder system for storing and loading biological specifications. Bio uses DAT for filesystem-based storage and retrieval of YAML specs.

## Bio DAT File Structure

A Bio DAT folder has a defined structure:

```
my_experiment/
├── _spec_.yaml         # Required: DAT specification (kind, do function)
├── _result_.yaml       # Generated: execution results from dat.run()
├── index.yaml          # Bio content: scenario, chemistry, etc.
│                       #   Default object returned by bio.fetch(dat_name)
├── timeline.yaml       # Generated: full simulation timeline (optional)
└── [other files...]       # Optional: additional data, logs, artifacts
```

### `_spec_.yaml` (Required)

The dvc_dat specification file. Defines DAT metadata and execution behavior.

**Minimal example:**
```yaml
# _spec_.yaml
dat:
  kind: Dat
  do: alienbio.run      # Function called when DAT is run
```

**Full example with base template and args:**
```yaml
# _spec_.yaml
dat:
  kind: Dat
  base: experiments.baseline        # Expand from this base template
  path: experiments/{YYYY}{MM}{DD}  # Path template with variables
  do: alienbio.run                  # Function to execute
  args: [10]                        # Positional args for do function
  kwargs:                           # Keyword args for do function
    verbose: true
    seed: 42
```

**Key fields:**
| Field | Description |
|-------|-------------|
| `dat.kind` | DAT class (usually "Dat") |
| `dat.do` | Function called when DAT is run (receives DAT as first arg) |
| `dat.base` | Base template to expand from (optional) |
| `dat.path` | Path template with `{YYYY}`, `{unique}`, etc. (optional) |
| `dat.args` | Positional args passed to do function (optional) |
| `dat.kwargs` | Keyword args passed to do function (optional) |


### `build:` and `run:` Sections

DAT specs can include `build:` and `run:` sections that define what happens during each phase:

**Example DAT spec with build and run:**
```yaml
# _spec_.yaml
scenarios.baseline:
  path: data/scenarios/baseline_{seed}/

  build:
    index.yaml: generators.baseline    # generate content from Bio generator

  run:
    - run . --agent claude             # execute scenario with agent
    - report .                         # generate report
```

**`build:` section:**
- Maps output filenames to Bio generators
- Each entry: `<filename>: <generator_name>`
- During `bio build`, each generator is called and output written to the filename
- Generators are Bio specs that produce content (scenarios, chemistries, etc.)

**`run:` section:**
- List of commands to execute sequentially
- Commands run in the context of the DAT folder (`.` refers to the DAT)
- Bio commands (like `run`, `report`) are recognized automatically
- Use `shell:` prefix for non-bio commands: `shell: python analysis.py`

### `_result_.yaml` (Generated when a DAT is run)
```yaml
# _result_.yaml
start_time: '2026-01-15 15:57:17.714576'
success: true
execution_time: 0.008767
end_time: '2026-01-15 15:57:17.723347'
run_metadata:
  final_state:
    A: 0.0
    B: 0.0
    D: 9.94
  scores:
    score: 0.997
    depletion: 1.0
    production: 0.994
  passing_score: 0.5
  success: true
```

### index.yaml (Bio Content)

The default Bio object for this DAT. When you call `bio.fetch("dat_name")`, this is what gets loaded:

```yaml
# index.yaml
scenario:
  _type: scenario
  chemistry:
    molecules: ...
    reactions: ...
  scoring:
    score: !ev "lambda trace: ..."
```

### Optional Components

Different DAT types may include additional files:
- `timeline.yaml` — full simulation state history
- `trace.yaml` — detailed agent action trace
- `report.csv` — tabular results
- `artifacts/` — large files, plots, etc.

---

## Overview

DAT (from dvc-dat) provides:
- **Folder-based storage** — each spec lives in a folder with `index.yaml`
- **Hierarchical organization** — nested folders for catalogs, scenarios, chemistries
- **Run integration** — DATs can define `do:` functions for execution

Bio wraps DAT for biological objects, adding hydration and typed objects on top.

---

## DAT Structure

A DAT folder contains an `index.yaml` (or `spec.yaml`) plus any supporting files:

```
catalog/
├── scenarios/
│   └── mutualism/
│       ├── index.yaml        # main spec
│       ├── hard.yaml         # variant
│       └── constitution.md   # included file
├── chemistries/
│   └── energy_ring.yaml      # single-file DAT
└── worlds/
    └── ecosystem/
        └── index.yaml
```

---

## Loading DATs

### Path-Style (Direct DAT Load)

```python
# Load folder DAT
bio.fetch("catalog/scenarios/mutualism")
# → loads catalog/scenarios/mutualism/index.yaml

# Load file within DAT folder
bio.fetch("catalog/scenarios/mutualism.hard")
# → loads catalog/scenarios/mutualism/hard.yaml

# Load single-file DAT
bio.fetch("catalog/chemistries/energy_ring")
# → loads catalog/chemistries/energy_ring.yaml
```

### Dotted-Style (Through lookup)

```python
bio.fetch("catalog.scenarios.mutualism")
# → lookup() checks loaded modules first
# → then tries filesystem: catalog/scenarios/mutualism/index.yaml
```

See [lookup()](../../commands/ABIO Lookup.md) for full resolution rules.

---

## DAT Configuration

Configuration lives in `.dataconfig.yaml` in your project root. Bio-specific config goes in the `dat` section:

```yaml
# .dataconfig.yaml
local_prefix: data/                    # DAT sync folder
dat:
  bio_roots:                           # Bio lookup roots
    - ./catalog
    - ~/.alienbio/catalog
```

### DataConfig Fields

| Field | Description |
|-------|-------------|
| `local_prefix` | Primary sync folder for DAT |
| `cwd` | Working directory for relative paths |
| `dat` | Dict for additional config (Bio uses `dat.bio_roots`) |

### Bio Resolution Order

When Bio resolves a dotted name like `scenarios.mutualism`, it checks:

1. **Python modules** — `sys.modules` for first segment
2. **bio_roots** — scans each root in order, converting dots to path separators

See [fetch()](../../commands/ABIO Fetch.md) for the complete resolution order.

---

## Bio vs DAT Loading

| Feature | DAT (`do.load`) | Bio (`lookup`) |
|---------|-----------------|----------------|
| Dynamic Python import | Yes | **No** |
| YAML loading | Yes | Yes |
| Hydration to typed objects | No | Yes |

**Key difference:** DAT's `do.load()` can dynamically import Python modules. Bio's `lookup()` only navigates already-loaded modules — no dynamic imports. This makes Bio's behavior predictable and safe.

### DAT's do.load() (for reference)

```python
from dvc_dat import do

# DAT can dynamically load Python
fn = do.load("mymodule.process_data")  # imports mymodule, gets process_data

# And navigate into dicts
value = do.load("mymodule.CONFIG.timeout")
```

### Bio's lookup() (no dynamic import)

```python
# Bio requires module to already be imported
import mymodule  # must import first

bio.lookup("mymodule.process_data")    # works - module is loaded
bio.lookup("mymodule.CONFIG.timeout")  # works - navigates into dict
```

---

## DAT Run Integration

DATs can specify a `do:` function to run:

```yaml
# In index.yaml
dat:
  kind: Dat
  do: alienbio.run

scenario.mutualism:
  chemistry: ...
  interface: ...
```

When you call `dat.run()`, it executes the `do:` function with the DAT as context.

Bio's `bio.run()` wraps this:
```python
bio.run("catalog/scenarios/mutualism")
# → loads DAT, calls its do: function (alienbio.run)
# → runs the scenario, returns results
```

---

## Recommended Project Structure

```
myproject/
├── catalog/                    # DAT root for specs
│   ├── scenarios/
│   │   ├── baseline/
│   │   │   └── index.yaml
│   │   └── competition/
│   │       └── index.yaml
│   ├── chemistries/
│   │   └── energy_ring.yaml
│   └── experiments/
│       └── sweep/
│           └── index.yaml
├── src/
│   └── myproject/              # Python source
│       ├── __init__.py
│       ├── agents.py
│       └── metrics.py
└── pyproject.toml
```

Configure via `.dataconfig.yaml`:
```yaml
# .dataconfig.yaml
local_prefix: data/
dat:
  bio_roots:
    - ./catalog
```

Now all of these work:
```python
bio.fetch("catalog/scenarios/baseline")      # path-style
bio.fetch("scenarios.baseline")              # dotted → checks modules, then bio_roots
bio.fetch("myproject.agents.LLMAgent")       # Python module (must be imported)
```

---

## See Also

- [lookup()](../../commands/ABIO Lookup.md) — Name resolution
- [fetch()](../../commands/ABIO Fetch.md) — Load and hydrate specs
- [Bio](Bio.md) — Bio class overview
