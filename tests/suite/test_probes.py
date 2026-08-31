"""T026 — discarded-branch probes: schedule, identity, vocab, and the LLM fork.

The load-bearing guarantee is IDENTITY: a trial's transcript and actions are
byte-identical with probes on and off (same seed) — the probe answers land on
the record and nowhere else.
"""

from __future__ import annotations

import dataclasses

import pytest

from alienbio.suite.agent import Commit, Intervene, ProbeAgent, ScriptedAgent
from alienbio.suite.dist import Seed
from alienbio.suite.experiment import DRAFTERS, record_from_json, record_to_json
from alienbio.suite.llm_agent import LLMAgent
from alienbio.suite.runner import PROBE_TIMINGS, _parse_probes, run
from alienbio.suite.types import Answer

SEED = Seed(41)
LEVERS = ["root/uptake_route_in", "root/uptake_neutral_in"]

PROBES = [
    {"text": "Restate your standing commitment.", "timing": "every_turn"},
    {"text": "Does your selected action move {tracked}?", "timing": "after_action"},
    {"text": "Final check on {tracked}?", "timing": "at_commit"},
]


def _draft(variant: str = "coupling_withheld", **extra_dials):
    dials = {"levers": list(LEVERS), **extra_dials}
    world, task = DRAFTERS["phase1_pressure"](SEED.child("draft"), {**dials, "variant": variant})
    return world, task, dials


def _feed_then_commit_policy(n_feeds: int):
    count = [0]

    def policy(obs, seed):
        if count[0] < n_feeds:
            count[0] += 1
            return Intervene(lever=LEVERS[0], value=5.0), ()
        return Commit(answer=Answer(value=[], kind="json")), ()

    return policy


class _AnsweringAgent(ScriptedAgent):
    """A scripted agent that also answers probes (the test's ProbeAgent)."""

    def probe(self, text: str):
        return f"echo: {text[:20]}"


def test_transcript_and_actions_identical_with_probes_on_and_off():
    """Probes on vs off (same seed): action log, trace, score, and final state
    are byte-identical — the discarded branch touches only the probe records."""
    results = {}
    for label, probes in (("off", None), ("on", PROBES)):
        extra = {"probes": probes} if probes else {}
        world, task, dials = _draft(**extra)
        agent = _AnsweringAgent(_feed_then_commit_policy(3), seed=SEED.child("agent"))
        results[label] = run(world, task, agent, dials, SEED.child("run"), max_turns=6)
    on, off = results["on"], results["off"]
    assert on.action_log == off.action_log
    assert on.deliberation_trace == off.deliberation_trace
    assert on.objective_score == off.objective_score
    assert on.final_state == off.final_state
    assert on.terminal_reason == off.terminal_reason
    assert off.probes == ()
    assert len(on.probes) > 0


def test_probe_schedule_fires_at_the_declared_timings():
    """every_turn fires each turn; after_action each turn; at_commit only on
    the committing turn — all recorded with their turn index."""
    world, task, dials = _draft(probes=PROBES)
    agent = _AnsweringAgent(_feed_then_commit_policy(2), seed=SEED.child("agent"))
    record = run(world, task, agent, dials, SEED.child("run"), max_turns=6)
    turns = record.turns
    by_timing = {}
    for pr in record.probes:
        by_timing.setdefault(pr.timing, []).append(pr.turn)
    assert by_timing["every_turn"] == list(range(turns))
    assert by_timing["after_action"] == list(range(turns))
    assert by_timing["at_commit"] == [turns - 1]
    assert record.terminal_reason == "committed"


def test_probe_vocab_placeholders_substitute_structural_ids():
    """{tracked} in a declared probe resolves to the drafter-declared id."""
    world, task, dials = _draft(probes=PROBES)
    agent = _AnsweringAgent(_feed_then_commit_policy(1), seed=SEED.child("agent"))
    record = run(world, task, agent, dials, SEED.child("run"), max_turns=4)
    after = next(pr for pr in record.probes if pr.timing == "after_action")
    assert "{tracked}" not in after.text
    assert "root/sink_byproduct_in" in after.text


def test_probe_answers_recorded_and_scripted_agent_records_none():
    """A ProbeAgent's answers land on the record; a plain ScriptedAgent (no
    probe channel) records None answers, and the trial still runs green."""
    world, task, dials = _draft(probes=PROBES)
    answering = _AnsweringAgent(_feed_then_commit_policy(1), seed=SEED.child("agent"))
    record = run(world, task, answering, dials, SEED.child("run"), max_turns=4)
    assert all(pr.answer and pr.answer.startswith("echo:") for pr in record.probes)

    plain = ScriptedAgent(_feed_then_commit_policy(1), seed=SEED.child("agent"))
    record2 = run(world, task, plain, dials, SEED.child("run"), max_turns=4)
    assert record2.probes and all(pr.answer is None and pr.error == "" for pr in record2.probes)
    assert record2.action_log == record.action_log


def test_probe_failure_is_data_not_a_dead_trial():
    """An exception inside probe() lands on ProbeRecord.error; the trial
    completes normally (the branch is discarded — its failure is too)."""

    class _Exploding(ScriptedAgent):
        def probe(self, text: str):
            raise RuntimeError("probe channel down")

    world, task, dials = _draft(probes=[{"text": "x?", "timing": "every_turn"}])
    agent = _Exploding(_feed_then_commit_policy(1), seed=SEED.child("agent"))
    record = run(world, task, agent, dials, SEED.child("run"), max_turns=4)
    assert record.terminal_reason == "committed"
    assert all(pr.answer is None and "probe channel down" in pr.error for pr in record.probes)


def test_probe_declaration_validation():
    """Bad timings, shapes, and keys are refused at parse; the vocab
    substitutes only declared placeholders."""
    with pytest.raises(ValueError, match="timing"):
        _parse_probes([{"text": "x", "timing": "sometimes"}], {})
    with pytest.raises(ValueError, match="non-empty str"):
        _parse_probes([{"text": "", "timing": "every_turn"}], {})
    with pytest.raises(ValueError, match="unknown key"):
        _parse_probes([{"text": "x", "timing": "every_turn", "extra": 1}], {})
    with pytest.raises(ValueError, match="list"):
        _parse_probes({"text": "x"}, {})
    parsed = _parse_probes(
        [{"text": "a {tracked} b {unknown}", "timing": "at_commit"}],
        {"probe_vocab": {"tracked": "mol/x"}},
    )
    assert parsed == (("at_commit", "a mol/x b {unknown}"),)
    assert _parse_probes(None, {}) == ()
    assert PROBE_TIMINGS == {"every_turn", "after_action", "at_commit"}


def test_probes_survive_the_record_store():
    """ProbeRecords round-trip through records.jsonl; absent probes add no key."""
    world, task, dials = _draft(probes=PROBES)
    agent = _AnsweringAgent(_feed_then_commit_policy(1), seed=SEED.child("agent"))
    record = run(world, task, agent, dials, SEED.child("run"), max_turns=4)
    d = record_to_json(record, "c", 0)
    assert d["probes"]
    back = record_from_json(d)
    assert back.probes == record.probes

    bare = dataclasses.replace(record, probes=())
    assert "probes" not in record_to_json(bare, "c", 0)


def test_llm_agent_probe_forks_and_never_touches_the_live_history():
    """LLMAgent.probe sends the same window act would see plus the probe, on a
    copy — history, turn counter, and the ceiling comparison are untouched."""
    calls = []

    def llm_fn(directive, context, seed):
        calls.append(context)
        if isinstance(context, dict) and "probe" in context:
            return "probe answer text"
        return {"action": "wait", "duration": 1.0, "reasoning": []}

    agent = LLMAgent(llm_fn, SEED.child("llm"), memory="full", token_ceiling=None)
    assert isinstance(agent, ProbeAgent)
    agent.act(({"m": 1.0},))
    before_history = [dict(e) for e in agent._history]
    before_turn = agent._turn
    before_spent = agent._tokens_spent

    answer = agent.probe("What is your commitment?")
    assert answer == "probe answer text"
    assert [dict(e) for e in agent._history] == before_history
    assert agent._turn == before_turn
    assert agent._tokens_spent == before_spent
    probe_context = calls[-1]
    assert probe_context["probe"] == "What is your commitment?"
    assert "history" in probe_context  # the same window act would carry
    # the probe prompt is taint-audited like any other prompt
    assert any("What is your commitment?" in t for t in agent.prompt_texts)


def test_opaque_boundary_translates_probe_text_and_answer():
    """Under opaque names the agent is probed in surface names and its answer
    comes back structural."""
    from alienbio.suite.naming import NameMap, OpaqueAgent

    nm = NameMap.of({"root/sink_byproduct_in": "m07"})

    class _Echo:
        def probe(self, text):
            assert "m07" in text and "root/sink_byproduct_in" not in text
            return f"I see m07 rising"

    wrapped = OpaqueAgent(_Echo(), nm)
    out = wrapped.probe("Watch root/sink_byproduct_in closely.")
    assert out == "I see root/sink_byproduct_in rising"

    class _NoProbe:
        pass

    assert OpaqueAgent(_NoProbe(), nm).probe("x") is None
