# Experiment

Single world setup with task, agent, and scoring.

**Subsystem**: [[execution]] > Experimentation

## Description
Experiment represents a single experimental run: one world, one task, one agent, producing one result.

## Protocol Definition
```python
from typing import Protocol, Any

class Experiment(Protocol):
    """Single experimental run."""

    world: World
    task: Task
    agent: Any  # The AI agent being tested
    result: "ExperimentResult | None"

    def run(self) -> "ExperimentResult":
        """Execute the experiment."""
        ...
```

## Properties
| Property | Type | Description |
|----------|------|-------------|
| world | World | The biological system |
| task | Task | What the agent should do |
| agent | Any | The AI system being evaluated |
| result | ExperimentResult | Outcome after running |

## ExperimentResult
```python
class ExperimentResult:
    score: float
    trace: list[tuple[str, Any]]  # (action/measurement, result)
    success: bool
    duration: float
```

## See Also
- [[execution]]
- [[Task]] - Goal specification
- [[Test]] - Batch of experiments
