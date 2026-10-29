"""T091 verifier X — follow-ups on round S (the live-model path, fake providers only)."""

from __future__ import annotations

import json

import pytest

from alienbio.suite import drafters, runner
from alienbio.suite.dist import Seed
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.llm_agent import (
    PROVIDER_DEFAULT_MAX_TOKENS,
    LLMAgent,
    _is_number,
    default_anthropic_llm_fn,
    pop_output_budget,
)


def _diagnose():
    return DRAFTERS["diagnose"](Seed(5), {})


# ── X1 — the stamp covers only the matched dials this spec sweeps ────────────


def _run(tmp_path):
    from alienbio.suite.experiment import run_experiment
    from alienbio.suite.spec import ExperimentSpec

    spec = ExperimentSpec(name="scheme", axes=(("rung", ("single",)),), drafter="conflict", agent="idle",
                          trials_per_condition=1, base_seed=1, fixed_dials={"levers": []})
    run_experiment(spec, out_dir=str(tmp_path / "run"))
    return spec


def test_an_unswept_dial_joining_the_matched_set_leaves_the_store_resumable(tmp_path, monkeypatch):
    from alienbio.suite.guards import preflight
    from alienbio.suite.store import world_scheme

    spec = _run(tmp_path)
    stamp = world_scheme(spec)
    monkeypatch.setattr(drafters, "WORLD_INVARIANT_DIALS", tuple(drafters.WORLD_INVARIANT_DIALS) + ("zzz_future_dial",))
    assert world_scheme(spec) == stamp
    assert preflight(spec, out_dir=str(tmp_path / "run"), resume=True).refusal is None


def test_a_swept_dial_joining_the_matched_set_refuses_the_resume(tmp_path, monkeypatch):
    from alienbio.suite.guards import preflight

    spec = _run(tmp_path)
    monkeypatch.setattr(drafters, "WORLD_INVARIANT_DIALS", tuple(drafters.WORLD_INVARIANT_DIALS) + ("rung",))
    refusal = preflight(spec, out_dir=str(tmp_path / "run"), resume=True).refusal
    assert refusal is not None and "another seed scheme" in str(refusal)


# ── X2 — no output budget: the estimate counts the provider's default bound ──


class _Fake:
    def __init__(self, meter):
        self.meter, self.calls = meter, 0

    def __call__(self, directive, context, seed):
        budget, context = pop_output_budget(context)
        self.calls += 1
        n = len(directive + json.dumps(context, sort_keys=True)) // 4
        out = budget or PROVIDER_DEFAULT_MAX_TOKENS
        self.meter.record(model="fake", input_tokens=n, output_tokens=out, latency_s=0.0)
        return {"type": "wait", "duration": 1.0}


def test_the_provider_fn_default_is_the_named_constant():
    import inspect

    default = inspect.signature(default_anthropic_llm_fn).parameters["max_tokens"].default
    assert default == PROVIDER_DEFAULT_MAX_TOKENS


def test_the_factory_agent_refuses_a_first_call_whose_default_reply_would_cross(monkeypatch):
    from alienbio.suite import llm_agent
    from alienbio.suite.agents import llm_agent_factory

    fakes: list[_Fake] = []

    def fake_fn(model, *, max_tokens, meter, **_kw):
        assert max_tokens == PROVIDER_DEFAULT_MAX_TOKENS
        fakes.append(_Fake(meter))
        return fakes[-1]

    monkeypatch.setattr(llm_agent, "default_anthropic_llm_fn", fake_fn)
    agent = llm_agent_factory(model=None, token_ceiling=1000)(Seed(1), {})
    assert isinstance(agent, LLMAgent) and agent.default_output_bound == PROVIDER_DEFAULT_MAX_TOKENS
    world, task = _diagnose()
    record = runner.run(world, task, agent, {}, Seed(5), max_turns=10)
    # Before X2: one call sent, 1355 measured tokens against a 1000 ceiling.
    assert record.aborted == "token_ceiling" and fakes[0].calls == 0


def test_the_summarizer_without_compact_budget_is_charged_the_default_bound():
    agent = LLMAgent(lambda d, c, s: {"type": "wait", "duration": 1.0}, Seed(1), memory="full", compact_at=2,
                     default_output_bound=PROVIDER_DEFAULT_MAX_TOKENS)
    assert agent._summary_estimate() == PROVIDER_DEFAULT_MAX_TOKENS
    assert agent._output_estimate(0) == PROVIDER_DEFAULT_MAX_TOKENS
    budgeted = LLMAgent(lambda d, c, s: {}, Seed(1), compact_at=2, compact_budget=50, max_tokens=80,
                        default_output_bound=PROVIDER_DEFAULT_MAX_TOKENS)
    assert budgeted._summary_estimate() == 50 and budgeted._output_estimate(0) == 80
    with pytest.raises(ValueError, match="default_output_bound"):
        LLMAgent(lambda d, c, s: {}, Seed(1), default_output_bound=0)


# ── X3 — an integer beyond float range is malformed, not a crash ─────────────


def test_a_huge_integer_is_a_parse_failure():
    huge = int("9" * 400)
    assert not _is_number(huge)
    replies = iter([{"type": "intervene", "lever": "r1", "value": huge}, {"type": "wait", "duration": 1.0}])
    agent = LLMAgent(lambda d, c, s: next(replies), Seed(1))
    agent.act(({"m": 1.0},))
    assert agent.parse_failures == 1 and agent.aborted is None


# ── X4 — a provider ValueError is a provider error, not parse exhaustion ─────


def test_a_provider_value_error_is_raised_not_filed_as_parse_exhaustion():
    calls = []

    def boom(d, c, s):
        calls.append(1)
        raise ValueError("provider said no")

    agent = LLMAgent(boom, Seed(1))
    with pytest.raises(ValueError, match="provider said no"):
        agent.act(({"m": 1.0},))
    assert len(calls) == 1 and agent.aborted is None and agent.parse_failures == 0


def test_a_provider_value_error_lands_as_an_error_record_with_its_class():
    from alienbio.suite.mass_trial import MassTrialRunner

    def boom(d, c, s):
        raise ValueError("provider said no")

    rmap = MassTrialRunner().run(
        [("x", (1,))], lambda seed, dials: _diagnose(), lambda seed, dials: LLMAgent(boom, seed),
        1, Seed(1), on_error="record",
    )
    (record,) = rmap.records
    assert record.error is not None and record.error.startswith("ValueError: provider said no")


# ── X5 — the "<id>" echo is rejected on the tool_use path too ────────────────


def test_a_tool_use_echo_is_a_parse_failure():
    replies = iter([{"type": "measure", "probe": "<id>"}, {"type": "wait", "duration": 1.0}])
    agent = LLMAgent(lambda d, c, s: next(replies), Seed(1))
    action, _ = agent.act(({"m": 1.0},))
    assert agent.parse_failures == 1 and type(action).__name__ == "Wait"


# ── X8 — the conftest blocks every alias of the client ───────────────────────


def test_the_client_alias_is_blocked_too():
    anthropic = pytest.importorskip("anthropic")
    for cls in (anthropic.Client, anthropic.Anthropic):
        with pytest.raises(RuntimeError, match="live provider in tests"):
            cls(api_key="sk-FAKE")
    with pytest.raises(RuntimeError, match="live provider in tests"):
        anthropic.AsyncClient(api_key="sk-FAKE")


# ── Y1 — the re-draft proof runs on every resume; an unrendered label refuses ─


def _exp08(tmp_path):
    from alienbio.suite.experiment import run_experiment
    from alienbio.suite.spec import REPO_ROOT, load_spec

    spec = load_spec(REPO_ROOT / "catalog/experiments/exp08.yaml")
    run_experiment(spec, out_dir=str(tmp_path / "run"))
    return spec


def test_a_stamped_store_whose_drafter_now_draws_another_world_refuses(tmp_path, monkeypatch):
    from alienbio.suite import guards
    from alienbio.suite.guards import preflight

    spec = _exp08(tmp_path)
    assert preflight(spec, out_dir=str(tmp_path / "run"), resume=True).refusal is None
    orig = guards.DRAFTERS[spec.drafter]
    monkeypatch.setitem(guards.DRAFTERS, spec.drafter, lambda seed, dials, **kw: orig(seed.child("v2"), dials, **kw))
    refusal = str(preflight(spec, out_dir=str(tmp_path / "run"), resume=True).refusal)
    assert "is stamped alike but" in refusal and "re-drafts a different world" in refusal


def test_an_unstamped_store_with_labels_the_grid_does_not_render_refuses(tmp_path):
    from alienbio.suite.guards import preflight

    spec = _exp08(tmp_path)
    out = tmp_path / "run"
    lines = []
    for line in (out / "records.jsonl").read_text().splitlines():
        d = json.loads(line)
        d["label"] = d["label"].replace("=", ":")
        lines.append(json.dumps(d))
    (out / "records.jsonl").write_text("\n".join(lines) + "\n")
    manifest = json.loads((out / "manifest.json").read_text())
    manifest.pop("world_scheme")
    (out / "manifest.json").write_text(json.dumps(manifest))
    refusal = str(preflight(spec, out_dir=str(out), resume=True).refusal)
    assert "which this spec's grid does not render" in refusal and "re-drafted identically" not in refusal
