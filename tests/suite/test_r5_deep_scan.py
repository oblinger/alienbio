"""Deep scan round 5 (Tink, 2026-10-27): holes in round 4's fixes and the
T066 batches.

Each test is one stated break, red before its fix:

1. ``certainty_slice_problem`` applied round 4's slice-grid rule at
   ``windows=1``, which every certainty arm carries and which runs the turn
   whole on the untouched path — so ``sim_steps=25`` (``sample_every`` 10) on
   a certainty world refused inside every trial.
2. The manifest's ``model`` read ``spec.agent`` alone, so an ``agent`` axis
   ``[idle, llm]`` on a scripted spec ran llm cells on PINNED_MODEL under a
   header saying ``model: null``.
3. ``expected_turns`` is persisted as its derived value, so widening a
   ``max_turns`` axis — a legitimate resume edit — read as drift.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from alienbio.suite.experiment import run_experiment, spec_from_dict, spec_to_dict
from alienbio.suite.guards import _resume_spec_drift
from alienbio.suite.llm_agent import PINNED_MODEL
from alienbio.suite.runner import certainty_slice_problem
from alienbio.suite.store import _build_manifest

W1_LEVERS = ["root/uptake_fast_in", "root/uptake_clean_in"]


def _d(**over):
    d = {
        "name": "r5", "axes": {"pi": [0.5]}, "drafter": "pressure", "agent": "idle",
        "trials_per_condition": 1, "base_seed": 1,
        "fixed_dials": {"levers": list(W1_LEVERS), "max_turns": 2, "sim_steps": 20},
        "drafter_kwargs": {},
    }
    d.update(over)
    return d


def test_one_certainty_window_has_no_slice_grid():
    assert certainty_slice_problem(25, 1, 10) is None
    # The multi-window rule still holds.
    assert certainty_slice_problem(200, 8, 10) is not None


def test_certainty_arm_off_the_sample_grid_runs():
    out = tempfile.mkdtemp()
    fixed = {"levers": list(W1_LEVERS), "max_turns": 2, "sim_steps": 25, "certainty": 0.6}
    run_experiment(spec_from_dict(_d(fixed_dials=fixed)), out_dir=out)
    lines = [json.loads(line) for line in Path(out, "records.jsonl").read_text().splitlines()]
    assert [d["error"] for d in lines] == [""]


def test_manifest_names_the_model_an_agent_axis_runs():
    spec = spec_from_dict(_d(axes={"pi": [0.5], "agent": ["idle", "llm"]}, temperature=0.0))
    assert _build_manifest(spec, 2, "t")["model"] == PINNED_MODEL
    # A scripted-only run still names none.
    assert _build_manifest(spec_from_dict(_d()), 1, "t")["model"] is None


def test_resume_admits_a_widened_max_turns_axis():
    no_levers = {"levers": []}
    before = spec_from_dict(_d(axes={"pi": [0.5], "max_turns": [2, 3]}, fixed_dials=no_levers))
    after = spec_from_dict(_d(axes={"pi": [0.5], "max_turns": [2, 3, 4]}, fixed_dials=no_levers))
    assert _resume_spec_drift(spec_to_dict(before), after) == []
    # An explicit expected_turns edit is still drift.
    edited = spec_from_dict(
        _d(axes={"pi": [0.5], "max_turns": [2, 3]}, fixed_dials=no_levers, expected_turns=9)
    )
    assert _resume_spec_drift(spec_to_dict(before), edited) == ["expected_turns"]
