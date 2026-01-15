 [[Architecture Docs]] → [[ABIO execution]]

# ActionResult

Result of executing an agent's action request.

## Overview
ActionResult represents the outcome of executing an action or measurement. It includes success/failure status, any result data (especially for measurements), cost charged, timing information, and the new observable state after the action.

| Property | Type | Description |
|----------|------|-------------|
| `success` | bool | Whether the action executed successfully |
| `error` | Optional[str] | Error message if success is False |
| `data` | Optional[Any] | Result data (especially for measurements) |
| `cost` | float | Cost charged for this action |
| `new_state` | Optional[dict[str, Any]] | Observable state after action |
| `initiated` | Optional[float] | Simulation time when action started |
| `completed` | Optional[float] | Simulation time when action finished |
| `completion_time` | Optional[float] | Duration of the action |

## Discussion

### Success and Failure
An action can fail for several reasons:
- Invalid action name (not in scenario interface)
- Missing or invalid parameters
- Insufficient budget
- Scenario-specific validation failures

When `success=False`, the `error` field contains an explanation:

```python
result = ActionResult(
    success=False,
    error="Insufficient budget: need 50.0, have 30.0",
    cost=0.0  # No cost charged for failed actions
)
```

### Measurement Data
For measurements, the `data` field contains the observation result:

```python
# Example: population measurement result
result = ActionResult(
    success=True,
    data={"species_A": 1523, "species_B": 847},
    cost=5.0,
    new_state={"time": 100.0, "temperature": 37.0}
)
```

### Timing Information
The timing fields track when the action occurred in simulation time:
- `initiated`: Simulation time when the action started
- `completed`: Simulation time when the action finished
- `completion_time`: How long the action took (`completed - initiated`)

This matters for actions that take simulation time (e.g., "wait 10 time units").

### State Updates
The `new_state` field provides the observable environment state after the action executes. This allows agents to see the effects of their actions without requiring a separate observation step.

### Relationship to Observation
In the agent interface, `ActionResult` serves as the observation the agent receives after taking an action. The `new_state` field maps to `Observation.current_state`, providing continuity in the agent's perception loop.

## Protocol
```python
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ActionResult:
    """Result of executing an action."""

    success: bool
    error: Optional[str] = None
    data: Optional[Any] = None
    cost: float = 0.0
    new_state: Optional[dict[str, Any]] = None
    initiated: Optional[float] = None
    completed: Optional[float] = None
    completion_time: Optional[float] = None
```

## See Also
- [[Observation]] - Initial perception of the environment
- [[Action (Agent Request)]] - The agent's action request
- [[ABIO execution]] - Parent subsystem
