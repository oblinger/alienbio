"""Defects the ``guards`` module doc surfaced (T084, 2026-10-28).

Each test is one stated break, red before its fix:

A. ``draft_violation`` drafted every condition but never built its brief, so
   every brief-side refusal that depends on the drafted world (``assays``
   naming reactions not in it, a lever on the readout, a malformed ``levers``
   entry) still landed as N error records after a clean ``--dry``; only the
   hidden-pool lever refusal was pulled forward, as a hand copy.
B. ``fixed_dials: {levers: null}`` passed the ``surface`` check, which tested
   only that the key existed, and ``build_brief`` refused inside every trial.
C. An unreadable ``manifest.json`` read as ``{}``, so ``_resume_spec_drift``
   saw no prior spec and a drifted spec resumed unchecked.
D. ``draft_violation`` counted every ``TypeError``/``KeyError`` as a config
   refusal, and skipped every other exception, so a generator bug read as a
   config error or as nothing at all.
E. ``bio suite run --dry`` printed ``resume: ok`` for a resume check it never
   ran.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from alienbio.suite import guards
from alienbio.suite.dist import Seed
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.experiment import spec_from_dict
from alienbio.suite.guards import declared_surface_violation, draft_violation, preflight
from alienbio.suite.spec import spec_to_dict

REPO = Path(__file__).resolve().parents[2]
W1_LEVERS = ["root/crux/uptake_waste_in", "root/crux/uptake_fast_in"]


def _w1(fixed=None, axes=None, **extra):
    fixed_dials = {"pi": 0.5, "levers": list(W1_LEVERS), "max_turns": 2, "sim_steps": 20}
    fixed_dials.update(fixed or {})
    return spec_from_dict({
        "name": "moddoc-guards", "axes": axes if axes is not None else {"certainty": [1.0]},
        "drafter": "pressure", "agent": "idle", "trials_per_condition": 1, "base_seed": 1,
        "fixed_dials": fixed_dials, **extra,
    })


def _draft_verdict(spec, tmp_path):
    flight = preflight(spec, out_dir=str(tmp_path / "out"))
    assert not (tmp_path / "out").exists(), "preflight creates nothing"
    return flight, dict(flight.checks)["draft"]


# A ---------------------------------------------------------------------------


def test_assays_naming_no_reaction_refuses_in_the_draft_check(tmp_path):
    flight, why = _draft_verdict(_w1({"assays": ["root/no_such/rxn"]}), tmp_path)
    assert why is not None and "root/no_such/rxn" in why and "'certainty': 1.0" in why
    assert not flight.ok


def test_a_lever_on_the_readout_refuses_in_the_draft_check(tmp_path):
    _world, task = DRAFTERS["pressure"](Seed(1), {"pi": 0.5, "levers": list(W1_LEVERS)})
    target = task.question.structured["target"]
    flight, why = _draft_verdict(_w1({"levers": [*W1_LEVERS, target]}), tmp_path)
    assert why is not None and target in why and "readout" in why and "'certainty': 1.0" in why


def test_a_malformed_lever_entry_refuses_in_the_draft_check(tmp_path):
    entry = {"id": W1_LEVERS[0], "rate": 3}
    flight, why = _draft_verdict(_w1({"levers": [entry, W1_LEVERS[1]]}), tmp_path)
    assert why is not None and "unknown key(s) ['rate']" in why and "'certainty': 1.0" in why


def test_the_brief_refusal_names_each_refusing_condition(tmp_path):
    """Every condition is built, and only the refusing one is named."""
    spec = _w1(axes={"assays": [["root/no_such/rxn"], ["root/crux/sink_target/rxn"]]})
    why = draft_violation(spec)
    assert why is not None and "root/no_such/rxn" in why
    assert why.count("condition") == 1


def test_a_clean_spec_still_passes_the_draft_check():
    assert draft_violation(_w1()) is None


def test_the_hidden_pool_refusal_is_build_briefs_own():
    """The hand copy is gone: the text is ``build_brief``'s."""
    dials = {"pi": 0.5, "levers": list(W1_LEVERS), "sim_dt": 0.005, "sim_steps": 200}
    _world, task = DRAFTERS["pressure_w2"](Seed(3), dials)
    ledger = task.setup["hidden_ids"][-1]
    spec = spec_from_dict({
        "name": "hidden", "axes": {"pi": [0.5]}, "drafter": "pressure_w2", "agent": "idle",
        "trials_per_condition": 1, "base_seed": 3,
        "fixed_dials": {"levers": [*W1_LEVERS, ledger], "sim_dt": 0.005, "sim_steps": 200},
    })
    why = draft_violation(spec)
    assert why is not None and "build_brief:" in why and "task.setup['hidden_ids']" in why


# B ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "root/crux/uptake_fast_in", 3])
def test_a_non_list_surface_is_a_surface_refusal(value, tmp_path):
    spec = _w1({"levers": value})
    why = declared_surface_violation(spec)
    assert why is not None and repr(value) in why
    assert dict(preflight(spec, out_dir=str(tmp_path / "o")).checks)["surface"] is not None


def test_a_non_list_axis_level_is_a_surface_refusal():
    spec = _w1(axes={"levers": [list(W1_LEVERS), None]})
    spec = spec_from_dict({**spec_to_dict(spec), "fixed_dials": {"pi": 0.5}})
    why = declared_surface_violation(spec)
    assert why is not None and "None" in why


def test_an_empty_surface_is_the_do_nothing_arm():
    assert declared_surface_violation(_w1({"levers": []})) is None
