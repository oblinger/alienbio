"""Agent interface for alienbio experiments.

This module provides the agent-environment interaction interface:

Core Types:
- Action: represents an action or measurement
- ActionResult: result of executing an action
- Observation: what the agent observes
- ExperimentResults: final results of an experiment

Recording:
- Timeline: system-centric chronological event log
- TimelineEvent: a single event in the timeline
- Trace: agent-centric action→observation history
- ActionObservationRecord: a single action→observation pair

Session:
- AgentSession: manages agent-environment interaction

Agents:
- Agent: protocol that all agents implement
- RandomAgent: takes random actions
- ScriptedAgent: follows predefined action sequence
- OracleAgent: has access to ground truth

Orchestration:
- run_experiment(): runs agent in scenario

Example usage:
    from alienbio.agent import AgentSession, Action

    session = AgentSession(scenario, seed=42)
    while not session.is_done():
        obs = session.observe()
        action = Action(name="sample_substrate", params={"region": "Lora"})
        result = session.act(action)
    results = session.results()

    # Or use run_experiment():
    from alienbio.agent import run_experiment, ScriptedAgent

    results = run_experiment(scenario, ScriptedAgent(actions=[...]), seed=42)
"""

from .types import Action, ActionResult, Observation, ExperimentResults
from .timeline import Timeline, TimelineEvent
from .trace import Trace, ActionObservationRecord
from .session import AgentSession
from .protocol import Agent, RandomAgent, ScriptedAgent, OracleAgent
from .experiment import run_experiment

__all__ = [
    # Core types
    "Action",
    "ActionResult",
    "Observation",
    "ExperimentResults",
    # Timeline
    "Timeline",
    "TimelineEvent",
    # Trace
    "Trace",
    "ActionObservationRecord",
    # Session
    "AgentSession",
    # Agents
    "Agent",
    "RandomAgent",
    "ScriptedAgent",
    "OracleAgent",
    # Orchestration
    "run_experiment",
]
