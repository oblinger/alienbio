"""F007 Phase 0 — characterization / golden tests at the biology<->neutral boundary.

These lock the *current* behavior of the seam that F007 will replace (the
``adapters.py`` copy-functions + the ``verify`` bridge that consumes them), so
the protocol-ization refactor can be shown to be behavior-preserving.

Unlike the property/acceptance tests in ``test_adapters.py`` (which use hand-built,
atom-free neutral fixtures and check round-trip *shape*), these use a **real**
``ChemistryImpl`` with atoms — so ``symbol``/``molecular_weight`` are non-trivial —
and pin the **exact values** the engines see through the boundary today. When
F007 makes the biology classes implement the neutral ``Protocol``s directly, the
Protocol view must reproduce the `to_network(...)` golden below unchanged; the
`from_network` lossy-delta test documents precisely what the refactor is expected
to fix (and will therefore need updating when it does).

Golden values were captured by executing the real code, never hand-computed.
"""

from __future__ import annotations

import numpy as np

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import AtomImpl, MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.entity import MockDat
from alienbio.suite.adapters import from_network, to_network
from alienbio.suite.dist import Seed
from alienbio.suite.types import (
    Compartment,
    Reaction,
    ReactionNetwork,
    Species,
    StateVector,
    Topology,
    World,
)
from alienbio.suite.verify import SimConfig, simulate


def _build_real_chem() -> ChemistryImpl:
    """A real Chemistry with atoms: glucose (C6H12O6) -> 2 water (H2O), rate 0.3.

    Uses real ``AtomImpl`` composition so ``symbol``/``molecular_weight`` are
    derived (non-empty), exercising the tags the neutral view carries.
    """
    c = AtomImpl("C", "Carbon", 12.011)
    h = AtomImpl("H", "Hydrogen", 1.008)
    o = AtomImpl("O", "Oxygen", 15.999)
    glucose = MoleculeImpl(
        "glucose", dat=MockDat("mol/glucose"),
        atoms={c: 6, h: 12, o: 6}, name="Glucose", bdepth=2,
    )
    water = MoleculeImpl(
        "water", dat=MockDat("mol/water"),
        atoms={h: 2, o: 1}, name="Water", bdepth=0,
    )
    rxn = ReactionImpl(
        "r1", reactants={glucose: 1}, products={water: 2},
        rate=0.3, dat=MockDat("rxn/r1"),
    )
    return ChemistryImpl(
        "cell", molecules={"glucose": glucose, "water": water},
        reactions={"r1": rxn}, dat=MockDat("chem/cell"),
    )


# ── Boundary golden: what the engines see through to_network() TODAY ──────────

def test_to_network_real_chemistry_golden():
    """`to_network` on a real Chemistry produces this exact neutral network.

    F007 invariant: after protocol-ization the biology classes must expose the
    SAME view. Species are keyed by ``mol.name``; ``symbol``/``molecular_weight``
    (atom-derived) ARE carried into the neutral tags on this forward direction.
    """
    net = to_network(_build_real_chem())

    assert set(net.species.keys()) == {"Glucose", "Water"}
    assert dict(net.species["Glucose"].attrs) == {
        "name": "Glucose",
        "symbol": "C6H12O6",
        "bdepth": 2,
        "molecular_weight": 180.156,
    }
    assert dict(net.species["Water"].attrs) == {
        "name": "Water",
        "symbol": "H2O",
        "bdepth": 0,
        "molecular_weight": 18.015,
    }

    assert set(net.reactions.keys()) == {"r1"}
    r1 = net.reactions["r1"]
    assert r1.reactants == (("Glucose", 1),)
    assert r1.products == (("Water", 2),)
    assert r1.modifiers == ()
    assert r1.rate == 0.3


def test_from_network_lossy_delta_is_characterized():
    """Characterizes the CURRENT reverse-direction loss that F007 will fix.

    ``from_network`` reconstructs atom-free molecules, so ``symbol`` and
    ``molecular_weight`` are lost (``bdepth``/``name`` survive). This is the
    single-source-of-truth violation F007 removes — pinned here so the change is
    visible and intentional (this test is EXPECTED to change under F007 Phase 2).
    """
    rebuilt = from_network(to_network(_build_real_chem()))

    glucose = rebuilt.molecules["Glucose"]
    assert glucose.symbol == ""            # lost (atom-derived)
    assert glucose.molecular_weight == 0.0  # lost (atom-derived)
    assert glucose.bdepth == 2              # preserved
    assert glucose.name == "Glucose"        # preserved

    water = rebuilt.molecules["Water"]
    assert water.symbol == ""
    assert water.molecular_weight == 0.0
    assert water.bdepth == 0
    assert water.name == "Water"


# ── Engine golden: simulate() through the from_network + real-physics bridge ──

def _build_world() -> World:
    """Fixed 1-compartment world: S1 -> S2, constant mass-action rate 0.5, S1(0)=10."""
    net = ReactionNetwork(
        species={"S1": Species("S1", {}), "S2": Species("S2", {})},
        reactions={
            "R1": Reaction(
                "R1", reactants=(("S1", 1),), products=(("S2", 1),),
                modifiers=(), rate=0.5,
            )
        },
    )
    topo = Topology((Compartment("c0", None, "cell", 1.0),))
    initial = StateVector(
        data=np.array([[10.0, 0.0]], dtype=np.float64),
        compartments=("c0",), species=("S1", "S2"),
    )
    return World(network=net, topology=topo, initial=initial)


# Golden captured from the real Euler integrator (dt=0.1, 20 steps, sample every 5).
_SIM_TIMES = (0.0, 0.5, 1.0, 1.5, 2.0)
_SIM_DATA = [
    [10.0, 0.0],
    [7.737809, 2.262191],
    [5.987369, 4.012631],
    [4.632912, 5.367088],
    [3.584859, 6.415141],
]


def test_simulate_world_golden():
    """`simulate` reproduces this exact trajectory (real physics via from_network).

    F007 invariant: the refactored boundary must yield the identical trace — this
    pins the real-integrator output that flows through the adapter bridge.
    """
    trace = simulate(_build_world(), SimConfig(dt=0.1, steps=20, sample_every=5), seed=Seed(0))

    assert trace.times == _SIM_TIMES
    assert len(trace.states) == len(_SIM_DATA)
    for sv, expected in zip(trace.states, _SIM_DATA):
        assert sv.compartments == ("c0",)
        assert sv.species == ("S1", "S2")
        np.testing.assert_allclose(sv.data, np.array([expected]), rtol=0, atol=1e-6)


def test_simulate_is_deterministic():
    """Identical (world, cfg) yields an identical trace — refactor must preserve this."""
    world, cfg = _build_world(), SimConfig(dt=0.1, steps=20, sample_every=5)
    a = simulate(world, cfg, seed=Seed(0))
    b = simulate(world, cfg, seed=Seed(0))
    assert a.times == b.times
    assert all(np.array_equal(x.data, y.data) for x, y in zip(a.states, b.states))


def test_simulate_conserves_mass():
    """S1 + S2 stays at the initial total (10.0) at every sampled state.

    A C1-hardening invariant, locked at the boundary so the refactor can't
    silently perturb conservation.
    """
    trace = simulate(_build_world(), SimConfig(dt=0.1, steps=20, sample_every=5), seed=Seed(0))
    for sv in trace.states:
        total = float(sv.data.sum())
        assert abs(total - 10.0) < 1e-6
