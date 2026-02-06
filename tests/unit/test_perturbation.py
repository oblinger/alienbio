"""Tests for M6.3 Perturbation Testing."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    DriftResult,
    MoleculeImpl,
    PerturbationResult,
    ReactionImpl,
    StateImpl,
    inject_spike,
    measure_intervention_response,
    remove_reaction_drift,
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

def _make_homeostatic_system() -> BioSystem:
    """Create an open system with source + degradation that recovers from spikes.

    Source: produces A at constant rate 1.0
    Degradation: removes A proportional to [A] (rate 0.1*[A])
    Steady state: [A] = 10.0
    """
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    source = ReactionImpl(
        "source", reactants={}, products={a: 1.0},
        rate=1.0,
        dat=MockDat("rxn/source"),
    )
    degrade = ReactionImpl(
        "degrade", reactants={a: 1.0}, products={},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/degrade"),
    )
    chem = ChemistryImpl(
        "homeostatic", atoms={"C": carbon},
        molecules={"A": a},
        reactions={"source": source, "degrade": degrade},
        dat=MockDat("chem/homeostatic"),
    )
    state = StateImpl(chem, initial={"A": 10.0})
    return BioSystem(chem, state, dt=0.1)


def _make_chain_system() -> BioSystem:
    """Create mass-action chain A -> B -> C."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
    c = MoleculeImpl("C_mol", atoms={carbon: 3}, bdepth=0, dat=MockDat("mol/C"))
    r1 = ReactionImpl(
        "r1", reactants={a: 1.0}, products={b: 1.0},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/r1"),
    )
    r2 = ReactionImpl(
        "r2", reactants={b: 1.0}, products={c: 1.0},
        rate=lambda state: 0.05 * state["B"],
        dat=MockDat("rxn/r2"),
    )
    chem = ChemistryImpl(
        "chain", atoms={"C": carbon},
        molecules={"A": a, "B": b, "C_mol": c},
        reactions={"r1": r1, "r2": r2},
        dat=MockDat("chem/chain"),
    )
    state = StateImpl(chem, initial={"A": 10.0, "B": 0.0, "C_mol": 0.0})
    return BioSystem(chem, state, dt=0.1)


def _make_static_system() -> BioSystem:
    """No reactions — concentrations never change."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    chem = ChemistryImpl(
        "static", atoms={"C": carbon},
        molecules={"A": a}, reactions={},
        dat=MockDat("chem/static"),
    )
    state = StateImpl(chem, initial={"A": 5.0})
    return BioSystem(chem, state)


# === inject_spike ===

class TestInjectSpike:

    def test_homeostatic_system_recovers_from_spike(self):
        """M6.3 key test: spike recovery within N steps."""
        system = _make_homeostatic_system()
        result = inject_spike(
            system, molecule="A", amount=5.0,
            recovery_steps=500, tolerance=0.15,
        )
        assert isinstance(result, PerturbationResult)
        assert result.recovered

    def test_spike_increases_deviation(self):
        system = _make_homeostatic_system()
        result = inject_spike(
            system, molecule="A", amount=10.0,
            recovery_steps=10, tolerance=0.01,
        )
        # After only 10 steps, system hasn't fully recovered
        assert result.max_deviation > 0.0

    def test_static_system_does_not_recover(self):
        """Static system has no reactions to drive recovery."""
        system = _make_static_system()
        result = inject_spike(
            system, molecule="A", amount=5.0,
            recovery_steps=50, tolerance=0.05,
        )
        # A stays at 10.0 vs baseline 5.0 — no recovery
        assert not result.recovered

    def test_result_has_baseline_and_perturbed(self):
        system = _make_homeostatic_system()
        result = inject_spike(
            system, molecule="A", amount=3.0,
            recovery_steps=100,
        )
        assert "A" in result.baseline_final
        assert "A" in result.perturbed_final

    def test_recovery_step_found(self):
        system = _make_homeostatic_system()
        result = inject_spike(
            system, molecule="A", amount=1.0,
            recovery_steps=500, tolerance=0.15,
        )
        if result.recovered:
            assert result.recovery_step is not None
            assert result.recovery_step >= 0

    def test_small_spike_recovers_faster(self):
        system = _make_homeostatic_system()

        small = inject_spike(
            system, molecule="A", amount=0.5,
            recovery_steps=500, tolerance=0.1,
        )
        large = inject_spike(
            system, molecule="A", amount=5.0,
            recovery_steps=500, tolerance=0.1,
        )
        # Small spike should recover at same or earlier step
        if small.recovered and large.recovered:
            assert small.recovery_step <= large.recovery_step


# === remove_reaction_drift ===

class TestRemoveReactionDrift:

    def test_removing_reaction_causes_drift(self):
        """M6.3 key test: removal causes measurable drift."""
        system = _make_chain_system()
        result = remove_reaction_drift(
            system, reaction_name="r1", steps=100,
        )
        assert isinstance(result, DriftResult)
        assert result.drifted

    def test_drift_is_measurable(self):
        system = _make_chain_system()
        result = remove_reaction_drift(
            system, reaction_name="r1", steps=100,
        )
        assert result.max_drift > 0.0

    def test_per_molecule_drift(self):
        system = _make_chain_system()
        result = remove_reaction_drift(
            system, reaction_name="r1", steps=100,
        )
        assert "A" in result.drift_per_molecule
        assert "B" in result.drift_per_molecule
        assert "C_mol" in result.drift_per_molecule
        # r1 converts A->B, removing it means more A, less B
        assert result.drift_per_molecule["A"] > 0.0

    def test_removing_nonexistent_reaction(self):
        """Removing a reaction that doesn't exist = same as baseline."""
        system = _make_chain_system()
        result = remove_reaction_drift(
            system, reaction_name="nonexistent", steps=50,
        )
        assert not result.drifted
        assert result.max_drift < 0.01

    def test_static_system_no_drift(self):
        system = _make_static_system()
        # No reactions to remove, but should still work
        result = remove_reaction_drift(
            system, reaction_name="anything", steps=50,
        )
        assert not result.drifted

    def test_result_has_both_finals(self):
        system = _make_chain_system()
        result = remove_reaction_drift(
            system, reaction_name="r2", steps=50,
        )
        assert "A" in result.baseline_final
        assert "A" in result.modified_final


# === measure_intervention_response ===

class TestMeasureInterventionResponse:

    def test_intervention_changes_state(self):
        system = _make_chain_system()
        deltas = measure_intervention_response(
            system, intervention={"A": 20.0}, steps=50,
        )
        assert "A" in deltas
        assert "B" in deltas
        # Adding more A should increase B production
        assert deltas["B"] > 0.0

    def test_no_intervention_no_change(self):
        """Setting same concentrations gives baseline behavior."""
        system = _make_static_system()
        deltas = measure_intervention_response(
            system, intervention={"A": 5.0}, steps=50,
        )
        assert abs(deltas["A"]) < 1e-10

    def test_multiple_interventions(self):
        system = _make_chain_system()
        deltas = measure_intervention_response(
            system, intervention={"A": 0.0, "B": 10.0}, steps=50,
        )
        assert "A" in deltas
        assert "B" in deltas

    def test_does_not_modify_original_system(self):
        system = _make_chain_system()
        original_a = system.state["A"]
        original_b = system.state["B"]
        measure_intervention_response(
            system, intervention={"A": 100.0}, steps=50,
        )
        assert system.state["A"] == original_a
        assert system.state["B"] == original_b
