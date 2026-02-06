"""Tests for Quiescence Detection."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    MoleculeImpl,
    QuiescenceTimeout,
    ReactionImpl,
    StateImpl,
    run_until_quiet,
)


class MockDat:
    def __init__(self, path: str):
        self._path = path
    def get_path_name(self) -> str:
        return self._path
    def get_path(self) -> str:
        return f"/tmp/{self._path}"
    def save(self) -> None:
        pass


def _make_homeostatic_system() -> BioSystem:
    """System that converges to A=10.0."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))

    source = ReactionImpl(
        "source", reactants={}, products={a: 1.0},
        rate=1.0, dat=MockDat("rxn/source"),
    )
    degrade = ReactionImpl(
        "degrade", reactants={a: 1.0}, products={},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/degrade"),
    )
    chem = ChemistryImpl(
        "test", atoms={"C": carbon},
        molecules={"A": a, "B": b},
        reactions={"source": source, "degrade": degrade},
        dat=MockDat("chem/test"),
    )
    state = StateImpl(chem, initial={"A": 1.0, "B": 0.0})
    return BioSystem(chem, state, dt=0.1)


class TestRunUntilQuiet:

    def test_reaches_quiescence(self):
        """Homeostatic system should reach quiescence."""
        system = _make_homeostatic_system()
        steps = run_until_quiet(
            system,
            measure="all_concentrations",
            delta=0.01,
            span=20,
            timeout=5000,
        )
        assert steps > 0
        assert steps < 5000

    def test_returns_step_count(self):
        system = _make_homeostatic_system()
        steps = run_until_quiet(system, delta=0.01, span=20, timeout=5000)
        assert isinstance(steps, int)

    def test_system_is_stable_after(self):
        """After quiescence, concentrations should be near steady state."""
        system = _make_homeostatic_system()
        run_until_quiet(system, delta=0.001, span=50, timeout=10000)
        # A should be near 10.0 (source_rate / degrade_constant = 1.0 / 0.1)
        assert system.state["A"] == pytest.approx(10.0, abs=1.0)

    def test_timeout_raises(self):
        """Very tight delta with short timeout should raise."""
        system = _make_homeostatic_system()
        with pytest.raises(QuiescenceTimeout):
            run_until_quiet(
                system,
                delta=1e-20,  # impossibly tight
                span=50,
                timeout=100,
            )

    def test_single_molecule_measure(self):
        """Can use concentration measurement for single molecule."""
        system = _make_homeostatic_system()
        steps = run_until_quiet(
            system,
            measure="concentration",
            measure_params={"molecule": "A"},
            delta=0.01,
            span=20,
            timeout=5000,
        )
        assert steps > 0

    def test_already_stable_system(self):
        """System starting at steady state should quiesce quickly."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        # No reactions — already stable
        chem = ChemistryImpl(
            "test", atoms={"C": carbon},
            molecules={"A": a}, reactions={},
            dat=MockDat("chem/test"),
        )
        state = StateImpl(chem, initial={"A": 5.0})
        system = BioSystem(chem, state, dt=0.1)

        steps = run_until_quiet(system, delta=0.01, span=10, timeout=100)
        # Should be exactly span steps (10) since change is always 0
        assert steps == 10
