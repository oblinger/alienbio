 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Bio.fetch()

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

# Load and hydrate a spec
scenario = bio.fetch("catalog/scenarios/mutualism")
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
| Has slashes | DAT path | Loads within DAT at path |
| First segment in `sys.modules` | Python module | Dereferences within the loaded module |
| Under a configured root | Configured root | Loads within DAT under root |
| Not found locally | Remote sync | Fetches from remote storage *(planned)* |

```python
bio.fetch("/data/experiments/run1")           # absolute path
bio.fetch("./experiments/test1")              # relative path
bio.fetch("catalog/scenarios/mutualism")      # DAT path
bio.fetch("alienbio.bio.Chemistry")           # Python module
bio.fetch("scenarios.mutualism.baseline")     # configured root
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

## Configuration

Fetch uses `.dataconfig.yaml` to locate data. Bio-specific config goes in the `dat` section:

```yaml
# .dataconfig.yaml
local_prefix: data/
dat:
  bio_roots:
    - ./catalog
    - ~/.alienbio/catalog
```

When resolving dotted names (no slashes), Bio scans `bio_roots` in order after checking Python modules.

See [[classes/infra/DAT|DAT]] for full configuration details.

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

After loading YAML, fetch hydrates the result — resolving tags, wiring up scope chains, and converting to typed objects. See [[commands/ABIO Hydrate|hydrate()]] for details.

Use `hydrate=False` to skip hydration and get a Scope object instead.

---

## See Also

- [[classes/infra/DAT|DAT]] — DAT configuration and folder structure
- [[classes/infra/Bio|Bio]] — Bio class overview
- [[commands/ABIO Hydrate|hydrate()]] — Hydration details

