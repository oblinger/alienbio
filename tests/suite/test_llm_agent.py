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

import alienbio.suite.llm_agent as llm_agent_mod
from alienbio.suite.agent import ActionOutcome, Commit, Intervene, Measure, ScriptedAgent, Wait
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.brief import build_brief
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.llm_agent import (
    ACTION_INPUT_SCHEMA,
    DEFAULT_DIRECTIVE,
    LLMAgent,
    UsageMeter,
    _call_with_retry,
    cost_usd,
    default_anthropic_llm_fn,
    extract_action_json,
    price_for,
    render_observation,
    reply_from_content,
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


def test_llm_agent_malformed_mock_output_aborts_as_data_after_max_retries():
    # M46.4: parse exhaustion is recorded, not raised — the trial ends with a
    # tagged null Commit so a mass-trial sweep keeps going.
    def llm_fn(directive, context, seed):
        return {"type": "not_a_real_action"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0), max_retries=3)
    action, reasoning = agent.act(_obs())
    assert isinstance(action, Commit)
    assert action.params == {"aborted": "parse_exhausted"}
    assert action.answer.value is None
    assert reasoning[0].kind == "abort" and "3 attempts" in reasoning[0].content
    assert agent.parse_failures == 3
    assert agent.aborted == "parse_exhausted"


class _Block:
    def __init__(self, type: str, text: str = "", input=None):
        self.type = type
        self.text = text
        self.input = input


def test_extract_action_json_tolerates_fences_and_prose():
    bare = '{"type": "measure", "probe": "probe_x"}'
    fenced = "Here is my action:\n```json\n" + bare + "\n```\nDone."
    prefaced = "I will measure first. " + bare + " That is all."
    for text in (bare, fenced, prefaced):
        assert extract_action_json(text) == {"type": "measure", "probe": "probe_x"}
    assert extract_action_json("no json here at all") is None
    assert extract_action_json("[1, 2, 3]") is None  # a list is not an action


def test_reply_from_content_prefers_tool_use_then_text():
    payload = {"type": "wait", "duration": 2.0}
    assert reply_from_content([_Block("text", "ignored"), _Block("tool_use", input=payload)]) == payload
    fenced = _Block("text", "```json\n{\"type\": \"wait\", \"duration\": 1.0}\n```")
    assert reply_from_content([fenced]) == {"type": "wait", "duration": 1.0}
    assert reply_from_content([_Block("text", "nothing structured")]) == "nothing structured"


def test_llm_agent_accepts_a_fenced_string_reply_with_no_retry():
    def llm_fn(directive, context, seed):
        return "Sure!\n```json\n{\"type\": \"measure\", \"probe\": \"probe_x\"}\n```"

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    action, _ = agent.act(_obs())
    assert action == Measure(probe="probe_x")
    assert agent.parse_failures == 0


def test_llm_agent_counts_each_invalid_reply_before_succeeding():
    calls = []

    def llm_fn(directive, context, seed):
        calls.append(seed.value)
        if len(calls) < 3:
            return "garbage"
        return {"type": "wait", "duration": 1.0}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0), max_retries=3)
    action, _ = agent.act(_obs())
    assert isinstance(action, Wait)
    assert agent.parse_failures == 2
    assert agent.aborted is None
    assert len(set(calls)) == 3  # every retry rode a distinct child seed


def test_action_input_schema_matches_the_validator_vocabulary():
    assert set(ACTION_INPUT_SCHEMA["properties"]["type"]["enum"]) == {"measure", "intervene", "commit", "wait"}
    assert ACTION_INPUT_SCHEMA["required"] == ["type"]


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
    # M46.10: the exact prompt text is kept beside each hash for the taint audit.
    assert len(agent.prompt_texts) == 2
    assert all(DEFAULT_DIRECTIVE in t and "probe_x" in t for t in agent.prompt_texts)


# ═══════════════════════════════════════════════════════════════════════════
# Usage accounting / pricing / retry-backoff (M45.5)
# ═══════════════════════════════════════════════════════════════════════════


def test_usage_meter_record_and_snapshot_arithmetic():
    meter = UsageMeter()
    meter.record(model="m", input_tokens=10, output_tokens=5, latency_s=0.1)
    meter.record(
        model="m",
        input_tokens=20,
        output_tokens=7,
        cache_read_tokens=3,
        cache_write_tokens=1,
        latency_s=0.2,
        attempt=2,
    )
    snap = meter.snapshot()
    assert snap == {
        "calls": 2,
        "input_tokens": 30,
        "output_tokens": 12,
        "cache_read_tokens": 3,
        "cache_write_tokens": 1,
    }
    assert len(meter.per_call) == 2
    assert meter.per_call[1]["attempt"] == 2
    assert meter.per_call[1]["latency_s"] == 0.2
    assert meter.events == []


def test_price_for_unknown_model_raises_and_override_wins():
    with pytest.raises(ValueError, match="no published price"):
        price_for("some-unknown-model-20260101")
    assert price_for("some-unknown-model-20260101", override=(1.0, 2.0)) == (1.0, 2.0)
    # An override wins even for a KNOWN model.
    assert price_for("claude-sonnet-4-5-20250929", override=(9.0, 9.0)) == (9.0, 9.0)
    assert price_for("claude-sonnet-4-5-20250929") == (3.0, 15.0)


def test_cost_usd_with_cache_tokens():
    price = (2.0, 10.0)
    # 1,000,000 input @ $2 + 1,000,000 output @ $10 = $12.00
    assert cost_usd(1_000_000, 1_000_000, price) == pytest.approx(12.0)
    # Cache-read priced at 10% of input, cache-write at 125% of input.
    assert cost_usd(
        0, 0, price, cache_read_tokens=1_000_000, cache_write_tokens=0
    ) == pytest.approx(2.0 * 0.10)
    assert cost_usd(
        0, 0, price, cache_read_tokens=0, cache_write_tokens=1_000_000
    ) == pytest.approx(2.0 * 1.25)


class _FakeRateLimitError(Exception):
    pass


class _FakeAPIStatusError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _renamed(cls, name):
    """A subclass sharing ``name`` (``_retry_kind`` matches by class NAME)."""
    return type(name, (cls,), {})


def test_call_with_retry_retries_rate_limit_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm_agent_mod, "_sleep", lambda s: sleeps.append(s))

    rate_limit_cls = _renamed(_FakeRateLimitError, "RateLimitError")
    calls = [0]

    def create():
        calls[0] += 1
        if calls[0] < 3:
            raise rate_limit_cls("slow down")
        return "ok"

    meter = UsageMeter()
    result = _call_with_retry(create, meter, max_attempts=5, backoff_s=1.0)

    assert result == "ok"
    assert calls[0] == 3
    assert len(meter.events) == 2
    assert all(e["kind"] == "rate_limit" for e in meter.events)
    assert sleeps == [1.0, 2.0]


def test_call_with_retry_non_retryable_status_propagates_with_no_event():
    status_cls = _renamed(_FakeAPIStatusError, "APIStatusError")
    calls = [0]

    def create():
        calls[0] += 1
        raise status_cls("bad request", 400)

    meter = UsageMeter()
    with pytest.raises(Exception, match="bad request"):
        _call_with_retry(create, meter, max_attempts=5, backoff_s=1.0)
    assert calls[0] == 1
    assert meter.events == []


def test_call_with_retry_exhausts_max_attempts_and_reraises_last_error(monkeypatch):
    monkeypatch.setattr(llm_agent_mod, "_sleep", lambda s: None)
    rate_limit_cls = _renamed(_FakeRateLimitError, "RateLimitError")
    calls = [0]

    def create():
        calls[0] += 1
        raise rate_limit_cls(f"attempt {calls[0]}")

    meter = UsageMeter()
    with pytest.raises(Exception, match="attempt 3"):
        _call_with_retry(create, meter, max_attempts=3, backoff_s=0.5)
    assert calls[0] == 3
    assert len(meter.events) == 3


def test_llm_agent_usage_per_turn_deltas_when_mock_records_into_agent_meter():
    def llm_fn(directive, context, seed):
        agent.meter.record(model="m", input_tokens=100, output_tokens=20, latency_s=0.01)
        return {"type": "measure", "probe": "probe_x"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    agent.act(_obs())
    agent.act(_obs())

    usage = agent.usage
    assert usage["calls"] == 2
    assert usage["input_tokens"] == 200
    assert usage["output_tokens"] == 40
    assert len(usage["per_turn"]) == 2
    assert usage["per_turn"][0] == {
        "turn": 0,
        "calls": 1,
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    assert usage["per_turn"][1]["turn"] == 1
    assert usage["events"] == []


def test_llm_agent_usage_is_zero_when_mock_never_touches_meter():
    def llm_fn(directive, context, seed):
        return {"type": "measure", "probe": "probe_x"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0))
    agent.act(_obs())
    usage = agent.usage
    assert usage["calls"] == 0
    assert usage["per_turn"] == [
        {
            "turn": 0,
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }
    ]


def test_token_ceiling_still_aborts_before_a_call_with_a_meter():
    calls = []

    def llm_fn(directive, context, seed):
        calls.append(1)
        return {"type": "measure", "probe": "probe_x"}

    agent = LLMAgent(llm_fn=llm_fn, seed=Seed(0), token_ceiling=1)
    action, _ = agent.act(_obs())
    assert isinstance(action, Commit)
    assert action.params["aborted"] == "token_ceiling"
    assert calls == []


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
