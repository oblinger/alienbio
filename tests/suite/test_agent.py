"""Acceptance tests for the Agent Protocol + ScriptedAgent (F020, Phase-2 D4).

Every test drives ``ScriptedAgent`` with synthetic ``Observation`` tuples
directly — no full world, no LLM, no network, no API key.
"""

from __future__ import annotations

import pytest

from alienbio.suite.agent import (
    Commit,
    Intervene,
    Measure,
    ReasoningStep,
    ScriptedAgent,
    Wait,
    WaitUntil,
)
from alienbio.suite.dist import Seed
from alienbio.suite.observation import Observation
from alienbio.suite.types import Answer


def _obs(probe_x: float) -> Observation:
    """A single-compartment synthetic observation exposing one probe value."""
    return ({"probe_x": probe_x},)


def _threshold_policy():
    """WaitUntil(probe_x > 5.0) -> Intervene(pump_rate) -> Commit."""
    return (
        WaitUntil(predicate=lambda obs: obs[0]["probe_x"] > 5.0, probe="probe_x"),
        Intervene(lever="pump_rate", value=2.0),
        Commit(answer=Answer(value="done", kind="scalar")),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Determinism
# ═══════════════════════════════════════════════════════════════════════════


def test_scripted_agent_determinism_same_policy_and_seed_same_action_log():
    observations = [_obs(0.1), _obs(1.0), _obs(6.0), _obs(6.0)]

    def run() -> tuple:
        agent = ScriptedAgent(policy=_threshold_policy(), seed=Seed(42))
        log = []
        for obs in observations:
            action, _ = agent.act(obs)
            log.append(action)
            if isinstance(action, Commit):
                break
        return tuple(log)

    log1 = run()
    log2 = run()
    assert log1 == log2
    assert len(log1) == 4
    assert isinstance(log1[0], Measure)
    assert isinstance(log1[1], Measure)
    assert isinstance(log1[2], Intervene)
    assert isinstance(log1[3], Commit)


def test_scripted_agent_determinism_holds_across_different_seeds_too():
    # The step-list path is a pure function of (policy, observations) — the
    # seed does not perturb it, so even distinct seeds agree byte-for-byte.
    observations = [_obs(0.1), _obs(6.0), _obs(6.0)]

    def run(seed_value: int) -> tuple:
        agent = ScriptedAgent(policy=_threshold_policy(), seed=Seed(seed_value))
        log = []
        for obs in observations:
            action, _ = agent.act(obs)
            log.append(action)
        return tuple(log)

    assert run(1) == run(999)


# ═══════════════════════════════════════════════════════════════════════════
# Conditional-hook branching (WaitUntil)
# ═══════════════════════════════════════════════════════════════════════════


def test_waituntil_measures_repeatedly_until_threshold_then_intervenes_and_commits():
    agent = ScriptedAgent(policy=_threshold_policy(), seed=Seed(1))

    action1, reasoning1 = agent.act(_obs(1.0))
    assert isinstance(action1, Measure)
    assert action1.probe == "probe_x"
    assert len(reasoning1) == 1
    assert isinstance(reasoning1[0], ReasoningStep)

    action2, _ = agent.act(_obs(2.0))
    assert isinstance(action2, Measure)  # still below threshold -> keeps measuring

    action3, _ = agent.act(_obs(6.0))  # crosses threshold now
    assert isinstance(action3, Intervene)
    assert action3.lever == "pump_rate"

    action4, _ = agent.act(_obs(6.0))
    assert isinstance(action4, Commit)


def test_waituntil_resolved_immediately_when_predicate_starts_true():
    agent = ScriptedAgent(policy=_threshold_policy(), seed=Seed(2))
    action, _ = agent.act(_obs(100.0))  # threshold already crossed on turn 0
    assert isinstance(action, Intervene)


# ═══════════════════════════════════════════════════════════════════════════
# Reasoning-step shape (one synthetic ReasoningStep per fired policy step)
# ═══════════════════════════════════════════════════════════════════════════


def test_one_synthetic_reasoning_step_per_fired_policy_step():
    agent = ScriptedAgent(policy=_threshold_policy(), seed=Seed(7))
    _, reasoning_measure = agent.act(_obs(0.0))
    assert len(reasoning_measure) == 1

    _, reasoning_intervene = agent.act(_obs(6.0))
    assert len(reasoning_intervene) == 1
    assert "Intervene" in reasoning_intervene[0].content

    _, reasoning_commit = agent.act(_obs(6.0))
    assert len(reasoning_commit) == 1
    assert "Commit" in reasoning_commit[0].content


# ═══════════════════════════════════════════════════════════════════════════
# Policy exhaustion after the terminal Commit
# ═══════════════════════════════════════════════════════════════════════════


def test_act_after_terminal_commit_raises():
    policy = (Commit(answer=Answer(value=1, kind="scalar")),)
    agent = ScriptedAgent(policy=policy, seed=Seed(9))
    action, _ = agent.act(_obs(0.0))
    assert isinstance(action, Commit)
    with pytest.raises(RuntimeError):
        agent.act(_obs(0.0))


# ═══════════════════════════════════════════════════════════════════════════
# Callable escape hatch
# ═══════════════════════════════════════════════════════════════════════════


def test_callable_policy_escape_hatch():
    def policy(obs: Observation, seed: Seed) -> tuple:
        return Wait(duration=1.0), (ReasoningStep(kind="callable", content="always wait"),)

    agent = ScriptedAgent(policy=policy, seed=Seed(3))
    action, reasoning = agent.act(_obs(0.0))
    assert isinstance(action, Wait)
    assert action.duration == 1.0
    assert reasoning[0].kind == "callable"
