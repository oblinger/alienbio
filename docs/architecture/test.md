# Test
**Subsystem**: [[ABIO execution]] > Experimentation
Batch of experiments across variations.

## Description
Test represents a batch of experiments varying across worlds, agents, or task parameters, with aggregated statistics.

| Properties | Type | Description |
|----------|------|-------------|
| name | str | Test batch identifier |
| experiments | list | Individual experiments |
| variations | dict | Parameter variations being tested |

| Methods | Description |
|---------|-------------|
| run_all | Run all experiments in batch |

## Protocol Definition
```python
from typing import Protocol

class Test(Protocol):
    """Batch of experiments."""

    name: str
    experiments: list[Experiment]
    variations: dict[str, list[Any]]  # parameter -> values

    def run_all(self) -> "TestResult":
        """Run all experiments in batch."""
        ...
```

## Methods
### run_all() -> TestResult
Run all experiments in batch.

## TestResult
```python
class TestResult:
    experiment_results: list[ExperimentResult]
    aggregate_score: float
    by_variation: dict[str, dict[Any, float]]  # param -> value -> avg score
```

## Variation Types
- **World variations**: Different seeds, complexity levels
- **Agent variations**: Different models, prompts
- **Task variations**: Different difficulty, time horizons

## See Also
- [[ABIO execution]]
- [[Experiment]] - Individual runs
- [[TestHarness]] - Execution runner
