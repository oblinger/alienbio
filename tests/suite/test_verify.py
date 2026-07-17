"""Acceptance tests for the verification / simulation harness (FT05).

A synthetic 2-species, single-compartment world (A -> B, constant mass-action
rate; A large, B zero) is integrated by the REAL simulator directly on the
biology ``Chemistry`` carried by the world (F007 — unified protocol model; the
old ``from_network`` reconstruction bridge is gone).
"""

from __future__ import annotations

import numpy as np
import pytest

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.entity import MockDat
from alienbio.suite.types import (
    Compartment,
    StateVector,
    Topology,
    World,
)
from alienbio.suite.verify import SimConfig, VerifyResult, simulate, verify


CELL = "cell"
A = "A"
B = "B"


def make_world(initial_a: float = 100.0, rate: object = 0.1) -> World:
    """A 2-species single-compartment world: A -> B (constant rate)."""
    mol_a = MoleculeImpl(A, name=A, dat=MockDat(f"mol/{A}"))
    mol_b = MoleculeImpl(B, name=B, dat=MockDat(f"mol/{B}"))
    r1 = ReactionImpl(
        "R1",
        reactants={mol_a: 1.0},
        products={mol_b: 1.0},
        rate=rate,
        dat=MockDat("rxn/R1"),
    )
    network = ChemistryImpl(
        "world",
        molecules={A: mol_a, B: mol_b},
        reactions={"R1": r1},
        dat=MockDat("chem/world"),
    )
    topology = Topology(
        compartments=(Compartment(id=CELL, parent=None, kind="cell", volume=1.0),),
    )
    initial = StateVector(
        data=np.array([[initial_a, 0.0]], dtype=np.float64),
        compartments=(CELL,),
        species=(A, B),
    )
    return World(network=network, topology=topology, initial=initial)


def series(trace, species_id: str) -> list[float]:
    """Concentration of ``species_id`` in the cell across all sampled states."""
    return [st.concentration(CELL, species_id) for st in trace.states]


def _same(t1, t2) -> bool:
    """Value-equality of two timelines (concentrations + times).

    WorldState snapshots are compared by their concentration arrays; the bio
    ``WorldStateImpl`` deliberately carries no value ``__eq__`` (mutable buffer).
    """
    return t1.times == t2.times and all(
        np.array_equal(a.as_array(), b.as_array())
        for a, b in zip(t1.states, t2.states)
    )


# === 1. Qualitative response (robust; no closed-form) ===

def test_qualitative_response():
    trace = simulate(make_world())
    a_series = series(trace, A)
    b_series = series(trace, B)

    # A(t) non-increasing.
    for prev, nxt in zip(a_series, a_series[1:]):
        assert nxt <= prev + 1e-9

    # B(t) non-decreasing.
    for prev, nxt in zip(b_series, b_series[1:]):
        assert nxt >= prev - 1e-9

    # A actually falls and B actually rises (the reaction fires).
    assert a_series[-1] < a_series[0]
    assert b_series[-1] > b_series[0]

    # Total mass A + B conserved within tolerance across all samples.
    totals = [a + b for a, b in zip(a_series, b_series)]
    for tot in totals:
        assert abs(tot - totals[0]) < 1e-6


# === 2. Perturbation contrast (knockout) ===

def test_perturbation_contrast():
    world = make_world()

    def knock_out(w: World) -> World:
        # Perturbed world starts with A = 0, so B can never grow.
        return make_world(initial_a=0.0)

    def predicate(baseline, perturbed) -> bool:
        return series(perturbed, B)[-1] < series(baseline, B)[-1]

    result = verify(world, knock_out, predicate)
    assert isinstance(result, VerifyResult)
    assert result.passed is True
    assert result.discard is False
    # Perturbed B stays ~0.
    assert series(result.perturbed, B)[-1] == pytest.approx(0.0, abs=1e-9)
    # Baseline B grew.
    assert series(result.baseline, B)[-1] > 0.0


# === 3. Reject signal ===

def test_reject_signal():
    world = make_world()

    def identity(w: World) -> World:
        return w

    def failing_predicate(baseline, perturbed) -> bool:
        # Perturbed == baseline here, so "perturbed B < baseline B" is false.
        return series(perturbed, B)[-1] < series(baseline, B)[-1]

    result = verify(world, identity, failing_predicate)
    assert result.passed is False
    assert result.discard is True


# === 4. Determinism ===

def test_determinism():
    world = make_world()
    t1 = simulate(world)
    t2 = simulate(world)
    assert _same(t1, t2)
    assert t1.times == t2.times


# === 5. Callable-rate guard ===

def test_callable_rate_guard():
    world = make_world(rate=lambda state: 0.1)
    with pytest.raises(ValueError, match="callable rate"):
        simulate(world)


# === Extra: config threading (non-default sampling) ===

def test_config_sampling_shape():
    cfg = SimConfig(dt=0.1, steps=50, sample_every=10)
    trace = simulate(make_world(), cfg)
    # steps=50, sample_every=10 -> samples at 0,10,20,30,40 plus final 50 = 6.
    assert len(trace.states) == 6
    assert len(trace.times) == 6
    assert trace.times[0] == 0.0
    assert trace.times[-1] == pytest.approx(50 * 0.1)
