"""ExperimentSpec module-doc findings (T084): one normaliser for both forms.

A directly built ``ExperimentSpec`` must derive what ``spec_from_dict`` derives
— ``expected_turns`` from the declared episode budget, and the idle arm under
``idle_baseline`` — so the Python form AUP's launchers use is priced and run
like the YAML form, and ``spec_from_dict(spec_to_dict(s)) == s``.

Offline, scripted agents only: no model calls, no spend.
"""

from __future__ import annotations

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
    spec = _live(axes=(("pi", (0.0,)), ("max_turns", (4, 40))), fixed_dials={"max_turns": 4})
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
    again = ExperimentSpec(**{f: getattr(spec, f) for f in spec.__dataclass_fields__})
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
