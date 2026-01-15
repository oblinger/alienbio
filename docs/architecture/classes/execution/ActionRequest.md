 [[Architecture Docs]] → [[ABIO execution]]

# Action (Agent Request)

The agent's request to take an action or measurement.

## Overview
The Action dataclass represents what an agent wants to do. It specifies an action or measurement by name along with parameters. The environment validates the request against the scenario interface and executes it if valid.

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Name of the action (must match scenario interface) |
| `params` | dict[str, Any] | Parameters for the action |
| `kind` | Optional[str] | "action" or "measurement" (inferred if not provided) |
| `wait` | Optional[bool] | Whether to wait for completion (uses scenario default if None) |
| `reasoning` | Optional[str] | Optional explanation of why this action was chosen |

## Discussion

### Action vs Measurement
Actions modify the environment state; measurements observe without modifying. The `kind` field can explicitly specify which, but it's typically inferred from the scenario interface:

```python
# Explicit kind
Action(name="add_feedstock", params={"amount": 100}, kind="action")

# Inferred kind (looked up in scenario interface)
Action(name="add_feedstock", params={"amount": 100})
```

### Parameters
Parameters are passed as a dictionary and must match what the action expects:

```python
# Temperature adjustment
Action(name="adjust_temp", params={"delta": 5.0})

# Sampling with location
Action(name="sample_substrate", params={"location": "reactor_1"})
```

### Wait Behavior
The `wait` flag controls whether the action completes synchronously:
- `wait=True`: Action completes before next observation
- `wait=False`: Action initiates but may complete later
- `wait=None`: Uses scenario's `default_wait` setting

### Agent Reasoning
The `reasoning` field allows agents to record why they chose this action. This is useful for:
- Debugging agent behavior
- Creating audit trails
- Training and analysis

```python
Action(
    name="add_inhibitor",
    params={"molecule": "X", "amount": 50},
    reasoning="Population growing too fast, need to slow growth rate"
)
```

### Validation
The environment validates Action requests before execution:
1. Name must be in `available_actions` or `available_measurements`
2. Required parameters must be present
3. Sufficient budget must remain

Invalid requests result in `ActionResult(success=False, error="...")`.

## Protocol
```python
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class Action:
    """An action or measurement the agent wants to take."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)
    kind: Optional[str] = None  # "action" or "measurement"
    wait: Optional[bool] = None  # Uses scenario default if None
    reasoning: Optional[str] = None
```

## See Also
- [[Observation]] - What the agent sees before deciding
- [[ActionResult]] - Result of executing the action
- [[Action]] - Registered action functions (different concept)
- [[ABIO execution]] - Parent subsystem
