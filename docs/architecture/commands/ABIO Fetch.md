 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# bio.fetch()

Load and hydrate specs from DAT folders or Python modules.

---

## CLI

```bash
bio fetch <specifier>
```

The CLI command loads a spec by name.

```bash
bio fetch catalog/scenarios/mutualism
bio fetch experiments/sweep
```

*Remote sync: If a DAT path isn't found locally, fetch will pull it from remote storage. (Planned for later.)*

---

## Python API

```python
from alienbio import bio

run: dict = bio.fetch("data/experiments/run_001")                   # data directory — run results
scenario: Scenario = bio.fetch("data/experiments/run_001.scenario") # dig into structure
scenario: Scenario = bio.fetch("catalog.scenarios.mutualism")       # source tree — template
```

**Two fetch sources:**
- **Data directory** (paths with `/`) — Concrete results from completed runs
- **Source code tree** (dotted names) — Catalog of scenario templates

### Options

| Option | Description |
|--------|-------------|
| `raw=True` | Return unprocessed dict without resolving tags or hydrating |

---

## Processing Pipeline

Fetch loads and processes data in two phases:

```
1. Load & Resolve Tags
   - Load source (YAML file or Python global)
   - Parse YAML (if "yaml: " string format)
   - Recursively resolve tags (!include, !ref, !py, !ev)

2. Hydrate
   - Convert to typed objects (Scenario, Chemistry, etc.)
   - Wire up scope chains
```

Tag resolution happens in a single recursive pass — if an `!include` brings in content with more tags, those are resolved before continuing.

Use `raw=True` to get the unprocessed dict without resolving tags or hydrating.

---

## Caching (ORM Pattern)

Fetch uses an ORM-style caching pattern: the same DAT path always returns the same object instance.

```python
dat1 = bio.fetch("experiments/baseline")
dat2 = bio.fetch("experiments/baseline")
assert dat1 is dat2  # Same object from cache
```

**Key points:**
- Cache key is the resolved filesystem path
- Only processed results are cached (`raw=True` bypasses cache)
- Use `Bio.clear_cache()` to force reload from disk
- Cache is class-level (shared across all Bio instances)

---

## Resolution Order

Fetch resolves specifier strings by checking these rules in order:

| Rule | Name | Notes |
|------|------|-------|
| Begins with `/` | Absolute path | Loads within DAT at absolute path |
| Begins with `./` | Relative path | Loads within DAT relative to cwd |
| Has slashes | DAT path | Loads DAT; dots after path dig into content |
| First segment in `sys.modules` | Python module | Dereferences within the loaded module |
| Under a configured root | Configured root | Loads within DAT under root |
| Not found locally | Remote sync | Fetches from remote storage *(planned)* |

```python
bio.fetch("/data/experiments/run1")                      # absolute path → DAT
bio.fetch("./experiments/test1")                         # relative path → DAT
bio.fetch("catalog/scenarios/mutualism")                 # DAT path → loads index.yaml
bio.fetch("catalog/scenarios/mutualism.baseline")        # DAT + dig → scenario object
bio.fetch("catalog/scenarios/mutualism.config.timeout")  # DAT + deep dig → value
bio.fetch("alienbio.bio.Chemistry")                      # Python module
bio.fetch("scenarios.mutualism.baseline")                # configured root (no slashes)
```

Within source roots, when both `name.yaml` and `name.py` exist, YAML is checked first.

### Loading Within a DAT

When we say "loads within DAT", fetch:

1. Locates the DAT folder from the path portion (before any dots)
2. If no remaining dots → loads `index.yaml` and hydrates
3. If dots remain → loads the named YAML file in the DAT folder, dereferences into the structure, then hydrates the result

```python
bio.fetch("catalog/scenarios/mutualism")
# → loads catalog/scenarios/mutualism/index.yaml
# → hydrates entire content

bio.fetch("catalog/scenarios/mutualism.experiments.baseline")
# → loads catalog/scenarios/mutualism/index.yaml (without hydrating)
# → dereferences .experiments.baseline into the dict
# → hydrates the result
```

---

## Data Sources

Fetch can load data from two sources: **YAML files** or **Python module globals**.

### YAML Files

Fetch locates `.yaml` files in configured roots and loads them.

```yaml
# scenarios/mutualism.yaml
scenario.mutualism:
  name: Mutualism Demo
  chemistry: !ref mute.chem.energy_ring
```

### Python Module Globals

Python modules can export data as globals. Two formats are supported:

```python
# scenarios/mutualism.py

# Dict format - used directly
MUTUALISM = {
    "scenario.mutualism": {
        "name": "Mutualism Demo",
        "chemistry": "!ref mute.chem.energy_ring"
    }
}

# YAML string format - parsed first
MUTUALISM_YAML = """yaml:
scenario.mutualism:
  name: Mutualism Demo
  chemistry: !ref mute.chem.energy_ring
"""
```

Both formats go through the same processing pipeline after loading (see [[#Processing Pipeline]]).

---

## Examples

Examples below assume this configuration (see [[ABIO DAT]] for details):

```yaml
# .dataconfig.yaml
dat:
  source_roots:
    - path: ~/bio/catalog
```

### Loading from DAT Paths

```python
# Load a DAT (returns entire index.yaml content)
dat: dict = bio.fetch("~/bio/data/runs/exp_001")
# → loads ~/bio/data/runs/exp_001/index.yaml

# Load a scenario from a DAT with dig
scenario: Scenario = bio.fetch("~/bio/data/runs/exp_001.scenario")
# → loads index.yaml, digs into ["scenario"], hydrates
```

### Loading from Source Roots

```python
# Dotted path resolves through source roots
scenario: Scenario = bio.fetch("scenarios.mutualism")
# → finds ~/bio/catalog/scenarios/mutualism.yaml
# → hydrates to Scenario

# Dig into nested content
baseline: dict = bio.fetch("scenarios.mutualism.experiments.baseline")
# → loads scenarios/mutualism.yaml
# → digs into ["experiments"]["baseline"]
```

### Without Processing

```python
# Get raw dict without resolving tags or hydrating
raw: dict = bio.fetch("scenarios.mutualism", raw=True)
```

---

## See Also

- [DAT](../classes/infra/DAT.md) — DAT configuration and folder structure
- [Bio](../classes/infra/Bio.md) — Bio class overview
- [hydrate()](ABIO Hydrate.md) — Hydration details

