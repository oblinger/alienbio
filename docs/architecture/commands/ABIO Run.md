 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# bio.run()

Run a scenario or experiment.

## Synopsis

```bash
bio run <target> [options]
```

## Description

The `run` command executes scenarios or experiments. The target can be:

- **Recipe name** (dots, no slashes): Builds first, then runs
- **DAT path** (slashes): Runs existing DAT directly

```bash
bio run scenarios.baseline              # recipe → build + run
bio run data/scenarios/baseline_s42/    # DAT → run directly
bio run experiments.mutualism           # experiment recipe → build + run all
```

## Options

| Option | Description |
|--------|-------------|
| `--agent <name>` | Agent to use (default: from spec or config) |
| `--seed <N>` | Random seed for reproducibility |
| `--steps <N>` | Override number of simulation steps |
| `--dry-run` | Validate without executing |

## Examples

**Run a scenario with specific agent:**
```bash
bio run scenarios.baseline --agent claude --seed 42
# → Created: data/scenarios/baseline_s42/
# → Running with agent: claude
# → Score: 0.85 (passed)
```

**Run a previously built scenario:**
```bash
bio run data/scenarios/baseline_s42/ --agent gpt-4
# → Running with agent: gpt-4
# → Score: 0.72 (passed)
```

**Run an experiment (all combinations):**
```bash
bio run experiments.mutualism
# → Created: data/experiments/mutualism_2026-01-09/
# → Running 60 scenarios (2 scenarios × 3 agents × 10 seeds)
# → Progress: [████████████████████] 100%
# → Reports generated: summary.md, comparison.png
```

## Behavior

### Call Chain

```
run(target) → build(target) → fetch(target)  # if target is string
```

`run()` never calls `fetch()` directly — it always goes through `build()`.

### Resolution by Target Type

| Target | Behavior |
|--------|----------|
| **DAT object or DAT path** | Check if `result` exists → if yes, return cached result; if no, call `DAT.run()` |
| **Recipe name (dots, no slashes)** | Call `build()` to create DAT, then `DAT.run()` |
| **Non-DAT spec (dict)** | Call `build()` in context of anonymous DAT, then `entity.run()` |

### Detailed Behavior

1. **If target has dots (no slashes)**: Treated as recipe name
   - Calls `bio build` internally to create DAT
   - Then runs the built DAT

2. **If target has slashes**: Treated as DAT path
   - Checks if DAT already has a `result` field
   - If already run → returns existing result (no re-execution)
   - If not run → calls `DAT.run()` and stores result

3. **For experiments**: Build creates nested scenario DATs, run executes all

4. **Non-DAT entities**: When building something that's not a full DAT spec:
   - `build()` creates it in context of an anonymous DAT
   - Returns the instantiated entity
   - `run()` then calls `entity.run()` (not `DAT.run()`)
   - Returns whatever the entity's `run()` method returns

## Python API

```python
from alienbio import bio

# Equivalent to CLI
result = bio.run("scenarios.baseline", agent="claude", seed=42)

# Run existing DAT
result = bio.run("data/scenarios/baseline_s42/", agent="claude")
```

## See Also

- [[ABIO Build|build]] — build without running
- [[ABIO Report|report]] — generate reports
- [[Execution Guide]] — execution model overview
