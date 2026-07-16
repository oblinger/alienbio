"""Acceptance tests for the bio<->neutral state adapters (neutral-level round-trips)."""

from __future__ import annotations

import numpy as np

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.suite.adapters import from_state, to_state
from alienbio.suite.types import StateVector


def test_state_round_trip():
    tree = CompartmentTreeImpl()
    root = tree.add_root("organism")
    tree.add_child(root, "cell")  # 2 compartments total

    data = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float64)
    sv = StateVector(
        data=data,
        compartments=("c0", "c1"),
        species=("s0", "s1", "s2"),
    )
    round_tripped = to_state(from_state(sv, tree))
    assert round_tripped == sv


def test_state_round_trip_reports_value_equality_not_identity():
    tree = CompartmentTreeImpl()
    tree.add_root("only")  # 1 compartment

    sv = StateVector(
        data=np.array([[7.0, 8.0]], dtype=np.float64),
        compartments=("c0",),
        species=("s0", "s1"),
    )
    out = to_state(from_state(sv, tree))
    assert out is not sv
    assert out == sv
