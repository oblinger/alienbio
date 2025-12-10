# Task
**Subsystem**: [[ABIO execution]] > Interface
Goal specification with scoring criteria.

## Overview
Task defines what an agent should accomplish, including the setup, goal, scoring criteria, and constraints on available actions.

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Task identifier |
| `task_type` | TaskType | Predict, diagnose, or cure |
| `world` | World | Initial world setup |
| `available_measurements` | List[Measurement] | What agent can observe |
| `available_actions` | List[Action] | What agent can do |

| Method | Returns | Description |
|--------|---------|-------------|
| `score(result)` | float | Score the agent's result |
| `is_complete(world)` | bool | Check if goal is achieved |

## Discussion

### Task Types
- **Predict**: Forecast future concentrations
- **Diagnose**: Identify disease from symptoms
- **Cure**: Restore healthy homeostasis

### Usage Example
```python
from alienbio import Task, TaskType

task = Task(
    name="diagnose_diabetes",
    task_type=TaskType.DIAGNOSE,
    world=patient_world,
    available_measurements=[glucose_test, insulin_test],
    available_actions=[],  # Diagnosis only
)

result = agent.solve(task)
score = task.score(result)
```

## Protocol
```python
from typing import Protocol, List, Any
from enum import Enum

class TaskType(Enum):
    PREDICT = "predict"
    DIAGNOSE = "diagnose"
    CURE = "cure"

class Task(Protocol):
    """Goal specification for agents."""

    name: str
    task_type: TaskType
    world: World
    available_measurements: List[Measurement]
    available_actions: List[Action]

    def score(self, result: Any) -> float:
        """Score the agent's result."""
        ...

    def is_complete(self, world: World) -> bool:
        """Check if goal is achieved."""
        ...
```

## See Also
- [[Measurement]] - Observation tools
- [[Action]] - Modification tools
- [[Experiment]] - Runs tasks
- [[ABIO execution]] - Parent subsystem
