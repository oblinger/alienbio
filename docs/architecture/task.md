# Task
**Subsystem**: [[ABIO execution]] > Interface
Goal specification with scoring criteria.

## Description
Task defines what an agent should accomplish, including the setup, goal, scoring criteria, and constraints on available actions.

| Properties | Type | Description |
|----------|------|-------------|
| name | str | Task identifier |
| task_type | TaskType | Predict, diagnose, or cure |
| world | World | Initial world setup |
| available_measurements | list | What agent can observe |
| available_actions | list | What agent can do |

| Methods | Description |
|---------|-------------|
| score | Score the agent's result |
| is_complete | Check if goal is achieved |

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

## Methods
### score(result) -> float
Score the agent's result.

### is_complete(world) -> bool
Check if goal is achieved.

## Task Types
- **Predict**: Forecast future concentrations
- **Diagnose**: Identify disease from symptoms
- **Cure**: Restore healthy homeostasis

## See Also
- [[ABIO execution]]
- [[Measurement]] - Observation tools
- [[Action]] - Modification tools
- [[Experiment]] - Runs tasks
