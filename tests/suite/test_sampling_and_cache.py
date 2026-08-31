"""M45.18 / M45.19 — the sampling every live call runs under is a stated,
recorded run parameter (temperature required for a live arm, top_p optional,
both on the manifest and every record line), and the fixed system prefix
(directive + brief) is sent as a prompt-cache block so a sweep's identical
prefix is paid for once per condition, not once per turn."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from alienbio.suite.dist import Seed
from alienbio.suite.experiment import (
    AGENTS,
    ExperimentSpec,
    estimate_cost,
    load_spec,
    run_experiment,
    sampling_violation,
    spec_from_dict,
    spec_to_dict,
)
from alienbio.suite.llm_agent import default_anthropic_llm_fn, PROVIDER_FIXED_SAMPLING

REPO = Path(__file__).resolve().parents[2]


def _llm_spec(**extra) -> ExperimentSpec:
    return ExperimentSpec(name="s", axes=(("pathway_length", (3,)),), drafter="identify_pathway", agent="llm", trials_per_condition=1, base_seed=1, **extra)


def test_sampling_parameters_round_trip_and_are_validated():
    spec = spec_from_dict({**spec_to_dict(_llm_spec()), "temperature": 0.7, "top_p": 0.9, "expected_cache_hit_rate": 0.5})
    assert (spec.temperature, spec.top_p, spec.expected_cache_hit_rate) == (0.7, 0.9, 0.5)
    assert spec_from_dict(spec_to_dict(spec)) == spec
    for key, bad in (("temperature", 1.5), ("top_p", -0.1), ("temperature", "hot"), ("expected_cache_hit_rate", 2)):
        with pytest.raises(ValueError, match=key):
            spec_from_dict({**spec_to_dict(_llm_spec()), key: bad})


def test_a_live_arm_without_temperature_is_refused_before_it_runs(tmp_path):
    assert sampling_violation(_llm_spec()) is not None
    assert sampling_violation(_llm_spec(temperature=1.0)) is None
    scripted = ExperimentSpec(name="s", axes=(("pathway_length", (3,)),), drafter="identify_pathway", agent="idle", trials_per_condition=1, base_seed=1)
    assert sampling_violation(scripted) is None  # nothing samples
    with pytest.raises(ValueError, match="temperature"):
        run_experiment(_llm_spec(), out_dir=str(tmp_path / "run"))


def test_the_catalog_live_file_declares_its_sampling():
    spec = load_spec(REPO / "catalog" / "experiments" / "exp04-first-live.yaml")
    assert spec.temperature == PROVIDER_FIXED_SAMPLING and sampling_violation(spec) is None


def test_provider_fixed_is_a_stated_regime_for_a_knobless_model():
    """M45.18 amendment (2026-08-31): the Claude 5 API refuses temperature /
    top_p ("deprecated for this model"), so `temperature: provider-fixed`
    states the regime, satisfies the live-arm gate, forbids a stray top_p,
    and sends NO sampling kwargs to the provider."""
    spec = spec_from_dict({**spec_to_dict(_llm_spec()), "temperature": PROVIDER_FIXED_SAMPLING})
    assert spec.temperature == PROVIDER_FIXED_SAMPLING and sampling_violation(spec) is None
    assert spec_from_dict(spec_to_dict(spec)) == spec
    with pytest.raises(ValueError, match="top_p"):
        spec_from_dict({**spec_to_dict(_llm_spec()), "temperature": PROVIDER_FIXED_SAMPLING, "top_p": 0.9})


def test_the_factory_hands_the_sampling_to_the_provider(monkeypatch):
    import alienbio.suite.llm_agent as llm_mod

    captured: dict = {}

    def fake(model, *, meter=None, **kw):
        captured.update(kw)
        return lambda directive, context, seed: {"type": "commit", "answer": None}

    monkeypatch.setattr(llm_mod, "default_anthropic_llm_fn", fake)
    AGENTS["llm"](_llm_spec(temperature=0.3, top_p=0.8))(Seed(1), {})
    assert captured["temperature"] == 0.3 and captured["top_p"] == 0.8


def test_the_provider_call_carries_sampling_and_a_cached_system_block(monkeypatch):
    """A fake `anthropic` module records the kwargs `messages.create` receives."""
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
    fn = default_anthropic_llm_fn("claude-sonnet-5", temperature=0.2, top_p=0.95)
    fn("DIRECTIVE", {"turn": 0}, Seed(1))
    kw = calls[0]
    assert kw["temperature"] == 0.2 and kw["top_p"] == 0.95
    assert kw["system"] == [{"type": "text", "text": "DIRECTIVE", "cache_control": {"type": "ephemeral"}}]
    assert kw["messages"] == [{"role": "user", "content": json.dumps({"turn": 0}, sort_keys=True)}]
    plain = default_anthropic_llm_fn("claude-sonnet-5", cache_system=False)
    plain("DIRECTIVE", {"turn": 0}, Seed(1))
    assert calls[1]["system"] == "DIRECTIVE" and "temperature" not in calls[1]
    fixed = default_anthropic_llm_fn("claude-sonnet-5", temperature=PROVIDER_FIXED_SAMPLING)
    fixed("DIRECTIVE", {"turn": 0}, Seed(1))
    assert "temperature" not in calls[2] and "top_p" not in calls[2]


def test_a_measured_cache_hit_rate_lowers_the_estimate():
    cold = estimate_cost(_llm_spec(temperature=1.0, model="claude-sonnet-5"))
    warm = estimate_cost(_llm_spec(temperature=1.0, model="claude-sonnet-5", expected_cache_hit_rate=0.8))
    assert warm.usd < cold.usd and "cache hit 80%" in warm.formula and warm.input_tokens == cold.input_tokens


def test_the_manifest_and_every_live_line_carry_the_sampling(tmp_path, monkeypatch):
    import alienbio.suite.llm_agent as llm_mod

    monkeypatch.setattr(llm_mod, "default_anthropic_llm_fn", lambda model, *, meter=None, **kw: (lambda d, c, s: {"type": "commit", "answer": None}))
    spec = ExperimentSpec(name="s", axes=(("pathway_length", (3,)), ("agent", ("llm", "idle"))), drafter="identify_pathway", agent="llm", trials_per_condition=1, base_seed=1, temperature=0.5, top_p=0.9, model="claude-sonnet-5")
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    manifest = json.loads((out / "manifest.json").read_text())
    assert (manifest["temperature"], manifest["top_p"]) == (0.5, 0.9)
    lines = [json.loads(l) for l in (out / "records.jsonl").read_text().splitlines()]
    by_agent = {l["agent"]: l for l in lines}
    assert (by_agent["llm"]["temperature"], by_agent["llm"]["top_p"]) == (0.5, 0.9)
    assert by_agent["idle"]["temperature"] is None and by_agent["idle"]["model"] is None
