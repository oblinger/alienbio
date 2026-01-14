 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# bio.fetch()

Load and hydrate specs from DAT folders or Python modules.

---

## Implementation Notes

**READ THIS FIRST** if implementing fetch/lookup.

### Specifier Routing (M2)

`fetch()` must detect specifier type and route appropriately:

```python
def fetch(self, specifier: str, hydrate: bool = True) -> Any:
    if specifier.startswith('/'):
        # Absolute path → load within DAT at absolute path
        return self._load_within_dat(specifier, hydrate)
    elif specifier.startswith('./'):
        # Relative path → load within DAT relative to current DAT
        return self._load_within_dat(self._current_dat / specifier[2:], hydrate)
    elif '/' in specifier:
        # Has slashes → DAT path
        return self._load_within_dat(specifier, hydrate)
    elif specifier.split('.')[0] in sys.modules:
        # First segment is loaded Python module → dereference into module
        return self._lookup_python(specifier)
    else:
        # Check configured bio_roots, then try remote (later)
        return self._lookup_roots(specifier, hydrate)
```

### Critical: Hydration Order

The "load within DAT" operation must hydrate AFTER dereferencing:

1. Load YAML into raw dict (no hydration yet)
2. Dereference remaining dots using `gets()` to navigate into dict
3. Hydrate the result

If you hydrate before dereferencing, typed objects don't support dict-like navigation.

### Suggested Internal Functions

```python
def _load_within_dat(self, dat_path: str, hydrate: bool = True) -> Any:
    """Load from DAT, optionally dereference dots, then hydrate."""
    # Split path into DAT folder and dotted name within
    # Load index.yaml as raw dict
    # If dots remain, navigate into dict with gets()
    # If hydrate=True, hydrate the result
    ...
```

See [[ABIO Roadmap#M2 — Bio Fetch & Lookup]] for full task list.

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

# Load a DAT (returns dict with all content from index.yaml)
dat: dict = bio.fetch("catalog/scenarios/mutualism")

# Load a typed object within a DAT (dots navigate into the structure)
scenario: Scenario = bio.fetch("catalog/scenarios/mutualism.baseline")
```

### Options

| Option | Description |
|--------|-------------|
| `hydrate=False` | Return Scope object without hydrating to typed objects |

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

Both formats go through the same processing pipeline after loading.

### Resolution Priority

When both `scenarios/mutualism.yaml` and `scenarios/mutualism.py` exist:

1. **YAML takes precedence** — the `.yaml` file is loaded
2. Python module is only checked if no YAML file is found

This keeps YAML as the primary declarative format while allowing Python when computation is needed.

### The `!py` Tag

YAML files can reference Python code using the `!py` tag. The tag resolves **relative to the YAML file's location**:

```yaml
# mute/chem/energy_ring.yaml
chemistry.energy_ring:
  reactions:
    synthesis: !py reactions.synthesis_rate  # loads mute/chem/reactions.py
```

The `!py` tag:
- Looks for a `.py` file in the same directory as the YAML
- Imports the module and accesses the specified attribute
- Supports dotted paths: `!py module.subattr.value`

### Processing Pipeline

Both YAML files and Python globals go through the same pipeline:

```
Load source (YAML file or Python global)
    ↓
Parse YAML string (if Python "yaml: " format)
    ↓
Resolve !include tags (inline other files)
    ↓
Resolve !ref tags (cross-references)
    ↓
Resolve !py tags (local Python access)
    ↓
Hydrate to typed objects
```

---

## Configuration

Fetch uses `.dataconfig.yaml` to locate data. Bio-specific config goes in the `dat` section:

```yaml
# .dataconfig.yaml
local_prefix: data/
dat:
  source_roots:
    # Each root has a filesystem path and optional Python module prefix
    - path: ./catalog
      module: myproject.catalog
    - path: ~/.alienbio/catalog
      module: alienbio.catalog
```

### Source Roots

Each source root pairs a filesystem path with an optional Python module prefix:

| Field | Description |
|-------|-------------|
| `path` | Filesystem directory to search for YAML files |
| `module` | Python module prefix for Python global lookups |

When resolving `mute.org.autotroph.krel`:

1. Check for YAML file at `<path>/mute/org/autotroph/krel.yaml`
2. If not found, check `<module>.mute.org.autotroph` for a `KREL` global
3. Continue to next root if neither found

See [DAT](../classes/infra/DAT.md) for full configuration details.

---

## Examples

### Loading Scenarios and Chemistries

```python
# Load a scenario DAT
scenario: Scenario = bio.fetch("catalog/scenarios/mutualism")
# → loads catalog/scenarios/mutualism/index.yaml
# → hydrates to Scenario object

# Load a chemistry
chemistry: Chemistry = bio.fetch("catalog/chemistries/energy_ring")
# → loads catalog/chemistries/energy_ring.yaml

# Load a variant file within a DAT folder
hard_mode: Scenario = bio.fetch("catalog/scenarios/mutualism/hard")
# → loads catalog/scenarios/mutualism/hard.yaml
```

### Getting Nested Content

```python
# Get a specific experiment from a scenario
baseline: Scenario = bio.fetch("catalog/scenarios/mutualism.experiments.baseline")

# Get results from the 'sweep' experimental run
summary: dict = bio.fetch("./sweep.results.summary")

# Get a config value from a Python module
timeout: int = bio.fetch("myapp.config.SETTINGS.timeout")
```

### Without Hydration

```python
# Get Scope without hydrating to typed objects
scope: Scope = bio.fetch("catalog/scenarios/mutualism", hydrate=False)
baseline: dict = scope["experiments"]["baseline"]
variant: Scope = scope["base"].child({"rate": 0.5})
```

---

### Hydration

After loading YAML, fetch hydrates the result — resolving tags, wiring up scope chains, and converting to typed objects. See [hydrate()](ABIO Hydrate.md) for details.

Use `hydrate=False` to skip hydration and get a Scope object instead.

---

## See Also

- [DAT](../classes/infra/DAT.md) — DAT configuration and folder structure
- [Bio](../classes/infra/Bio.md) — Bio class overview
- [hydrate()](ABIO Hydrate.md) — Hydration details

