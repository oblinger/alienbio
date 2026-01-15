"""Execution protocol definitions.

Protocols for the execution subsystem:
- Timeline: Sequence of states with intervention hooks
- World: Complete runnable setup
- Task: Goal specification with scoring
- Action: Agent action to perturb state
- Measurement: Function to observe state
- Experiment: Single world setup with task and agent
- Test: Batch of experiments
- TestHarness: Execution runner

These protocols will be implemented as the execution subsystem matures.
Note: State and Simulator protocols are in bio.py as they're closely
tied to Chemistry operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Protocol, runtime_checkable

# Import shared protocols
from .bio import State, Chemistry


@dataclass
class Organism:
    """An organism instance within a region.

    Attributes:
        id: Unique identifier for this organism
        species: Name of the species this organism belongs to
    """

    id: str = ""
    species: str = ""


@dataclass
class Region:
    """A spatial region containing organisms and substrates.

    Attributes:
        id: Unique identifier for this region
        substrates: Dict of substrate concentrations
        organisms: List of organisms in this region
    """

    id: str = ""
    substrates: dict[str, float] = field(default_factory=dict)
    organisms: list[Organism] = field(default_factory=list)


@dataclass
class Scenario:
    """Result of template instantiation (build phase).

    Contains the visible scenario (with opaque names) plus
    ground truth and visibility mapping for debugging/scoring.

    Attributes:
        molecules: Visible molecules (opaque names)
        reactions: Visible reactions (opaque names)
        regions: List of spatial regions with organisms
        _ground_truth_: Full scenario with internal names
        _visibility_mapping_: Map from internal to opaque names
        _seed: Random seed used for instantiation
        _metadata_: Optional metadata from spec
    """

    molecules: dict[str, Any] = field(default_factory=dict)
    reactions: dict[str, Any] = field(default_factory=dict)
    regions: list[Region] = field(default_factory=list)
    _ground_truth_: dict[str, Any] = field(default_factory=dict)
    _visibility_mapping_: dict[str, Any] = field(default_factory=dict)
    _seed: int = 0
    _metadata_: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Timeline(Protocol):
    """Protocol for simulation timeline.

    A Timeline is a sequence of States with hooks for interventions.
    """

    @property
    def states(self) -> List[State]:
        """All states in the timeline."""
        ...

    @property
    def current(self) -> State:
        """The current (latest) state."""
        ...

    def add_state(self, state: State) -> None:
        """Add a state to the timeline."""
        ...


@runtime_checkable
class World(Protocol):
    """Protocol for complete runnable world.

    A World combines a Chemistry, initial State, and Simulator
    into a complete runnable setup.
    """

    @property
    def chemistry(self) -> Chemistry:
        """The chemistry defining molecules and reactions."""
        ...

    @property
    def initial_state(self) -> State:
        """The initial state."""
        ...


@runtime_checkable
class Task(Protocol):
    """Protocol for task specification.

    A Task defines a goal with scoring criteria.
    Types: predict, diagnose, cure.
    """

    @property
    def name(self) -> str:
        """Task name."""
        ...

    @property
    def task_type(self) -> str:
        """Task type: predict, diagnose, or cure."""
        ...

    def score(self, result: Any) -> float:
        """Score the result."""
        ...


@runtime_checkable
class Action(Protocol):
    """Protocol for agent actions.

    An Action perturbs the system state.
    """

    @property
    def name(self) -> str:
        """Action name."""
        ...

    def apply(self, state: State) -> State:
        """Apply the action to a state."""
        ...


@runtime_checkable
class Measurement(Protocol):
    """Protocol for state measurements.

    A Measurement observes limited aspects of system state.
    """

    @property
    def name(self) -> str:
        """Measurement name."""
        ...

    def measure(self, state: State) -> Any:
        """Take a measurement from the state."""
        ...


# Experiment, Test, TestHarness protocols to be defined as that subsystem matures
