 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Bio.cd()

Get or set the current DAT context.

---

## CLI

```bash
bio cd              # print current DAT path
bio cd <path>       # change current DAT
```

Like the shell's current directory, `bio` maintains a **current DAT** — the default context for commands that operate on a DAT.

```bash
bio cd data/experiments/mutualism_2026-01-09/
bio report                   # reports on current DAT
```

---

## Python API

```python
from alienbio import bio

# Get current DAT path
path: Path = bio.cd()

# Set current DAT
path: Path = bio.cd("data/experiments/run1")

# Relative specifiers resolve against current DAT
bio.cd("catalog/scenarios/mutualism")
scenario: Scenario = bio.fetch(".baseline")  # fetches from current DAT
```

---

## Auto-Setting

Some commands automatically set the current DAT:

```bash
# After build (auto-sets to newly created DAT)
bio build experiments.mutualism
# → current DAT is now data/experiments/mutualism_2026-01-10_001/

# After run (auto-sets to the DAT that was run)
bio run scenarios.baseline --seed 42
# → current DAT is now data/scenarios/baseline_42/
```

---

## See Also

- [DAT](../classes/infra/DAT.md) — DAT folder structure
- [fetch()](ABIO Fetch.md) — Load specs (uses current DAT for relative paths)
- [run()](ABIO Run.md) — Run scenarios
- [Bio](../classes/infra/Bio.md) — Bio class overview
