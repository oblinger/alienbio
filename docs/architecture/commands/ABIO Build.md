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
