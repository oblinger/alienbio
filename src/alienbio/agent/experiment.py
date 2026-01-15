"""Experiment orchestration.

This module provides the run_experiment() function that orchestrates
the agent-environment interaction loop.
"""

from typing import Any, Optional

from .types import ExperimentResults
from .session import AgentSession
from .agents import Agent


def run_experiment(
    scenario: dict[str, Any],
    agent: Agent,
    seed: Optional[int] = None
) -> ExperimentResults:
    """Run an experiment with the given scenario and agent.

    This is the main orchestration function that:
    1. Creates an AgentSession
    2. Calls agent.start()
    3. Loops: observe → decide → act until is_done()
    4. Calls agent.end()
    5. Returns results

    Args:
        scenario: Scenario specification dict
        agent: Agent to run
        seed: Random seed for reproducibility

    Returns:
        ExperimentResults with scores, trace, and pass/fail status
    """
    # Create session
    session = AgentSession(scenario, seed=seed)

    # Start agent
    agent.start(session)

    # Main loop
    while not session.is_done():
        obs = session.observe()
        action = agent.decide(obs)
        session.act(action)

    # Get results
    results = session.results()

    # End agent
    agent.end(results)

    return results
