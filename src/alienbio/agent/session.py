"""AgentSession: the main interface for agent-environment interaction.

AgentSession manages the lifecycle of an experiment, providing:
- observe() → Observation: get current state
- act(action) → ActionResult: execute an action
- is_done() → bool: check if experiment is complete
- score() → dict: evaluate scoring functions
- results() → ExperimentResults: get final results
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional, cast
import random

from .types import Action, ActionResult, Observation, ExperimentResults
from .timeline import Timeline, TimelineEvent
from .trace import Trace


@dataclass
class _ExecutionResult:
    """Internal result from action execution (before creating full ActionResult)."""
    success: bool
    error: Optional[str] = None
    data: Any = None
    cost: float = 0.0


class AgentSession:
    """Manages an agent's interaction with a scenario.

    The session wraps a scenario and simulator, providing a clean interface
    for agents to observe the environment, take actions, and receive feedback.

    Typical usage:
        session = AgentSession(scenario, seed=42)
        while not session.is_done():
            obs = session.observe()
            action = agent.decide(obs)
            result = session.act(action)
        results = session.results()
    """

    def __init__(self, scenario: dict[str, Any], seed: Optional[int] = None) -> None:
        """Initialize a session for the given scenario.

        Args:
            scenario: Scenario specification dict
            seed: Random seed for reproducibility
        """
        self._scenario = scenario
        self._seed = seed
        self._rng = random.Random(seed)

        # Initialize trace and timeline
        self._trace = Trace()
        self._timeline = Timeline()

        # Session state
        self._step_count = 0
        self._done = False
        self._done_reason: Optional[str] = None
        self._is_first_observe = True

        # Extract interface configuration
        interface = scenario.get("interface", {})
        self._actions_spec = interface.get("actions", {})
        self._measurements_spec = interface.get("measurements", {})
        self._budget = interface.get("budget", float("inf"))
        self._spent = 0.0

        # Timing configuration
        timing = interface.get("timing", {})
        self._default_wait = timing.get("default_wait", True)
        self._initiation_time = timing.get("initiation_time", 0.0)

        # Sim configuration
        sim_config = scenario.get("sim", {})
        self._max_steps = sim_config.get("max_agent_steps", float("inf"))
        self._steps_per_action = sim_config.get("steps_per_action", 1)

        # Initialize simulator
        # TODO: Create actual simulator from scenario containers
        self._simulator = self._create_simulator(scenario)
        self._sim_time = 0.0

    def _create_simulator(self, scenario: dict[str, Any]) -> Any:
        """Create and initialize the simulator from scenario.

        This is a placeholder that returns a mock simulator.
        The real implementation will use WorldSimulatorImpl.
        """
        # Placeholder - will integrate with real simulator
        return _MockSimulator(scenario)

    @property
    def scenario(self) -> dict[str, Any]:
        """Return the scenario specification."""
        return self._scenario

    @property
    def seed(self) -> Optional[int]:
        """Return the random seed used for this session."""
        return self._seed

    @property
    def simulator(self) -> Any:
        """Return the underlying simulator."""
        return self._simulator

    @property
    def trace(self) -> Trace:
        """Return the trace recording agent actions."""
        return self._trace

    @property
    def timeline(self) -> Timeline:
        """Return the timeline of all events."""
        return self._timeline

    @property
    def step_count(self) -> int:
        """Return the number of agent steps taken."""
        return self._step_count

    def observe(self) -> Observation:
        """Get the current observation.

        Returns:
            Observation with all information needed for the agent to decide
        """
        is_initial = self._is_first_observe
        self._is_first_observe = False

        return Observation(
            briefing=self._scenario.get("briefing", ""),
            constitution=self._scenario.get("constitution", ""),
            available_actions=self._actions_spec,
            available_measurements=self._measurements_spec,
            current_state=self._simulator.observable_state(),
            step=self._step_count,
            budget=self._budget,
            spent=self._spent,
            remaining=self._budget - self._spent,
            _is_initial=is_initial
        )

    def _make_action_result(
        self,
        action_name: str,
        success: bool,
        error: Optional[str] = None,
        data: Any = None,
        cost: float = 0.0,
        initiated: Optional[float] = None,
        completed: Optional[float] = None,
        completion_time: Optional[float] = None
    ) -> ActionResult:
        """Create an ActionResult with all Observation fields populated.

        ActionResult is a subclass of Observation, so it needs all the
        world state fields plus action-specific feedback.
        """
        return ActionResult(
            # Observation fields
            briefing=self._scenario.get("briefing", ""),
            constitution=self._scenario.get("constitution", ""),
            available_actions=self._actions_spec,
            available_measurements=self._measurements_spec,
            current_state=self._simulator.observable_state(),
            step=self._step_count,
            budget=self._budget,
            spent=self._spent,
            remaining=self._budget - self._spent,
            _is_initial=False,
            # ActionResult fields
            action_name=action_name,
            success=success,
            error=error,
            data=data,
            cost=cost,
            initiated=initiated,
            completed=completed,
            completion_time=completion_time
        )

    def act(self, action: Action) -> ActionResult:
        """Execute an action and return the result.

        Args:
            action: The action to execute

        Returns:
            ActionResult with success status, data, cost, etc.
        """
        # Record action in timeline
        action_index = len(self._timeline)
        self._timeline.append(TimelineEvent(
            event_type="action",
            time=self._sim_time,
            data={"name": action.name, "params": action.params, "index": action_index},
            step=self._step_count
        ))

        # Determine action kind (infer if not specified)
        kind = action.kind
        if kind is None:
            if action.name in self._measurements_spec:
                kind = "measurement"
            else:
                kind = "action"

        # Get action/measurement spec
        if kind == "measurement":
            spec = self._measurements_spec.get(action.name, {})
        else:
            spec = self._actions_spec.get(action.name, {})

        # Handle built-in actions
        result = self._execute_action(action, kind, spec)

        # Determine wait behavior
        wait = action.wait if action.wait is not None else self._default_wait

        # Handle timing
        duration = spec.get("duration", 0.0)
        initiated = self._sim_time

        if result.success:
            if wait and duration > 0:
                self._sim_time += duration
                completed = self._sim_time
            else:
                completed = initiated if duration == 0 else None

            # Update step count for actions (not measurements)
            if kind == "action" and action.name != "done":
                self._step_count += 1
                # Advance simulator
                for _ in range(self._steps_per_action):
                    self._simulator.step()
        else:
            completed = initiated

        # Track cost
        self._spent += result.cost

        # Create full ActionResult with all Observation fields
        final_result = self._make_action_result(
            action_name=action.name,
            success=result.success,
            error=result.error,
            data=result.data,
            cost=result.cost,
            initiated=initiated,
            completed=completed,
            completion_time=duration if wait and result.success else None
        )

        # Record result in timeline
        self._timeline.append(TimelineEvent(
            event_type="result",
            time=self._sim_time,
            data={
                "success": result.success,
                "cost": result.cost,
                "action_index": action_index
            },
            step=self._step_count
        ))

        # Record in trace (action + resulting ActionResult which is an Observation)
        self._trace.append(action, final_result, self._step_count, result.cost)
        self._is_first_observe = False

        return final_result

    def _execute_action(
        self,
        action: Action,
        kind: str,
        spec: dict[str, Any]
    ) -> _ExecutionResult:
        """Execute the action and return intermediate result.

        Args:
            action: The action to execute
            kind: "action" or "measurement"
            spec: Action/measurement specification from scenario

        Returns:
            _ExecutionResult with basic success/error/cost info
        """
        # Check if action exists
        if kind == "measurement":
            if action.name not in self._measurements_spec:
                return _ExecutionResult(
                    success=False,
                    error=f"Unknown measurement: {action.name}",
                    cost=0.1  # Small cost for errors
                )
        else:
            # Handle built-in actions
            if action.name == "done":
                self._done = True
                self._done_reason = "agent_done"
                return _ExecutionResult(success=True, cost=0.0)

            if action.name == "wait":
                duration = action.params.get("duration", 1.0)
                self._sim_time += duration
                return _ExecutionResult(success=True, cost=0.0)

            if action.name not in self._actions_spec:
                return _ExecutionResult(
                    success=False,
                    error=f"Unknown action: {action.name}",
                    cost=0.1  # Small cost for errors
                )

        # Validate parameters
        required_params = spec.get("params", {})
        for param_name, param_type in required_params.items():
            if param_name not in action.params:
                return _ExecutionResult(
                    success=False,
                    error=f"Missing required parameter: {param_name}",
                    cost=0.1
                )
            # Basic type validation
            value = action.params[param_name]
            if param_type == "float" and not isinstance(value, (int, float)):
                return _ExecutionResult(
                    success=False,
                    error=f"Parameter {param_name} must be a number",
                    cost=0.1
                )

        # Calculate cost
        base_cost = spec.get("cost", 1.0 if kind == "action" else 0.0)
        cost_formula = spec.get("cost_formula")
        if cost_formula:
            # Evaluate cost formula with action params
            try:
                cost = eval(cost_formula, {"base": base_cost, **action.params})
            except Exception:
                cost = base_cost
        else:
            cost = base_cost

        # Execute the action on simulator
        # TODO: Implement actual action execution
        data = None
        if kind == "measurement":
            data = self._simulator.observable_state()

        return _ExecutionResult(
            success=True,
            data=data,
            cost=cost
        )

    def poll(self) -> list[TimelineEvent]:
        """Return new events since last interaction.

        This is used in concurrent mode to check for completed actions.

        Returns:
            List of new timeline events
        """
        # Track last poll position
        if not hasattr(self, "_last_poll_index"):
            self._last_poll_index = 0
        events = self._timeline.since_index(self._last_poll_index)
        self._last_poll_index = len(self._timeline)
        return events

    def is_done(self) -> bool:
        """Check if the experiment is complete.

        Returns:
            True if max_steps reached, agent signaled done, or terminal state
        """
        if self._done:
            return True
        if self._step_count >= self._max_steps:
            self._done = True
            self._done_reason = "max_steps"
            return True
        # TODO: Check for terminal state
        return False

    def score(self) -> dict[str, float]:
        """Evaluate scoring functions.

        Returns:
            Dictionary of score name → value
        """
        scoring_config = self._scenario.get("scoring", {})
        scores: dict[str, float] = {}

        for name, scorer in scoring_config.items():
            if callable(scorer):
                try:
                    score_fn = cast(Callable[[Trace], float], scorer)
                    scores[name] = score_fn(self._trace)
                except Exception:
                    scores[name] = 0.0
            # TODO: Handle string scoring expressions

        # Add budget compliance score
        from ..registry.scoring import budget_score
        scores["budget_compliance"] = budget_score(self._trace, self._budget)

        return scores

    def results(self) -> ExperimentResults:
        """Get final experiment results.

        Returns:
            ExperimentResults with scores, trace, and pass/fail status
        """
        scores = self.score()
        main_score = scores.get("score", scores.get("budget_compliance", 0.0))
        passing_score = self._scenario.get("passing_score", 0.5)

        return ExperimentResults(
            scenario=self._scenario.get("name", "unknown"),
            seed=self._seed,
            scores=scores,
            trace=self._trace,
            passed=main_score >= passing_score,
            status="completed" if self._done else "incomplete",
            incomplete_reason=None if self._done else "not_done"
        )


class _MockSimulator:
    """Placeholder simulator for initial testing.

    This will be replaced with actual WorldSimulatorImpl integration.
    """

    def __init__(self, scenario: dict[str, Any]) -> None:
        self._scenario = scenario
        self._time = 0.0
        self._state = self._init_state(scenario)

    def _init_state(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """Initialize state from scenario containers."""
        containers = scenario.get("containers", {})
        return {"regions": containers.get("regions", {})}

    @property
    def time(self) -> float:
        return self._time

    def observable_state(self) -> dict[str, Any]:
        return self._state.copy()

    def step(self) -> None:
        self._time += 1.0
