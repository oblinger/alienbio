"""T059 — the LLM agent's per-turn output budget (AUP's Protocol Atlas ask,
2026-09-15): ``max_tokens`` as a factory dial, an ``output_schedule``
``{"every", "deep", "shallow"}`` that pools the same total into fewer, deeper
turns, both agent-side and world-untouched; the budget rides the ``LLMFn``
seam out of band (the model never sees it, a budget-less agent's context is
byte-identical), the provider fn sends it as the call's ``max_tokens``, and
every turn's budget lands beside its measured ``output_tokens`` on the
record's ``usage.per_turn``. Zero model calls."""

from __future__ import annotations

import json
import sys
import types

import pytest

from alienbio.suite.dist import Seed
from alienbio.suite.experiment import AGENTS, DRAFTERS, spec_from_dict
from alienbio.suite.llm_agent import (
    OUTPUT_BUDGET_KEY,
    LLMAgent,
    default_anthropic_llm_fn,
    is_probe_context,
    output_budget_for_turn,
    pop_output_budget,
)
from alienbio.suite.runner import run

SEED = Seed(59)
LEVERS = ["root/uptake_route_in", "root/uptake_neutral_in"]
SCHEDULE = {"every": 3, "deep": 4096, "shallow": 512}


def _llm_fn(seen):
    def llm_fn(directive, context, seed):
        seen.append(context)
        if is_probe_context(context):
            return "probe answer"
        return {"type": "wait", "duration": 1.0}

    return llm_fn


def _run(agent_kwargs, max_turns=7, probes=None):
    seen: list = []
    dials = {"variant": "commitment_no_coupling", "levers": list(LEVERS)}
    if probes:
        dials["probes"] = probes
    world, task = DRAFTERS["phase1_pressure"](SEED.child("d"), dials)
    agent = LLMAgent(_llm_fn(seen), SEED.child("llm"), **agent_kwargs)
    record = run(world, task, agent, dials, SEED.child("r"), max_turns=max_turns)
    return record, agent, seen


def _spec_dict(**extra):
    return {
        "name": "t", "axes": {}, "drafter": "phase1_pressure", "agent": "llm", "trials_per_condition": 1,
        "base_seed": 1, "fixed_dials": {"levers": []}, "drafter_kwargs": {"variant": "commitment_no_coupling"},
        **extra,
    }


def test_schedule_arithmetic():
    assert output_budget_for_turn(0, None, None) is None
    assert output_budget_for_turn(5, 800, None) == 800
    assert [output_budget_for_turn(t, None, SCHEDULE) for t in range(7)] == [4096, 512, 512, 4096, 512, 512, 4096]
    assert pop_output_budget({"turn": 1, OUTPUT_BUDGET_KEY: 512}) == (512, {"turn": 1})
    assert pop_output_budget({"turn": 1}) == (None, {"turn": 1})
    assert pop_output_budget("free text") == (None, "free text")


def test_no_budget_sends_a_byte_identical_context_and_stamps_nothing():
    _, agent, seen = _run({})
    assert all(OUTPUT_BUDGET_KEY not in c for c in seen)
    assert all("max_tokens" not in u for u in agent.usage["per_turn"])


def test_the_budget_rides_the_seam_out_of_band_and_lands_on_the_record():
    """Every main-line call carries the turn's budget under OUTPUT_BUDGET_KEY;
    the recorded prompt text (what the taint audit scans, what the model
    sees) does not; each per_turn usage entry pairs the budget with the
    turn's measured output tokens, so budget-matching is measured."""
    record, agent, seen = _run({"output_schedule": SCHEDULE}, max_turns=7)
    assert [c[OUTPUT_BUDGET_KEY] for c in seen] == [4096, 512, 512, 4096, 512, 512, 4096]
    assert all(OUTPUT_BUDGET_KEY not in text for text in agent.prompt_texts)
    assert record.usage is not None
    assert [u["max_tokens"] for u in record.usage["per_turn"]] == [4096, 512, 512, 4096, 512, 512, 4096]
    assert all("output_tokens" in u for u in record.usage["per_turn"])
    flat, _, seen_flat = _run({"max_tokens": 800}, max_turns=3)
    assert [c[OUTPUT_BUDGET_KEY] for c in seen_flat] == [800, 800, 800]
    assert flat.usage is not None and [u["max_tokens"] for u in flat.usage["per_turn"]] == [800, 800, 800]


def test_probe_calls_keep_the_provider_default():
    """A discarded-branch probe is not a main-line turn: no budget key."""
    _, _, seen = _run({"max_tokens": 800}, max_turns=2, probes=[{"text": "What moves with {target}?", "timing": "after_action"}])
    main = [c for c in seen if not is_probe_context(c)]
    probes = [c for c in seen if is_probe_context(c)]
    assert probes and all(OUTPUT_BUDGET_KEY not in c for c in probes)
    assert main and all(c[OUTPUT_BUDGET_KEY] == 800 for c in main)


def test_the_provider_fn_sends_the_turn_budget_and_strips_the_key(monkeypatch):
    calls: list[dict] = []

    class _Usage:
        input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens = 10, 2, 0, 0

    class _Response:
        usage = _Usage()
        content = [types.SimpleNamespace(type="tool_use", input={"type": "commit", "answer": None})]

    class _Messages:
        def create(self, **kw):
            calls.append(kw)
            return _Response()

    class _Client:
        def __init__(self, api_key):
            self.messages = _Messages()

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Client))
    monkeypatch.setattr("alienbio.config.get_api_key", lambda name: "k")
    fn = default_anthropic_llm_fn("claude-sonnet-5")
    fn("DIRECTIVE", {"turn": 0, OUTPUT_BUDGET_KEY: 4096}, Seed(1))
    fn("DIRECTIVE", {"turn": 1}, Seed(1))
    assert calls[0]["max_tokens"] == 4096
    assert calls[0]["messages"] == [{"role": "user", "content": json.dumps({"turn": 0}, sort_keys=True)}]
    assert calls[1]["max_tokens"] == 1024


def test_validation_refuses_visibly():
    for bad in ({"max_tokens": 0}, {"max_tokens": True}, {"output_schedule": {"every": 3, "deep": 4096}},
                {"output_schedule": {"every": 0, "deep": 1, "shallow": 1}}, {"output_schedule": [3, 4096, 512]},
                {"max_tokens": 800, "output_schedule": SCHEDULE}):
        with pytest.raises(ValueError, match="LLMAgent"):
            LLMAgent(_llm_fn([]), SEED, **bad)
    with pytest.raises(ValueError, match="spec: output_schedule"):
        spec_from_dict(_spec_dict(output_schedule={"every": 3}))
    with pytest.raises(ValueError, match="one per arm"):
        spec_from_dict(_spec_dict(max_tokens=800, output_schedule=SCHEDULE))


def test_spec_experiment_form_and_factory_thread_the_budget(monkeypatch):
    from alienbio.suite.expr_experiment import load_experiment, spec_to_text
    import alienbio.suite.llm_agent as llm_mod

    spec = spec_from_dict(_spec_dict(output_schedule=SCHEDULE))
    assert spec.output_schedule == SCHEDULE and spec.max_tokens is None
    text = (
        "!experiment\nname: t\ntask: !q phase1_pressure(variant='commitment_no_coupling')\n"
        "brief: !q brief(levers=[])\nagent: llm\ntrials_per_condition: 1\nbase_seed: 1\n"
        "output_schedule: {every: 3, deep: 4096, shallow: 512}\n"
    )
    loaded = load_experiment("<t>", text=text)
    assert loaded.output_schedule == SCHEDULE
    rendered = spec_to_text(loaded)
    assert "output_schedule: {every: 3, deep: 4096, shallow: 512}" in rendered
    assert load_experiment("<t>", text=rendered).output_schedule == SCHEDULE
    monkeypatch.setattr(llm_mod, "default_anthropic_llm_fn", lambda *a, **k: _llm_fn([]))
    factory = AGENTS["llm"](spec_from_dict(_spec_dict(max_tokens=800)))
    assert factory(SEED, {}).max_tokens == 800
    swept = factory(SEED, {"max_tokens": 2048})
    assert swept.max_tokens == 2048 and swept.output_schedule is None
    scheduled = AGENTS["llm"](spec_from_dict(_spec_dict()))(SEED, {"output_schedule": SCHEDULE})
    assert scheduled.output_schedule == SCHEDULE


def test_budget_dials_are_known_seed_matched_and_never_guarded():
    from alienbio.suite.drafters import WORLD_INVARIANT_DIALS, guarded_dials, runtime_dials
    from alienbio.suite.guards import no_peeking_violation, unknown_dials_violation

    assert {"max_tokens", "output_schedule"} <= runtime_dials()
    assert {"max_tokens", "output_schedule"} <= set(WORLD_INVARIANT_DIALS)
    assert not {"max_tokens", "output_schedule"} & guarded_dials()
    spec = spec_from_dict(_spec_dict(axes={"max_tokens": [512, 4096]}))
    assert unknown_dials_violation(spec) is None
    assert no_peeking_violation(spec) is None
