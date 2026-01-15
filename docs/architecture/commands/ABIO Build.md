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

1. Creates the folder using the `path:` template
2. Recursively calls `bio.build()` for each entry in `build:`
3. Writes generated content to the DAT folder

```bash
bio build scenarios.baseline --seed 42
# → Created: data/scenarios/baseline_42/
```

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
