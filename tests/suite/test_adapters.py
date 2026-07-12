"""Acceptance tests for the bio<->neutral adapters (neutral-level round-trips)."""

from __future__ import annotations

import numpy as np

from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.suite.adapters import from_network, from_state, to_network, to_state
from alienbio.suite.types import Reaction, ReactionNetwork, Species, StateVector


def build_net() -> tuple[ReactionNetwork, object]:
    """A hand-built neutral network whose tags reflect atom-free molecules.

    ``symbol``/``molecular_weight`` are atom-derived and cannot survive
    reconstruction, so the fixture uses the atom-free values (``""`` / ``0.0``).
    """
    rate_obj = lambda state: 0.1  # noqa: E731  (opaque, unique object for identity)

    def attrs(name: str, bdepth: int) -> dict:
        return {
            "name": name,
            "symbol": "",
            "bdepth": bdepth,
            "molecular_weight": 0.0,
        }

    species = {
        "S1": Species("S1", attrs("S1", 0)),
        "S2": Species("S2", attrs("S2", 1)),
    }
    reactions = {
        "R1": Reaction(
            "R1",
            reactants=(("S1", 1),),
            products=(("S2", 1),),
            modifiers=(),
            rate=rate_obj,
        ),
    }
    return ReactionNetwork(species=species, reactions=reactions), rate_obj


def test_network_round_trip():
    net, _ = build_net()
    assert to_network(from_network(net)) == net


def test_rate_identity_preserved():
    net, rate_obj = build_net()
    rebuilt = to_network(from_network(net))
    assert rebuilt.reactions["R1"].rate is rate_obj


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
