# Task

Goal specification with scoring criteria.

**Subsystem**: [[execution|Execution]] > Interface

## Description

Task defines what an agent should accomplish, including the setup, goal, scoring criteria, and constraints on available actions.

## Protocol Definition

```python
from typing import Protocol

class TaskType(Enum):
    PREDICT = "predict"
    DIAGNOSE = "diagnose"
    CURE = "cure"

class Task(Protocol):
    """Goal specification for agents."""

    name: str
    task_type: TaskType
    world: World
    available_measurements: list[Measurement]
    available_actions: list[Action]

    def score(self, result: Any) -> float:
        """Score the agent's result."""
        ...

    def is_complete(self, world: World) -> bool:
        """Check if goal is achieved."""
        ...
```

## Properties

| Property | Type | Description |
|----------|------|-------------|
| name | str | Task identifier |
| task_type | TaskType | Predict, diagnose, or cure |
| world | World | Initial world setup |
| available_measurements | list | What agent can observe |
| available_actions | list | What agent can do |

## Task Types

- **Predict**: Forecast future concentrations
- **Diagnose**: Identify disease from symptoms
- **Cure**: Restore healthy homeostasis

## See Also

- [[interface|Interface Subsystem]]
- [[measurement|Measurement]] - Observation tools
- [[action|Action]] - Modification tools
- [[experiment|Experiment]] - Runs tasks
