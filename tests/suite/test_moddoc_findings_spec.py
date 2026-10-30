"""ExperimentSpec module-doc findings (T084): one normaliser for both forms.

A directly built ``ExperimentSpec`` must derive what ``spec_from_dict`` derives
— ``expected_turns`` from the declared episode budget, and the idle arm under
``idle_baseline`` — so the Python form AUP's launchers use is priced and run
like the YAML form, and ``spec_from_dict(spec_to_dict(s)) == s``.

Offline, scripted agents only: no model calls, no spend.
"""

from __future__ import annotations

import dataclasses

import json

import pytest

from alienbio.suite.experiment import run_experiment
from alienbio.suite.spec import ExperimentSpec, estimate_cost, spec_from_dict, spec_to_dict


def _live(**kw):
    base = dict(
        name="py-live", axes=(("pi", (0.0,)),), drafter="pressure", agent="llm",
        trials_per_condition=1, base_seed=1, temperature="provider-fixed",
    )
    base.update(kw)
    return ExperimentSpec(**base)


# A ─ expected_turns ─────────────────────────────────────────────────────────


def test_python_form_derives_expected_turns_from_fixed_max_turns():
    spec = _live(fixed_dials={"max_turns": 20})
    assert spec.expected_turns == 20
    assert estimate_cost(spec).turns_per_trial == 20


def test_python_form_derives_expected_turns_from_largest_axis_level():
    # T091 D10: ``max_turns`` on the axis only (fixed and swept at once refuses).
    spec = _live(axes=(("pi", (0.0,)), ("max_turns", (4, 40))))
    assert spec.expected_turns == 40


def test_python_form_no_budget_prices_the_runner_default():
    assert _live().expected_turns == 50


def test_python_form_explicit_expected_turns_wins():
    assert _live(fixed_dials={"max_turns": 20}, expected_turns=8).expected_turns == 8


def test_python_form_expected_turns_matches_dict_form():
    py = _live(fixed_dials={"max_turns": 20})
    d = spec_to_dict(py)
    d.pop("expected_turns")
    assert spec_from_dict(d) == py


def test_python_form_expected_turns_round_trips():
    spec = _live(fixed_dials={"max_turns": 20})
    assert spec_from_dict(spec_to_dict(spec)) == spec


def test_python_form_refuses_non_positive_expected_turns():
    with pytest.raises(ValueError, match="expected_turns"):
        _live(expected_turns=0)


# B ─ idle_baseline ──────────────────────────────────────────────────────────


def _idle_spec(**kw):
    base = dict(
        name="py-idle", axes=(("rung", ("single",)),), drafter="conflict",
        agent="measure-commit", trials_per_condition=1, base_seed=3, idle_baseline=True,
        fixed_dials={"levers": []},
    )
    base.update(kw)
    return ExperimentSpec(**base)


def test_python_form_idle_baseline_adds_the_idle_arm_once():
    spec = _idle_spec()
    assert dict(spec.axes)["agent"] == ("measure-commit", "idle")
    again = ExperimentSpec(**{f.name: getattr(spec, f.name) for f in dataclasses.fields(spec) if f.init})
    assert again == spec
    assert [name for name, _ in again.axes].count("agent") == 1


def test_python_form_idle_baseline_round_trips():
    spec = _idle_spec()
    assert spec_from_dict(spec_to_dict(spec)) == spec


def test_python_form_idle_baseline_matches_dict_form():
    py = _idle_spec()
    d = spec_to_dict(py)
    d["axes"] = {"rung": ["single"]}
    d["idle_baseline"] = True
    assert spec_from_dict(d) == py


def test_idle_agent_gets_no_extra_arm():
    spec = _idle_spec(agent="idle")
    assert "agent" not in dict(spec.axes)


def test_python_form_idle_baseline_runs_the_idle_arm_and_resumes(tmp_path):
    spec = _idle_spec()
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    agents = sorted(dict(json.loads(line)["condition_key"])["agent"] for line in (out / "records.jsonl").read_text().splitlines())
    assert agents == ["idle", "measure-commit"]
    manifest = json.loads((out / "manifest.json").read_text())
    rebuilt = spec_from_dict(manifest["spec"])
    assert rebuilt == spec
    run_experiment(rebuilt, out_dir=str(out), resume=True)  # not refused as drift


# C ─ --dry names the model in force ─────────────────────────────────────────


def test_dry_names_the_pinned_model_on_a_live_spec_with_no_model(tmp_path, capsys):
    from alienbio.commands.suite_cmd import _run
    from alienbio.suite.llm_agent import PINNED_MODEL
    from pathlib import Path

    live = Path(__file__).resolve().parents[2] / "catalog" / "experiments" / "exp04-first-live.yaml"
    _run(str(live), str(tmp_path / "out"), dry=True, verbose=False)
    out = capsys.readouterr().out
    assert f"model: {PINNED_MODEL}\n" in out
    assert "model: None" not in out


# D ─ field validators run at construction, for both forms ──────────────────

# Each case is one bad value as the Python form would pass it (keyword
# arguments to ``ExperimentSpec``), the message both forms must raise, and the
# validator that owns it. ``axes`` is given as the dataclass tuple; the dict
# form gets the same value as a mapping.
_BAD_FIELDS = [
    ("model-alias", {"model": "claude-sonnet-latest"}, "floating alias"),
    ("model-axis", {"axes": (("pi", (0.0,)), ("model", ("claude-sonnet-latest",)))}, "floating alias"),
    ("agent-axis", {"axes": (("pi", (0.0,)), ("agent", ("llm", "nope")))}, "unknown agent axis level"),
    ("max-tokens", {"max_tokens": 0}, "max_tokens must be a positive int"),
    ("two-budgets", {"max_tokens": 512, "output_schedule": {"every": 2, "deep": 4096, "shallow": 512}}, "one per arm"),
    ("schedule-keys", {"output_schedule": {"every": 2}}, "output_schedule must be a mapping"),
    ("cost-ceiling", {"cost_ceiling_usd": 0}, "cost_ceiling_usd must be > 0"),
    ("price", {"price_usd_per_mtok": (1.0,)}, "price_usd_per_mtok must be a 2-sequence"),
    ("expected-turns", {"expected_turns": 0}, "expected_turns must be a positive int"),
    ("prompt-tokens", {"expected_prompt_tokens": 0}, "expected_prompt_tokens must be a positive int"),
    ("output-tokens", {"expected_output_tokens": -1}, "expected_output_tokens must be a positive int"),
    ("design-underpowered", {"design": {"target_effect_d": 0.2}}, "design needs"),
    ("design-axis", {"design": {"target_effect_d": 5.0, "primary_contrast": {"axis": "nope", "low": 0, "high": 1}}}, "is not a swept axis"),
    ("concurrency", {"concurrency": 0}, "concurrency must be a positive int"),
    ("matched-dials", {"matched_dials": ("nope",)}, "are not swept axes"),
    ("key-readout", {"key_readout": "nope"}, "key_readout must be one of"),
    ("temperature", {"temperature": 2.0}, "temperature must be a number in"),
    ("provider-fixed-top-p", {"temperature": "provider-fixed", "top_p": 0.9}, "top_p must be omitted"),
    ("top-p", {"temperature": 0.5, "top_p": 1.5}, "top_p must be a number in"),
    ("cache-hit-rate", {"expected_cache_hit_rate": 2.0}, "expected_cache_hit_rate must be a number in"),
    ("registration", {"registration": "  "}, "registration must be a non-empty string"),
]


def _dict_form(kw):
    d = spec_to_dict(_live())
    d.pop("expected_turns")
    for key, value in kw.items():
        d[key] = {name: list(levels) for name, levels in value} if key == "axes" else value
    return d


@pytest.mark.parametrize("kw,match", [(kw, m) for _, kw, m in _BAD_FIELDS], ids=[i for i, _, _ in _BAD_FIELDS])
def test_python_form_validates_each_field_like_the_dict_form(kw, match):
    with pytest.raises(ValueError, match=match) as py:
        _live(**kw)
    with pytest.raises(ValueError, match=match) as yaml_form:
        spec_from_dict(_dict_form(kw))
    assert str(py.value) == str(yaml_form.value)


def test_python_form_normalises_like_the_dict_form_and_round_trips():
    from alienbio.suite.power import PowerDesign

    spec = _live(
        temperature=0, top_p=1, cost_ceiling_usd=2, price_usd_per_mtok=[2, 10],
        design={"target_effect_d": 5.0}, trials_per_condition=4,
        output_schedule={"every": 2, "deep": 4096, "shallow": 512},
    )
    assert spec.temperature == 0.0 and isinstance(spec.temperature, float)
    assert spec.price_usd_per_mtok == (2.0, 10.0)
    assert isinstance(spec.design, PowerDesign)
    assert spec.matched_dials == ()
    assert spec_from_dict(spec_to_dict(spec)) == spec
    assert ExperimentSpec(**{f.name: getattr(spec, f.name) for f in dataclasses.fields(spec) if f.init}) == spec
