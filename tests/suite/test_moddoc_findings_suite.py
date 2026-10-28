"""Defects the suite module-doc writers reproduced with the source open.

Each section pins one finding: it failed before its fix and passes after.

A. ``compact_budget`` reached the summarizer only as model-visible text
   (``budget_tokens``); the provider fn's ``max_tokens`` seam never saw it,
   so the bound the compact-turn ceiling pre-check assumes was not enforced.
B. ``_action_cost`` honoured an agent-supplied ``params["cost"]``: a model
   emitting ``cost: 0`` (or negative) beat the budget, and a non-numeric one
   raised inside the loop as a ``TrialError``.
C. A trial that died mid-episode was never taint-audited: a secret the agent
   had already been sent landed with ``taint_hits=()`` under the crash's name.
"""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Measure, ReasoningStep, ScriptedAgent
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.llm_agent import (
    OUTPUT_BUDGET_KEY,
    LLMAgent,
    is_compact_context,
    pop_output_budget,
)
from alienbio.suite.pipeline import build_suite
from alienbio.suite import runner as runner_mod
from alienbio.suite.runner import TaintError, TrialError, run
from alienbio.suite.types import SuiteSpec


P1_LEVERS = ["root/uptake_route_in", "root/uptake_neutral_in"]


def _p1_world(seed: int = 5, **extra):
    dials = {"variant": "commitment_no_coupling", "levers": list(P1_LEVERS), **extra}
    world, task = DRAFTERS["phase1_pressure"](Seed(seed).child("d"), dials)
    return world, task, dials


# A ---------------------------------------------------------------------------


@pytest.mark.parametrize("max_tokens", [None, 300])
def test_compact_budget_rides_the_output_budget_seam(max_tokens):
    calls: list[tuple[bool, object]] = []

    def llm_fn(directive, context, seed):
        budget, stripped = pop_output_budget(context)
        calls.append((is_compact_context(stripped), budget))
        if is_compact_context(stripped):
            return "summary"
        return {"type": "wait", "duration": 1.0}

    world, task, dials = _p1_world()
    agent = LLMAgent(
        llm_fn, Seed(5).child("llm"), memory="full", compact_at=2,
        compact_budget=77, max_tokens=max_tokens,
    )
    record = run(world, task, agent, dials, Seed(5).child("r"), max_turns=4)
    assert record.compaction is not None
    compact = [b for is_c, b in calls if is_c]
    main = [b for is_c, b in calls if not is_c]
    assert compact == [77]
    assert main and all(b == max_tokens for b in main)
    # The model-facing prompt never carries the seam key.
    assert not any(f'"{OUTPUT_BUDGET_KEY}"' in t for t in agent.prompt_texts)


# B ---------------------------------------------------------------------------


def _pathway_world():
    spec = SuiteSpec(archetype_mix=Constant(identify_pathway(pathway_length=3)))
    suite = build_suite(spec, Seed(1), n_tasks=1, distractor_count=1)
    return suite.worlds[0], suite.tasks[0]


@pytest.mark.parametrize("cost", [0, -100.0, 0.25, "free", None])
def test_agent_supplied_cost_does_not_buy_budget(cost):
    world, task = _pathway_world()
    mol = next(iter(world.chemistry.molecules))

    def policy(observation, seed):
        del observation, seed
        return Measure(probe=mol, params={"cost": cost}), (ReasoningStep(kind="policy", content="m"),)

    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {"budget": 3.0}, Seed(5), max_turns=20)
    assert record.terminal_reason == "budget_exhausted"
    assert record.spent == 3.0
    assert len(record.action_log) == 3
    assert all(a.accepted for a in record.action_log)
    assert all("cost" in a.reason and "ignored" in a.reason for a in record.action_log)


def test_no_cost_key_leaves_the_reason_empty():
    world, task = _pathway_world()
    mol = next(iter(world.chemistry.molecules))

    def policy(observation, seed):
        del observation, seed
        return Measure(probe=mol), ()

    record = run(world, task, ScriptedAgent(policy, seed=Seed(0)), {"budget": 2.0}, Seed(5), max_turns=20)
    assert [a.reason for a in record.action_log] == ["", ""]


# C ---------------------------------------------------------------------------


class _LeakThenCrash:
    """Sends a prompt naming a hidden reaction id on turn 0, crashes on turn 1."""

    def __init__(self, leak: str) -> None:
        self._leak = leak
        self._texts: list[str] = []

    @property
    def prompt_texts(self):
        return tuple(self._texts)

    def act(self, observation):
        if self._texts:
            raise RuntimeError("provider 500")
        self._texts.append(f"the world contains {self._leak} somewhere")
        from alienbio.suite.agent import Wait

        return Wait(duration=1.0), ()


def test_a_crashed_trial_is_still_taint_audited():
    world, task, dials = _p1_world()
    leak = next(r for r in world.chemistry.reactions if r not in P1_LEVERS)
    with pytest.raises(TaintError) as info:
        run(world, task, _LeakThenCrash(leak), dials, Seed(5), max_turns=5)
    assert info.value.record.taint_hits == (leak,)
    assert info.value.record.terminal_reason == "error"
    assert isinstance(info.value.__cause__, RuntimeError)


def test_a_clean_crashed_trial_stays_a_trial_error():
    world, task = _pathway_world()
    with pytest.raises(TrialError) as info:
        run(world, task, _LeakThenCrash("nothing-secret-here"), {}, Seed(5), max_turns=5)
    assert info.value.record.taint_hits == ()


def test_an_audit_failure_on_the_partial_record_leaves_the_trial_error(monkeypatch):
    world, task, dials = _p1_world()
    leak = next(r for r in world.chemistry.reactions if r not in P1_LEVERS)

    def broken(*a, **k):
        raise ValueError("audit broke")

    monkeypatch.setattr(runner_mod, "audit_prompts", broken)
    with pytest.raises(TrialError) as info:
        run(world, task, _LeakThenCrash(leak), dials, Seed(5), max_turns=5)
    assert isinstance(info.value.cause, RuntimeError)
    assert any("audit broke" in n for n in getattr(info.value, "__notes__", []))
