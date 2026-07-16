"""F007 Phase 0 — characterization / golden tests at the biology<->neutral boundary.

These lock the *current* behavior of the seam F007 replaced (the biology classes
now ARE the unified protocol model; the neutral ``ReactionNetwork`` shadow and
its ``adapters.py`` copy-functions ``to_network``/``from_network`` are gone), so
the protocol-ization refactor can be shown to be behavior-preserving.

The boundary golden below pins the **exact values** engines see straight off a
**real** ``ChemistryImpl`` with atoms — so ``symbol``/``molecular_weight`` are
non-trivial — read directly from ``chem.molecules`` / ``chem.reactions`` (no
neutral conversion step exists anymore; there is nothing to lose).

Golden values were captured by executing the real code, never hand-computed.
"""

from __future__ import annotations

import numpy as np

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import AtomImpl, MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.entity import MockDat
from alienbio.suite.dist import Seed
from alienbio.suite.types import (
    Compartment,
    StateVector,
    Topology,
    World,
)
from alienbio.suite.verify import SimConfig, simulate


def _build_real_chem() -> ChemistryImpl:
    """A real Chemistry with atoms: glucose (C6H12O6) -> 2 water (H2O), rate 0.3.

    Uses real ``AtomImpl`` composition so ``symbol``/``molecular_weight`` are
    derived (non-empty).
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


# ── Boundary golden: what the engines see straight off ChemistryImpl TODAY ────

def test_chemistry_molecule_and_reaction_fields_golden():
    """A real Chemistry's molecule/reaction fields carry this exact golden data.

    F007 invariant: the biology classes ARE the unified protocol model — no
    neutral conversion happens anymore, so these fields are read directly off
    ``ChemistryImpl``. ``symbol``/``molecular_weight`` are atom-derived and
    non-trivial here (this pins the same golden values the retired
    ``to_network`` forward-direction conversion used to expose).
    """
    chem = _build_real_chem()

    assert set(chem.molecules.keys()) == {"glucose", "water"}
    glucose = chem.molecules["glucose"]
    assert glucose.name == "Glucose"
    assert glucose.symbol == "C6H12O6"
    assert glucose.bdepth == 2
    assert glucose.molecular_weight == 180.156

    water = chem.molecules["water"]
    assert water.name == "Water"
    assert water.symbol == "H2O"
    assert water.bdepth == 0
    assert water.molecular_weight == 18.015

    assert set(chem.reactions.keys()) == {"r1"}
    r1 = chem.reactions["r1"]
    assert {mol.name: coeff for mol, coeff in r1.reactants.items()} == {"Glucose": 1}
    assert {mol.name: coeff for mol, coeff in r1.products.items()} == {"Water": 2}
    assert r1.rate == 0.3


# ── Engine golden: simulate() over the world's concrete Chemistry (real physics) ──

def _build_world() -> World:
    """Fixed 1-compartment world: S1 -> S2, constant mass-action rate 0.5, S1(0)=10.

    F007: the world now carries a concrete biology ``Chemistry`` directly (unified
    protocol model); the neutral ``ReactionNetwork`` + ``from_network`` bridge is
    gone.  The physics is unchanged, so the golden trajectory below is identical —
    which is exactly what proves the retarget is behavior-preserving.
    """
    s1 = MoleculeImpl("S1", name="S1", dat=MockDat("mol/S1"))
    s2 = MoleculeImpl("S2", name="S2", dat=MockDat("mol/S2"))
    r1 = ReactionImpl(
        "R1", reactants={s1: 1.0}, products={s2: 1.0},
        rate=0.5, dat=MockDat("rxn/R1"),
    )
    net = ChemistryImpl(
        "cell", molecules={"S1": s1, "S2": s2},
        reactions={"R1": r1}, dat=MockDat("chem/world"),
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
    """`simulate` reproduces this exact trajectory (real physics on the Chemistry).

    F007 invariant: the refactored boundary must yield the identical trace — this
    pins the real-integrator output, now read straight off the world's Chemistry.
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
