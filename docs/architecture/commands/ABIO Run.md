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
   - If not run → executes the `run:` section commands

3. **For experiments**: Build creates nested scenario DATs, run executes all

4. **Non-DAT entities**: When building something that's not a full DAT spec:
   - `build()` creates it in context of an anonymous DAT
   - Returns the instantiated entity
   - `run()` then calls `entity.run()` (not `DAT.run()`)
   - Returns whatever the entity's `run()` method returns

### The `run:` Section

When a DAT has a `run:` section in its spec, `bio run` executes each command sequentially:

```yaml
scenarios.baseline:
  path: data/scenarios/baseline_{seed}/
  build:
    index.yaml: generators.baseline
  run:
    - run . --agent claude       # execute scenario with agent
    - report .                   # generate report
```

**Command processing:**
- Commands run in the context of the DAT folder (`.` refers to current DAT)
- Bio commands (`run`, `report`, etc.) are recognized automatically
- Use `shell:` prefix for non-bio commands:
  ```yaml
  run:
    - run . --agent claude
    - shell: python analysis.py    # arbitrary shell command
    - report .
  ```
- Results are written to `_result_.yaml` in the DAT folder

## DAT Execution Context

When running a DAT, the `run` command creates an **isolated sandbox** to ensure clean execution:

### Sandboxing

```
bio run my_experiment/
  └─> Detects: target is a DAT (has _spec_.yaml)
  └─> Creates: new Bio() instance as sandbox
  └─> Sets: sandbox.cd(dat_path)  # current_dat = executing DAT
  └─> Runs: experiment within sandbox context
  └─> Saves: results via dvc_dat _result_.yaml
```

**Why sandboxing matters:**
- Each DAT execution is **fully self-contained**
- No accidental mixing with the global `bio` singleton state
- Results are stored with the DAT for **reproducibility**
- Multiple DATs can run concurrently without interference

### Sandbox Setup

When `run` detects a DAT target:

1. **Create sandbox**: `sandbox = Bio()` — fresh Bio instance
2. **Set current_dat**: `sandbox.cd(dat_path)` — point to executing DAT
3. **Execute**: All `fetch()`, `expand()` calls use sandbox context
4. **Save results**: Write `execution.yaml` to DAT folder

### Non-DAT Execution

When target is **not** a DAT (e.g., a standalone scenario YAML):
- Uses the global `bio` singleton
- No sandbox created
- Results printed but not persisted to disk

## DAT File Structure

See [[DAT|DAT File Structure]] for the complete Bio DAT folder structure, including:
- `index.yaml` — required scenario definition
- `execution.yaml` — generated results after run
- Optional components (timeline, trace, artifacts)

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
