"""Tests for M32.4: the environmental-pressure injection dial.

An opaque NAMED pressure carried with an INTENSITY and a PERSISTENCE, surfaced to
the simulator seam (:func:`alienbio.suite.verify.simulate`) as a **removable**
perturbation. The defining property is removability: once the pressure is lifted,
the reported world state recovers toward the unperturbed trajectory.

The world under test is the same synthetic 2-species single-compartment world
used by :mod:`tests.suite.test_verify` (A -> B, constant mass-action rate).
"""

from __future__ import annotations

import numpy as np
import pytest

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.entity import MockDat
from alienbio.suite.dist import Seed
from alienbio.suite.pressure import (
    INTENSITY_LEVELS,
    NAMED_PRESSURES,
    EnvironmentalPressure,
    make_pressure,
)
from alienbio.suite.types import Compartment, StateVector, Timeline, Topology, World
from alienbio.suite.verify import SimConfig, simulate


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


def _stack(trace: Timeline) -> np.ndarray:
    """[n_samples x n_comp x n_species] array of a timeline's sampled states."""
    return np.array(
        [np.asarray(st.as_array(), dtype=np.float64) for st in trace.states],
        dtype=np.float64,
    )


def _deviation(trace: Timeline, baseline: Timeline) -> np.ndarray:
    """Per-sample L2 deviation of ``trace`` from the unperturbed ``baseline``."""
    diff = _stack(trace) - _stack(baseline)
    return np.sqrt((diff ** 2).sum(axis=(1, 2)))


def _same(t1: Timeline, t2: Timeline) -> bool:
    """Value-equality of two timelines (concentrations + times).

    WorldState snapshots are compared by their concentration arrays rather than
    by object identity — the bio ``WorldStateImpl`` deliberately carries no value
    ``__eq__`` (it is the mutable simulator buffer).
    """
    return t1.times == t2.times and np.array_equal(_stack(t1), _stack(t2))


# === 1. Absent == identity (the #1 guarantee) ===

class TestAbsentIsIdentity:

    def test_pressure_none_is_byte_identical(self):
        world = make_world()
        baseline = simulate(world)
        with_none = simulate(world, pressure=None)
        assert _same(with_none, baseline)
        assert with_none.times == baseline.times
        # Byte-identical arrays, not merely close.
        for a, b in zip(with_none.states, baseline.states):
            assert np.array_equal(a.as_array(), b.as_array())

    def test_zero_intensity_is_identity(self):
        world = make_world()
        baseline = simulate(world)
        zeroed = simulate(world, pressure=make_pressure("suppress", intensity="none"))
        for a, b in zip(zeroed.states, baseline.states):
            assert np.allclose(a.as_array(), b.as_array())


# === 2. Monotone intensity: higher intensity -> larger perturbation ===

class TestMonotoneIntensity:

    def test_deviation_monotone_in_intensity(self):
        world = make_world()
        baseline = simulate(world)
        # Active for the whole run (remove_at=None) so each reaches its plateau.
        levels = ["low", "moderate", "high", "severe"]
        totals = []
        for lvl in levels:
            trace = simulate(world, pressure=make_pressure("suppress", intensity=lvl))
            totals.append(float(_deviation(trace, baseline).sum()))
        # Strictly increasing across the intensity ladder.
        for lo, hi in zip(totals, totals[1:]):
            assert hi > lo

    def test_numeric_intensity_monotone(self):
        world = make_world()
        baseline = simulate(world)
        d1 = _deviation(
            simulate(world, pressure=make_pressure("amplify", intensity=0.3)), baseline
        ).sum()
        d2 = _deviation(
            simulate(world, pressure=make_pressure("amplify", intensity=0.9)), baseline
        ).sum()
        assert d2 > d1


# === 3. Removable -> recovers (the defining property) ===

class TestRemovableRecovers:

    def test_state_recovers_after_removal(self):
        world = make_world()
        cfg = SimConfig(dt=0.1, steps=200, sample_every=10)
        baseline = simulate(world, cfg)
        # Lift the pressure halfway through the run.
        pressure = make_pressure(
            "suppress", intensity="high", persistence="moderate", remove_at=100
        )
        perturbed = simulate(world, cfg, pressure=pressure)

        dev = _deviation(perturbed, baseline)
        peak = float(dev.max())
        final = float(dev[-1])

        # The pressure actually perturbed the world...
        assert peak > 1e-3
        # ...and after removal the state recovers toward the baseline: the final
        # deviation is far smaller than the peak, and essentially zero.
        assert final < peak
        assert final < peak * 1e-3
        assert final == pytest.approx(0.0, abs=1e-6)

    def test_never_removed_stays_perturbed(self):
        world = make_world()
        cfg = SimConfig(dt=0.1, steps=200, sample_every=10)
        baseline = simulate(world, cfg)
        # remove_at=None => pressure active throughout => no recovery at the end.
        pressure = make_pressure(
            "suppress", intensity="high", persistence="moderate", remove_at=None
        )
        perturbed = simulate(world, cfg, pressure=pressure)
        assert float(_deviation(perturbed, baseline)[-1]) > 1e-2


# === 4. Seed determinism (stochastic jitter reuses the framework RNG) ===

class TestSeedDeterminism:

    def test_deterministic_without_jitter(self):
        world = make_world()
        pressure = make_pressure("drain", intensity="moderate")
        # No jitter => two different seeds still produce identical traces.
        t1 = simulate(world, pressure=pressure, seed=Seed(1))
        t2 = simulate(world, pressure=pressure, seed=Seed(999))
        assert _same(t1, t2)

    def test_same_seed_reproducible_with_jitter(self):
        world = make_world()
        pressure = make_pressure("drain", intensity="high", jitter=0.5)
        t1 = simulate(world, pressure=pressure, seed=Seed(7))
        t2 = simulate(world, pressure=pressure, seed=Seed(7))
        assert _same(t1, t2)

    def test_different_seed_differs_with_jitter(self):
        world = make_world()
        pressure = make_pressure("drain", intensity="high", jitter=0.5)
        t1 = simulate(world, pressure=pressure, seed=Seed(7))
        t2 = simulate(world, pressure=pressure, seed=Seed(8))
        assert not _same(t1, t2)


# === 5. Bad input raises (no silent fallback) ===

class TestBadInputRaises:

    def test_unknown_pressure_name_raises(self):
        with pytest.raises(ValueError, match="unknown environmental pressure"):
            make_pressure("not_a_pressure")

    def test_unknown_intensity_level_raises(self):
        with pytest.raises(ValueError, match="unknown intensity level"):
            make_pressure("suppress", intensity="ludicrous")

    def test_unknown_persistence_level_raises(self):
        with pytest.raises(ValueError, match="unknown persistence level"):
            make_pressure("suppress", persistence="forever")

    def test_negative_intensity_raises(self):
        with pytest.raises(ValueError, match="intensity must be"):
            make_pressure("suppress", intensity=-1.0)

    def test_persistence_out_of_range_raises(self):
        with pytest.raises(ValueError, match="persistence must be"):
            make_pressure("suppress", persistence=1.0)

    def test_negative_remove_at_raises(self):
        with pytest.raises(ValueError, match="remove_at must be"):
            make_pressure("suppress", remove_at=-5)

    def test_negative_jitter_raises(self):
        with pytest.raises(ValueError, match="jitter must be"):
            make_pressure("suppress", jitter=-0.1)


# === 6. Overlay mechanics (build-up + decay, domain-neutral) ===

class TestOverlayMechanics:

    def test_overlay_builds_and_decays(self):
        # Active [0,50), removed after => p climbs then relaxes to ~0.
        pressure = make_pressure(
            "amplify", intensity="high", persistence="moderate", remove_at=50
        )
        p = pressure.overlay(steps=200)
        assert p[49] > p[0]                     # built up while active
        assert p[-1] == pytest.approx(0.0, abs=1e-6)  # recovered after removal
        assert p[49] > p[-1]

    def test_overlay_plateau_approaches_intensity(self):
        pressure = make_pressure(
            "amplify", intensity=1.0, persistence="moderate", remove_at=None
        )
        p = pressure.overlay(steps=300)
        assert p[-1] == pytest.approx(1.0, abs=1e-3)

    def test_registries_are_opaque_and_populated(self):
        assert "suppress" in NAMED_PRESSURES
        assert INTENSITY_LEVELS["none"] == 0.0
        assert isinstance(make_pressure("shock"), EnvironmentalPressure)
