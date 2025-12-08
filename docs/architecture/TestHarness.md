# TestHarness

Execution runner for experiments with logging and result aggregation.

**Subsystem**: [[execution]] > Experimentation

## Description
TestHarness manages experiment runs with proper timeout handling, logging, and result aggregation. It is attached to [[Context]] during test execution.

## Protocol Definition
```python
from typing import Protocol

class TestHarness(Protocol):
    """Execution runner for experiments."""

    timeout: float
    log_dir: str
    experiments: list[Experiment]
    results: list[ExperimentResult]

    def run_experiment(self, experiment: Experiment) -> ExperimentResult:
        """Run single experiment with timeout and logging."""
        ...

    def run_test(self, test: Test) -> TestResult:
        """Run test batch with parallel execution."""
        ...

    def run(self) -> list[ExperimentResult]:
        """Run all queued experiments."""
        ...

    def export_results(self, path: str) -> None:
        """Export results for analysis."""
        ...
```

## Properties
| Property | Type | Description |
|----------|------|-------------|
| timeout | float | Max time per experiment |
| log_dir | str | Directory for execution logs |
| experiments | list[Experiment] | Queue of experiments to run |
| results | list[ExperimentResult] | Collected results |

## Methods
### run_experiment(experiment) -> ExperimentResult
Runs a single experiment with timeout and error handling.

### run_test(test) -> TestResult
Runs a test batch, potentially in parallel.

### run() -> list[ExperimentResult]
Runs all queued experiments and returns results.

### export_results(path)
Exports results to JSON/CSV for analysis.

## See Also
- [[Context]] - Pegboard that holds this harness
- [[execution]] - Parent subsystem
- [[Experiment]] - What gets run
- [[Test]] - Batch runs
