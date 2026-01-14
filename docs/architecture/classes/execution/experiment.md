 [[Architecture Docs]] → [[ABIO Protocols|Protocols]]

# Experiment

Container for systematic exploration of scenarios with configurable iteration patterns.

## Overview

An Experiment defines a scenario and axes to sweep over. When executed via `bio.run()`, it:

1. References the scenario to run
2. Iterates according to the exploration pattern (default: `iterate`)
3. For each axis combination: runs scenario and collects result
4. Returns a list of result dictionaries

## Specification

```yaml
experiment.parameter_sweep:
  scenario: !ref baseline
  name: "temp{temperature}_me{initial_ME1}"

  axes:
    temperature: [20, 25, 30, 35]
    initial_ME1: [1.0, 2.0, 5.0]

  exploration: iterate    # or: sample, grid
  samples: 100            # for sample exploration
  seed: 42                # reproducibility
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scenario` | `Scenario` | required | Scenario to run |
| `name` | `str` | `None` | Naming pattern for child DATs |
| `axes` | `dict[str, list]` | `{}` | Parameter axes to sweep |
| `exploration` | `str` | `"iterate"` | Exploration pattern |
| `samples` | `int` | `100` | Number of samples (for `sample` exploration) |
| `seed` | `int` | `None` | Random seed for reproducibility |

### Exploration Patterns

| Pattern | Behavior |
|---------|----------|
| `iterate` | Run scenario once for each axis combination (Cartesian product) |
| `sample` | Randomly sample from axis space |
| `grid` | Alias for `iterate` |

## Run Behavior

When `bio.run(experiment)` is called:

```
┌─────────────────────────────────────────────────────────┐
│ 1. Resolve scenario reference                           │
│    └─ Load the referenced Scenario object               │
├─────────────────────────────────────────────────────────┤
│ 2. Generate iteration points                            │
│    └─ iterate: Cartesian product of all axes            │
│    └─ sample: Random sampling from axis space           │
├─────────────────────────────────────────────────────────┤
│ 3. For each axis_values:                                │
│    └─ Run scenario with axis values as parameters       │
│    └─ Compute result (scores, final_state, etc.)        │
│    └─ Merge result with axis values → result dict       │
├─────────────────────────────────────────────────────────┤
│ 4. Return list of result dictionaries                   │
└─────────────────────────────────────────────────────────┘
```

### Result Structure

Each result dictionary contains:

```python
{
    # Axis values for this run
    "temperature": 25,
    "initial_ME1": 2.0,

    # Computed results
    "scores": {"efficiency": 0.85, "stability": 0.92},
    "final_state": {"ME1": 1.2, "ME2": 3.4, ...},
    "success": True,

    # Metadata
    "seed": 42,
    "steps": 100,
}
```

## Example Usage

```python
bio = Bio()

# Fetch and run experiment
experiment: Experiment = bio.fetch("catalog/experiments/parameter_sweep")
results: list[dict] = bio.run(experiment)

# results is a list of dictionaries
for r in results:
    print(f"temp={r['temperature']}, ME1={r['initial_ME1']}: score={r['scores']['efficiency']}")

# Generate report from results
bio.report(results, format="table")
```

## Relationship to Report

The Experiment produces data; the Report formats it:

```
Experiment.run() → list[dict] → bio.report() → formatted output
```

See [Bio.report()](../infra/Bio.md#bioreport) for report generation.

## Protocol

```python
@biotype("experiment")
class Experiment:
    """Container for systematic scenario exploration."""

    scenario: Scenario
    name: str | None
    axes: dict[str, list[Any]]
    exploration: str  # "iterate" | "sample" | "grid"
    samples: int
    seed: int | None

    def run(self, bio: Bio) -> list[dict[str, Any]]:
        """Execute experiment and return list of result dictionaries."""
        ...
```

## See Also

- [Bio](../infra/Bio.md) — `bio.run()` executes experiments
- [[Scenario]] — Individual scenarios within experiments
- [[Task]] — Goal specification for agent evaluation
