"""Acceptance tests for ``LLMAgent`` (F025, opt-in, out of CI).

Every test but the last drives ``LLMAgent`` with a MOCK ``llm_fn`` — no
network, no API key. The last test is the single opt-in end-to-end path,
gated ``pytest.mark.skipif`` on an env flag + key presence, so a bare
``uv run pytest`` collects it as SKIPPED.
"""

from __future__ import annotations

import json
import os

import pytest

from alienbio.suite.agent import ActionOutcome, Commit, Intervene, Measure, ScriptedAgent, Wait
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.brief import build_brief
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.llm_agent import (
    DEFAULT_DIRECTIVE,
    LLMAgent,
    default_anthropic_llm_fn,
    render_observation,
)
from alienbio.suite.observation import narrow_observation, project_observation
from alienbio.suite.pipeline import build_suite
from alienbio.suite.runner import Budget, run
from alienbio.suite.types import Answer, AnswerObjective, SuiteSpec
from alienbio.suite.verify import SimConfig


def _identify_pathway_suite(pathway_length: int = 3, n_tasks: int = 1, seed_val: int = 1):
    arch = identify_pathway(pathway_length=pathway_length)
    spec = SuiteSpec(archetype_mix=Constant(arch), per_archetype={}, seed=0)
    return build_suite(spec, Seed(seed_val), n_tasks=n_tasks, distractor_count=1)


# ═══════════════════════════════════════════════════════════════════════════
# Taint guard — the hard invariant: render never sees hidden/oracle data
# ═══════════════════════════════════════════════════════════════════════════


def test_taint_guard_hidden_ground_truth_token_never_rendered():
    # A "full" ground-truth observation carries a hidden oracle token that a
    # real narrow_observation pass would strip before an agent ever sees it.
    full = ({"visible_probe": 1.0, "SECRET_ORACLE_TOKEN": 42.0},)
    narrowed = project_observation(full, hidden={"SECRET_ORACLE_TOKEN"})

    context = render_observation(narrowed, turn=0)
    rendered = DEFAULT_DIRECTIVE + json.dumps(context)

    assert "SECRET_ORACLE_TOKEN" not in rendered
    assert "42.0" not in rendered
    assert "visible_probe" in rendered  # sanity: the visible id DOES render

    # The oracle/score is never even a parameter render_observation accepts —
    # structurally it can only read the (already-narrowed) Observation tuple
    # and this agent's own turn counter.
    assert "objective_score" not in rendered
    assert "ground_truth" not in rendered


# ═══════════════════════════════════════════════════════════════════════════
# Mock llm_fn — well-formed actions parse; malformed rides the LLMOp retry path
# ═══════════════════════════════════════════════════════════════════════════


def _obs(probe_x: float = 1.0):
    return ({"probe_x": probe_x},)


def test_llm_agent_measure_action_from_mock():
    def llm_fn(directive, context, seed):
        return {"type": "measure", "probe": "probe_x", "reasoning": "checking probe_x"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    action, reasoning = agent.act(_obs())
    assert isinstance(action, Measure)
    assert action.probe == "probe_x"
    assert len(reasoning) == 1
    assert reasoning[0].content == "checking probe_x"


def test_llm_agent_intervene_action_from_mock():
    def llm_fn(directive, context, seed):
        return {"type": "intervene", "lever": "pump_rate", "value": 2.0}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    action, reasoning = agent.act(_obs())
    assert isinstance(action, Intervene)
    assert action.lever == "pump_rate"
    assert action.value == 2.0
    assert reasoning == ()  # no "reasoning" field in the mock reply


def test_llm_agent_wait_action_from_mock():
    def llm_fn(directive, context, seed):
        return {"type": "wait", "duration": 3.0}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    action, _ = agent.act(_obs())
    assert isinstance(action, Wait)
    assert action.duration == 3.0


def test_llm_agent_commit_action_from_mock():
    def llm_fn(directive, context, seed):
        return {"type": "commit", "answer": {"value": "X", "kind": "node_id"}}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    action, _ = agent.act(_obs())
    assert isinstance(action, Commit)
    assert action.answer == Answer(value="X", kind="node_id")


def test_llm_agent_malformed_mock_output_raises_after_max_retries():
    def llm_fn(directive, context, seed):
        return {"type": "not_a_real_action"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0), max_retries=3)
    with pytest.raises(ValueError, match="no schema-valid output"):
        agent.act(_obs())


def test_llm_agent_context_varies_by_turn_even_for_identical_observation():
    calls = []

    def llm_fn(directive, context, seed):
        calls.append(context)
        return {"type": "measure", "probe": "probe_x"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    agent.act(_obs(6.0))
    agent.act(_obs(6.0))  # byte-identical Observation, different turn
    assert calls[0] != calls[1]
    assert len(calls) == 2  # LLMOp cache did NOT short-circuit the 2nd call


# ═══════════════════════════════════════════════════════════════════════════
# Token-ceiling guard (Q3 = C): aborts the trial, recorded as such
# ═══════════════════════════════════════════════════════════════════════════


def test_token_ceiling_aborts_with_commit_tagged_and_never_calls_model_again():
    calls = []

    def llm_fn(directive, context, seed):
        calls.append(1)
        return {"type": "measure", "probe": "probe_x"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0), token_ceiling=1)
    action, reasoning = agent.act(_obs())
    assert isinstance(action, Commit)
    assert action.params["aborted"] == "token_ceiling"
    assert len(reasoning) == 1
    assert "token ceiling" in reasoning[0].content
    assert calls == []  # the model was never invoked once the ceiling tripped


# ═══════════════════════════════════════════════════════════════════════════
# Consistency with ScriptedAgent's shape (both satisfy Agent identically)
# ═══════════════════════════════════════════════════════════════════════════


def test_llm_agent_and_scripted_agent_are_interchangeable_at_the_call_site():
    def llm_fn(directive, context, seed):
        return {"type": "commit", "answer": {"value": "done", "kind": "scalar"}}

    llm_agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    scripted_agent = ScriptedAgent(
        policy=(Commit(answer=Answer(value="done", kind="scalar")),), seed=Seed(0)
    )
    for agent in (llm_agent, scripted_agent):
        action, reasoning = agent.act(_obs())
        assert isinstance(action, Commit)
        assert isinstance(reasoning, tuple)


# ═══════════════════════════════════════════════════════════════════════════
# TaskBrief + turn memory (M46.1/M46.2)
# ═══════════════════════════════════════════════════════════════════════════


def test_begin_composes_directive_from_brief():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    dials = {"observability": 1.0, "constitution": "Do no harm."}
    first_obs = narrow_observation(world.initial_state, dials, Seed(0).child("turn/0/observe"))
    brief = build_brief(
        task, world.chemistry, first_obs, dials, Budget(), 10, SimConfig(steps=10, sample_every=10)
    )

    captured = []

    def llm_fn(directive, context, seed):
        captured.append(directive)
        return {"type": "commit", "answer": {"value": None, "kind": "json"}}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    agent.begin(brief)
    agent.act(first_obs)

    directive = captured[0]
    assert json.dumps(brief.question, sort_keys=True) in directive
    assert str(brief.answer_kind) in directive
    for probe in brief.affordances.probes:
        assert probe in directive
    for lever in brief.affordances.levers:
        assert lever in directive
    assert "Do no harm." in directive


def test_history_records_prior_turn_action_observation_and_outcome():
    replies = [
        {"type": "measure", "probe": "probe_x", "reasoning": "look"},
        {"type": "commit", "answer": {"value": "done", "kind": "scalar"}},
    ]
    calls = []

    def llm_fn(directive, context, seed):
        calls.append(context)
        return replies[len(calls) - 1]

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    obs0 = _obs(1.0)
    action0, _ = agent.act(obs0)
    agent.notice(ActionOutcome(turn=0, action=action0, accepted=False, reason="unknown probe 'zz'"))
    obs1 = _obs(2.0)
    agent.act(obs1)

    history = calls[1]["history"]
    assert len(history) == 1
    entry = history[0]
    assert entry["action"] == {"type": "measure", "probe": "probe_x"}
    assert entry["observation"] == [dict(c) for c in obs0]
    assert entry["outcome"] == {"accepted": False, "reason": "unknown probe 'zz'"}


def test_memory_none_omits_history_key():
    def llm_fn(directive, context, seed):
        assert "history" not in context
        return {"type": "measure", "probe": "probe_x"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0), memory="none")
    agent.act(_obs(1.0))
    agent.act(_obs(2.0))


def test_memory_int_k_keeps_only_the_last_k_entries():
    calls = []

    def llm_fn(directive, context, seed):
        calls.append(context)
        return {"type": "measure", "probe": "probe_x"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0), memory=1)
    agent.act(_obs(1.0))
    agent.act(_obs(2.0))
    agent.act(_obs(3.0))

    assert "history" in calls[0] and calls[0]["history"] == []
    assert len(calls[2]["history"]) == 1
    assert calls[2]["history"][0]["turn"] == 1  # only the most recent prior turn


def test_memory_invalid_value_raises():
    def llm_fn(directive, context, seed):
        return {"type": "measure", "probe": "probe_x"}

    with pytest.raises(ValueError):
        LLMAgent(llm_fn=llm_fn, seed=Seed(0), memory="sometimes")


def test_prompt_hashes_one_per_real_call_and_differ_across_turns():
    def llm_fn(directive, context, seed):
        return {"type": "measure", "probe": "probe_x"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    assert agent.prompt_hashes == ()
    agent.act(_obs(1.0))
    agent.act(_obs(2.0))
    assert len(agent.prompt_hashes) == 2
    assert agent.prompt_hashes[0] != agent.prompt_hashes[1]


# ═══════════════════════════════════════════════════════════════════════════
# Opt-in end-to-end — SKIPPED unless ABIO_LLM_E2E is set and a key is present
# ═══════════════════════════════════════════════════════════════════════════

_E2E_ENABLED = bool(os.environ.get("ABIO_LLM_E2E")) and bool(
    os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ALIENBIO_ANTHROPIC_API_KEY")
)


@pytest.mark.skipif(
    not _E2E_ENABLED,
    reason="opt-in LLM e2e test: set ABIO_LLM_E2E=1 and ANTHROPIC_API_KEY to run",
)
def test_llm_agent_end_to_end_real_trial_via_scenario_runner():
    suite = _identify_pathway_suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    agent = LLMAgent(
        llm_fn=default_anthropic_llm_fn(),
        seed=Seed(0),
        token_ceiling=50_000,
    )
    dials = {"observability": 1.0}
    record = run(world, task, agent, dials, Seed(7), max_turns=10)

    assert record.terminal_reason in ("committed", "budget_exhausted", "max_turns")
    assert 0.0 <= record.objective_score <= 1.0
