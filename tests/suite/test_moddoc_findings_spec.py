"""ExperimentSpec module-doc findings (T084): one normaliser for both forms.

A directly built ``ExperimentSpec`` must derive what ``spec_from_dict`` derives
— ``expected_turns`` from the declared episode budget, and the idle arm under
``idle_baseline`` — so the Python form AUP's launchers use is priced and run
like the YAML form, and ``spec_from_dict(spec_to_dict(s)) == s``.

Offline, scripted agents only: no model calls, no spend.
"""

from __future__ import annotations

import pytest

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
