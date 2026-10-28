"""Findings from the ``ABIO Store`` module doc (T084): the run store's
robustness defects, each pinned red-then-green.

A — a non-finite float anywhere on a record line wrote a bare ``NaN`` /
``Infinity`` token that strict JSON readers refuse.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from alienbio.suite.experiment import ExperimentSpec, record_from_json, record_to_json, run_experiment
from alienbio.suite.info_seeking import ActionRecord
from alienbio.suite.store import _canonical_json


def _spec(name: str, trials_per_condition: int = 1, **overrides) -> ExperimentSpec:
    kwargs = dict(
        name=name,
        axes=(("rung", ("single", "forced")),),
        drafter="conflict",
        agent="idle",
        trials_per_condition=trials_per_condition,
        base_seed=42,
        fixed_dials={"levers": []},
    )
    kwargs.update(overrides)
    return ExperimentSpec(**kwargs)


def _strict_loads(line: str):
    def refuse(token: str):
        raise ValueError(f"non-strict JSON token {token!r}")

    return json.loads(line, parse_constant=refuse)


# ── A. non-finite floats ────────────────────────────────────────────────────


def test_non_finite_floats_round_trip_as_strict_json(tmp_path):
    rmap = run_experiment(_spec("nonfinite"), out_dir=str(tmp_path / "run"))
    record = dataclasses.replace(
        rmap.records[0],
        final_state={"root": {"m1": float("nan"), "m2": float("inf"), "m3": 1.5}},
        action_log=(
            ActionRecord(
                kind="intervene", destructive=False, accepted=True, reason="", target="m1",
                value=float("-inf"), delta=float("nan"),
            ),
        ),
        objective_score=float("nan"),
        oracle={"v_target": float("inf"), "nested": [float("-inf"), 2.0]},
    )
    line = _canonical_json(record_to_json(record, "rung=single", 0))
    d = _strict_loads(line)  # strict readers accept the line
    rebuilt = record_from_json(d)

    assert math.isnan(rebuilt.final_state["root"]["m1"])
    assert rebuilt.final_state["root"]["m2"] == float("inf")
    assert rebuilt.final_state["root"]["m3"] == 1.5
    assert rebuilt.action_log[0].value == float("-inf")
    assert math.isnan(rebuilt.action_log[0].delta)
    assert math.isnan(rebuilt.objective_score)
    assert rebuilt.oracle["v_target"] == float("inf")
    assert rebuilt.oracle["nested"] == [float("-inf"), 2.0]


def test_canonical_json_refuses_a_stray_non_finite_float():
    class Wrapper(float):
        pass

    # A finite tree is byte-identical to the plain dump.
    payload = {"b": [1.0, 2], "a": {"x": "inf-not-a-float"}}
    assert _canonical_json(payload) == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    # The encoder spells a float subclass too; nothing reaches the dump bare.
    assert _strict_loads(_canonical_json({"v": Wrapper("nan")})) == {"v": "nan"}


def test_run_store_lines_are_strict_json(tmp_path):
    out = tmp_path / "run"
    run_experiment(_spec("strict"), out_dir=str(out))
    for line in (out / "records.jsonl").read_text().splitlines():
        _strict_loads(line)
