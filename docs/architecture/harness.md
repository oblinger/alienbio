# Harness

Execution runner with logging and result aggregation.

**Subsystem**: [[execution]] > Experimentation

## Description
Harness is the top-level execution runner that manages experiment runs with proper timeout handling, logging, and result aggregation.

## Protocol Definition
```python
from typing import Protocol

class Harness(Protocol):
    """Execution runner for experiments."""

    timeout: float
    log_dir: str

    def run_experiment(self, experiment: Experiment) -> ExperimentResult:
        """Run single experiment with timeout and logging."""
        ...

    def run_test(self, test: Test) -> TestResult:
        """Run test batch with parallel execution."""
        ...

    def export_results(self, result: TestResult, path: str) -> None:
        """Export results for analysis."""
        ...
```

## Properties
| Property | Type | Description |
|----------|------|-------------|
| timeout | float | Max time per experiment |
| log_dir | str | Directory for execution logs |

## Methods
### run_experiment(experiment) -> ExperimentResult
Runs a single experiment with timeout and error handling.

### run_test(test) -> TestResult
Runs a test batch, potentially in parallel.

### export_results(result, path)
Exports results to JSON/CSV for analysis.

## See Also
- [[experimentation|Experimentation Subsystem]]
- [[experiment|Experiment]] - What gets run
- [[test|Test]] - Batch runs
