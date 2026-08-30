# ABIO DAT
**Topic**: [[ABIO Topics]]
Data management via dvc_dat integration.

## Overview

ABIO uses [dvc_dat](https://github.com/oblinger/dvc-dat) for data persistence. See the [dvc_dat documentation](https://github.com/oblinger/dvc-dat/blob/main/docs/concepts.md) for full details.

**Key concepts:**
- **Dotted names** (do-system): Reference source code templates via `do()` and `create()`
- **Slash paths** (DAT storage): Reference data folders via `load()` and `save()`
- **Bio class**: Higher-level interface for biology objects via `Bio.fetch()` and `Bio.store()` — see [[Bio]]
- **Spec Language**: YAML syntax extensions (`!ev`, `!ref`, `!include`, typed keys, jobs) — see [[Spec Language]]

## Configuration

`.dataconfig.yaml` in the project root:

```yaml
sync_folder: data
mount_commands:
  - at: catalog
    folder: src/alienbio/catalog
  - at: fixtures
    module: tests.fixtures
```

## Operators

| Function | Description |
|----------|-------------|
| `do(name)` | Load object by dotted name (returns dict, module, or callable) |
| `create(spec, path=)` | Create a Dat from spec string or dict |
| `load(path)` | Load a Dat from a data path |
| `save(obj, path)` | Save object as Dat to data path |

## Usage

```python
from alienbio import do, create, load, save

# Load a template
template = do("fixtures.simple")

# Create a Dat from template
dat = create("fixtures.simple", path="runs/exp1")

# Load existing Dat
dat = load("runs/exp1")
print(dat.get_spec()["name"])

# Save data
dat = save({"name": "result", "value": 42}, "results/run1")
```

## Development Setup

During co-development, dvc_dat is symlinked:
```
src/dvc_dat -> ../../dvc-dat/dvc_dat
```

## See Also

- [dvc_dat concepts](https://github.com/oblinger/dvc-dat/blob/main/docs/concepts.md) - Core mental model
- [dvc_dat spec format](https://github.com/oblinger/dvc-dat/blob/main/docs/spec-format.md) - `_spec_.yaml` reference
- [[Bio]] - Higher-level `Bio.fetch()`, `Bio.store()`, `Bio.run()` for biology objects
- [[Spec Language]] - YAML syntax extensions (`!ev`, `!ref`, `!include`, typed keys, jobs)
- [[Decorators]] - `@biotype` registration for hydration
- [[ABIO Data]] - Organization of the `data/` folder
- [[alienbio]] - Top-level operators API
