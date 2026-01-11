 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Bio

The `bio` command is the CLI entry point for all ABIO operations.

---

## Synopsis

```bash
bio <command> [args]         # run a subcommand
bio cd                       # print current DAT
bio cd <dat>                 # change current DAT
```

---

## Current DAT

Like the shell's current directory, `bio` maintains a **current DAT** — the default target for commands that operate on a DAT.

```bash
bio cd data/experiments/mutualism_2026-01-09/
bio report                   # reports on current DAT
bio report summary           # same, with type specified
```

When no current DAT is set, commands require an explicit DAT argument.

### Setting Current DAT

```bash
# Explicitly
bio cd data/experiments/mutualism_2026-01-09/

# After build (auto-sets to newly created DAT)
bio build experiments.mutualism
# → current DAT is now data/experiments/mutualism_2026-01-10_001/

# After run (auto-sets to the DAT that was run)
bio run scenarios.baseline --seed 42
# → current DAT is now data/scenarios/baseline_42/
```

### Checking Current DAT

```bash
bio cd                       # print current DAT path
```

---

## Subcommands

| Command | Description |
|---------|-------------|
| `run` | Build and/or run scenarios and experiments |
| `build` | Build a recipe into a DAT without running |
| `fetch` | Retrieve a spec by name |
| `report` | Generate reports from results |
| `agent` | Manage agent registrations |
| `cd` | Get/set current DAT |

See [[ABIO Commands|Commands]] for full reference.

---

## See Also

- [[ABIO Commands|Commands]] — All commands
- [[ABIO Run|Bio.run()]] — Running scenarios and experiments
- [[Execution Guide]] — Execution model overview
