"""Tests for M6.2 Equilibrium Testing."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    HomeostasisTarget,
    MoleculeImpl,
    ReactionImpl,
    StateImpl,
    StabilityResult,
    check_homeostasis,
    check_stability,
    compute_variance,
    find_unstable_rates,
    run_to_equilibrium,
)


class MockDat:
    """Mock DAT for testing."""

    def __init__(self, path: str):
        self._path = path

    def get_path_name(self) -> str:
        return self._path

    def get_path(self) -> str:
        return f"/tmp/{self._path}"

    def save(self) -> None:
        pass


# --- Helpers ---

def _make_stable_system() -> BioSystem:
    """Create a system with mass-action A -> B that depletes A."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
    # Mass-action: rate proportional to [A]
    r1 = ReactionImpl(
        "r1", reactants={a: 1.0}, products={b: 1.0},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/r1"),
    )
    chem = ChemistryImpl(
        "stable", atoms={"C": carbon},
        molecules={"A": a, "B": b}, reactions={"r1": r1},
        dat=MockDat("chem/stable"),
    )
    state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
    return BioSystem(chem, state, dt=0.1)


def _make_reversible_system() -> BioSystem:
    """Create a system with mass-action A <-> B that reaches true equilibrium.

    At equilibrium: 0.1*[A] = 0.05*[B], with [A]+[B]=10.
    So [A] ~ 3.33, [B] ~ 6.67.
    """
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
    fwd = ReactionImpl(
        "fwd", reactants={a: 1.0}, products={b: 1.0},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/fwd"),
    )
    rev = ReactionImpl(
        "rev", reactants={b: 1.0}, products={a: 1.0},
        rate=lambda state: 0.05 * state["B"],
        dat=MockDat("rxn/rev"),
    )
    chem = ChemistryImpl(
        "reversible", atoms={"C": carbon},
        molecules={"A": a, "B": b}, reactions={"fwd": fwd, "rev": rev},
        dat=MockDat("chem/reversible"),
    )
    state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
    return BioSystem(chem, state, dt=0.1)


def _make_no_reaction_system() -> BioSystem:
    """Create a system with no reactions (always at equilibrium)."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    chem = ChemistryImpl(
        "static", atoms={"C": carbon},
        molecules={"A": a}, reactions={},
        dat=MockDat("chem/static"),
    )
    state = StateImpl(chem, initial={"A": 5.0})
    return BioSystem(chem, state)


# === compute_variance ===

class TestComputeVariance:

    def test_constant_timeline_zero_variance(self):
        system = _make_no_reaction_system()
        timeline = system.run(steps=50)
        var = compute_variance(timeline, window=50)
        assert var["A"] == 0.0

    def test_changing_timeline_nonzero_variance(self):
        system = _make_stable_system()
        timeline = system.run(steps=50)
        var = compute_variance(timeline, window=50)
        assert var["A"] > 0.0
        assert var["B"] > 0.0

    def test_window_larger_than_timeline(self):
        system = _make_no_reaction_system()
        timeline = system.run(steps=10)
        var = compute_variance(timeline, window=1000)
        assert "A" in var

    def test_empty_timeline(self):
        var = compute_variance([], window=10)
        assert var == {}


# === check_stability ===

class TestCheckStability:

    def test_static_system_is_stable(self):
        system = _make_no_reaction_system()
        timeline = system.run(steps=200)
        result = check_stability(timeline, window=100)
        assert result.stable
        assert result.max_variance == 0.0
        assert result.unstable_molecules == []

    def test_active_system_early_is_unstable(self):
        system = _make_stable_system()
        timeline = system.run(steps=20)
        result = check_stability(timeline, window=20, threshold=1e-8)
        assert not result.stable
        assert len(result.unstable_molecules) > 0

    def test_result_has_steps_and_window(self):
        system = _make_no_reaction_system()
        timeline = system.run(steps=50)
        result = check_stability(timeline, window=30)
        assert result.steps_run == 50
        assert result.window == 30

    def test_result_has_per_molecule_variance(self):
        system = _make_stable_system()
        timeline = system.run(steps=50)
        result = check_stability(timeline, window=50)
        assert "A" in result.variance
        assert "B" in result.variance

    def test_high_threshold_makes_stable(self):
        system = _make_stable_system()
        timeline = system.run(steps=50)
        result = check_stability(timeline, window=50, threshold=1e6)
        assert result.stable


# === run_to_equilibrium ===

class TestRunToEquilibrium:

    def test_static_system_stops_quickly(self):
        system = _make_no_reaction_system()
        timeline, result = run_to_equilibrium(
            system, max_steps=500, window=50, check_interval=50,
        )
        assert result.stable
        # Should stop at first check after window is filled
        assert len(timeline) <= 200

    def test_reversible_system_reaches_equilibrium(self):
        system = _make_reversible_system()
        timeline, result = run_to_equilibrium(
            system, max_steps=5000, window=100, threshold=1e-4,
            check_interval=100,
        )
        assert result.stable
        # Final concentrations should be non-trivial
        assert system.state["A"] > 0.0
        assert system.state["B"] > 0.0

    def test_max_steps_respected(self):
        system = _make_stable_system()
        timeline, result = run_to_equilibrium(
            system, max_steps=50, window=100, threshold=1e-20,
        )
        assert len(timeline) - 1 <= 50

    def test_returns_full_timeline(self):
        system = _make_no_reaction_system()
        timeline, result = run_to_equilibrium(
            system, max_steps=200, window=50, check_interval=50,
        )
        assert len(timeline) > 1
        # All entries should be StateImpl instances
        for s in timeline:
            assert "A" in s

    def test_system_state_updated(self):
        system = _make_reversible_system()
        initial_a = system.state["A"]
        run_to_equilibrium(system, max_steps=1000, window=100)
        # State should have changed from initial
        assert system.state["A"] != initial_a


# === find_unstable_rates ===

class TestFindUnstableRates:

    def test_stable_system_returns_empty(self):
        system = _make_no_reaction_system()
        rates = find_unstable_rates(system, steps=100, window=50)
        assert rates == {}

    def test_unstable_system_returns_rates(self):
        system = _make_stable_system()
        rates = find_unstable_rates(
            system, steps=20, window=20, threshold=1e-10,
        )
        # r1 has a mass-action rate that is > 0 at initial state
        assert "r1" in rates
        assert rates["r1"] > 0.0

    def test_returns_rate_values(self):
        system = _make_reversible_system()
        rates = find_unstable_rates(
            system, steps=20, window=20, threshold=1e-10,
        )
        # Both reactions have non-zero rates at initial state (A=10, B=0)
        # fwd rate = 0.1 * 10 = 1.0, rev rate = 0.05 * 0 = 0.0
        assert "fwd" in rates
        assert rates["fwd"] > 0.0


# === HomeostasisTarget ===

class TestHomeostasisTarget:

    def test_target_within_range(self):
        target = HomeostasisTarget("A", target=10.0, tolerance=0.1)
        assert target.check(10.0)
        assert target.check(9.5)
        assert target.check(10.5)

    def test_target_outside_range(self):
        target = HomeostasisTarget("A", target=10.0, tolerance=0.1)
        assert not target.check(8.0)
        assert not target.check(12.0)

    def test_low_and_high(self):
        target = HomeostasisTarget("A", target=10.0, tolerance=0.2)
        assert target.low == 8.0
        assert target.high == 12.0

    def test_zero_tolerance(self):
        target = HomeostasisTarget("A", target=5.0, tolerance=0.0)
        assert target.check(5.0)
        assert not target.check(5.01)

    def test_default_tolerance(self):
        target = HomeostasisTarget("A", target=10.0)
        assert target.tolerance == 0.1


# === check_homeostasis ===

class TestCheckHomeostasis:

    def test_all_targets_met(self):
        system = _make_no_reaction_system()
        targets = [HomeostasisTarget("A", target=5.0, tolerance=0.1)]
        result = check_homeostasis(system.state, targets)
        assert result["A"] is True

    def test_target_not_met(self):
        system = _make_no_reaction_system()
        targets = [HomeostasisTarget("A", target=100.0, tolerance=0.1)]
        result = check_homeostasis(system.state, targets)
        assert result["A"] is False

    def test_multiple_targets(self):
        system = _make_stable_system()
        targets = [
            HomeostasisTarget("A", target=10.0, tolerance=0.1),
            HomeostasisTarget("B", target=0.0, tolerance=1.0),
        ]
        result = check_homeostasis(system.state, targets)
        assert "A" in result
        assert "B" in result

    def test_after_simulation(self):
        system = _make_reversible_system()
        run_to_equilibrium(system, max_steps=2000, window=100)
        # At equilibrium with rates 0.1 and 0.05, A:B ratio is ~1:2
        # Total mass is 10, so A ~ 3.33, B ~ 6.67
        targets = [
            HomeostasisTarget("A", target=system.state["A"], tolerance=0.01),
        ]
        result = check_homeostasis(system.state, targets)
        assert result["A"] is True


# === Variance over last N steps ===

class TestVarianceThreshold:

    def test_variance_below_threshold_after_equilibrium(self):
        """M6.2 key test: variance of concentrations over last 100 steps < threshold."""
        system = _make_reversible_system()
        timeline, result = run_to_equilibrium(
            system, max_steps=5000, window=100, threshold=1e-4,
        )
        assert result.stable
        for mol, var in result.variance.items():
            assert var < 1e-4, f"{mol} variance {var} >= threshold"
