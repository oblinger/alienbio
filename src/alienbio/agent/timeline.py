"""Timeline for recording simulation events.

The Timeline is a system-centric chronological log of all events that occur
during an experiment. It records:
- Agent actions (with timestamps)
- Action results
- State changes
- Simulation steps
- Custom events

This is primarily for debugging and detailed analysis, complementing the
agent-centric Trace which focuses on the action→observation sequence.
"""

from dataclasses import dataclass, field
from typing import Any, Iterator, Optional


@dataclass
class TimelineEvent:
    """A single event in the timeline.

    Attributes:
        event_type: Type of event (e.g., "action", "result", "state_change", "step")
        time: Simulation time when event occurred
        data: Event-specific data
        step: Agent step number when event occurred (optional)
    """
    event_type: str
    time: float
    data: dict[str, Any]
    step: Optional[int] = None


class Timeline:
    """Chronological log of all simulation events.

    The timeline records events as they occur, allowing agents and debugging
    tools to query what has happened in the simulation.
    """

    def __init__(self) -> None:
        """Initialize an empty timeline."""
        self._events: list[TimelineEvent] = []
        self._total_cost: float = 0.0

    def __len__(self) -> int:
        """Return the number of events in the timeline."""
        return len(self._events)

    def __iter__(self) -> Iterator[TimelineEvent]:
        """Iterate over all events in chronological order."""
        return iter(self._events)

    def __getitem__(self, index: int) -> TimelineEvent:
        """Get event by index."""
        return self._events[index]

    def append(self, event: TimelineEvent) -> None:
        """Add an event to the timeline.

        Args:
            event: The event to add
        """
        self._events.append(event)
        # Track costs from action/result events
        if event.event_type == "result" and "cost" in event.data:
            self._total_cost += event.data["cost"]

    def recent(self, n: int) -> list[TimelineEvent]:
        """Return the n most recent events.

        Args:
            n: Number of events to return

        Returns:
            List of events, most recent last
        """
        return self._events[-n:] if n > 0 else []

    def since(self, time: float) -> list[TimelineEvent]:
        """Return all events since the given simulation time.

        Args:
            time: Simulation time threshold

        Returns:
            List of events with time > threshold
        """
        return [e for e in self._events if e.time > time]

    def since_index(self, index: int) -> list[TimelineEvent]:
        """Return all events since the given index.

        Args:
            index: Start index (exclusive)

        Returns:
            List of events after index
        """
        return self._events[index:] if index < len(self._events) else []

    def filter(self, event_type: str) -> list[TimelineEvent]:
        """Return all events of the given type.

        Args:
            event_type: Type of events to return

        Returns:
            List of matching events
        """
        return [e for e in self._events if e.event_type == event_type]

    def pending(self) -> list[TimelineEvent]:
        """Return events for actions that haven't completed yet.

        Returns:
            List of action events without corresponding result events
        """
        # Track which actions have results
        completed_actions: set[int] = set()
        for event in self._events:
            if event.event_type == "result" and "action_index" in event.data:
                completed_actions.add(event.data["action_index"])

        # Return actions without results
        pending: list[TimelineEvent] = []
        for i, event in enumerate(self._events):
            if event.event_type == "action" and i not in completed_actions:
                pending.append(event)
        return pending

    @property
    def total_cost(self) -> float:
        """Return total cost accumulated from all action results."""
        return self._total_cost
