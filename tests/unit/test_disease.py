"""Tests for M10 Disease and Variation."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AgentInterface,
    AtomImpl,
    Baseline,
    BioSystem,
    ChemistryImpl,
    HealthRange,
    MoleculeImpl,
    Perturbation,
    ReactionImpl,
    StateImpl,
    Symptom,
    detect_symptoms,
    generate_perturbations,
    measure_baseline,
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
    """System with source and degradation for homeostasis.

    Reactions:
        source: ∅ -> A at constant rate 1.0
        degrade: A -> ∅ at rate 0.1 * [A]

    Steady state: [A] = 10.0 (source rate / degradation constant)
    """
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
    # B has its own homeostasis
    source_b = ReactionImpl(
        "source_b", reactants={}, products={b: 1.0},
        rate=0.5, dat=MockDat("rxn/source_b"),
    )
    degrade_b = ReactionImpl(
        "degrade_b", reactants={b: 1.0}, products={},
        rate=lambda state: 0.1 * state["B"],
        dat=MockDat("rxn/degrade_b"),
    )
    chem = ChemistryImpl(
        "test", atoms={"C": carbon},
        molecules={"A": a, "B": b},
        reactions={
            "source": source, "degrade": degrade,
            "source_b": source_b, "degrade_b": degrade_b,
        },
        dat=MockDat("chem/test"),
    )
    state = StateImpl(chem, initial={"A": 10.0, "B": 5.0})
    return BioSystem(chem, state, dt=0.1)


# === M10.1 Baseline Definition ===

class TestHealthRange:

    def test_contains(self):
        r = HealthRange("A", 8.0, 12.0)
        assert r.contains(10.0)
        assert r.contains(8.0)
        assert r.contains(12.0)
        assert not r.contains(7.9)
        assert not r.contains(12.1)


class TestBaseline:

    def test_is_healthy(self):
        baseline = Baseline(
            steady_state={"A": 10.0},
            ranges=[HealthRange("A", 8.0, 12.0)],
        )
        assert baseline.is_healthy({"A": 10.0})
        assert baseline.is_healthy({"A": 8.0})
        assert not baseline.is_healthy({"A": 7.0})

    def test_measure_baseline(self):
        system = _make_homeostatic_system()
        baseline = measure_baseline(system, steps=500)
        # Should converge near steady state A=10.0, B=5.0
        assert baseline.steady_state["A"] == pytest.approx(10.0, abs=0.5)
        assert baseline.steady_state["B"] == pytest.approx(5.0, abs=0.5)

    def test_baseline_has_ranges(self):
        system = _make_homeostatic_system()
        baseline = measure_baseline(system, steps=500)
        assert len(baseline.ranges) == 2
        for r in baseline.ranges:
            assert r.low < r.high

    def test_healthy_system_stays_within_ranges(self):
        """M10.1 key test: healthy organism stays within ranges for 1000 steps."""
        system = _make_homeostatic_system()
        baseline = measure_baseline(system, steps=500)

        # Run for 1000 more steps
        for _ in range(1000):
            system.step()

        concentrations = {
            name: system.state[name]
            for name in system.chemistry.molecules
        }
        assert baseline.is_healthy(concentrations)


# === M10.2 Perturbation Generator ===

class TestPerturbation:

    def test_generate_perturbations(self):
        system = _make_homeostatic_system()
        perturbs = generate_perturbations(system, seed=42)
        assert len(perturbs) > 0
        # One per reaction
        assert len(perturbs) == len(system.chemistry.reactions)

    def test_perturbation_has_name(self):
        system = _make_homeostatic_system()
        perturbs = generate_perturbations(system, seed=42)
        for p in perturbs:
            assert len(p.name) > 0

    def test_perturbation_kinds(self):
        system = _make_homeostatic_system()
        perturbs = generate_perturbations(system, seed=42)
        for p in perturbs:
            assert p.kind in ("rate_change", "reaction_removal")

    def test_rate_change_modifies_rate(self):
        """M10.2 key test: perturbation changes at least one reaction rate."""
        system = _make_homeostatic_system()
        # Get initial rate
        state = system.state
        initial_rate = system.chemistry.reactions["source"].get_rate(state)

        p = Perturbation(
            name="source_rate_x0.1",
            kind="rate_change",
            target_reaction="source",
            factor=0.1,
        )
        p.apply(system)

        new_rate = system.chemistry.reactions["source"].get_rate(state)
        assert new_rate != initial_rate
        assert new_rate == pytest.approx(initial_rate * 0.1)

    def test_reaction_removal(self):
        system = _make_homeostatic_system()
        p = Perturbation(
            name="source_removed",
            kind="reaction_removal",
            target_reaction="source",
        )
        p.apply(system)

        rate = system.chemistry.reactions["source"].get_rate(system.state)
        assert rate == 0.0

    def test_apply_rate_change_to_callable(self):
        system = _make_homeostatic_system()
        state = system.state
        initial_rate = system.chemistry.reactions["degrade"].get_rate(state)

        p = Perturbation(
            name="degrade_rate_x2",
            kind="rate_change",
            target_reaction="degrade",
            factor=2.0,
        )
        p.apply(system)

        new_rate = system.chemistry.reactions["degrade"].get_rate(state)
        assert new_rate == pytest.approx(initial_rate * 2.0)

    def test_only_rate_change_kind(self):
        system = _make_homeostatic_system()
        perturbs = generate_perturbations(
            system, seed=42, kinds=["rate_change"],
        )
        for p in perturbs:
            assert p.kind == "rate_change"


# === M10.3 Symptom Measurement ===

class TestSymptomDetection:

    def test_no_symptoms_when_healthy(self):
        baseline = Baseline(
            steady_state={"A": 10.0, "B": 5.0},
            ranges=[
                HealthRange("A", 8.0, 12.0),
                HealthRange("B", 3.0, 7.0),
            ],
        )
        symptoms = detect_symptoms({"A": 10.0, "B": 5.0}, baseline)
        assert len(symptoms) == 0

    def test_detect_high_concentration(self):
        baseline = Baseline(
            steady_state={"A": 10.0},
            ranges=[HealthRange("A", 8.0, 12.0)],
        )
        symptoms = detect_symptoms({"A": 15.0}, baseline)
        assert len(symptoms) == 1
        assert symptoms[0].molecule == "A"
        assert symptoms[0].deviation == pytest.approx(3.0)

    def test_detect_low_concentration(self):
        baseline = Baseline(
            steady_state={"A": 10.0},
            ranges=[HealthRange("A", 8.0, 12.0)],
        )
        symptoms = detect_symptoms({"A": 5.0}, baseline)
        assert len(symptoms) == 1
        assert symptoms[0].deviation == pytest.approx(3.0)

    def test_diseased_system_has_symptoms(self):
        """M10.3 key test: diseased organism has at least one measurement outside healthy range."""
        system = _make_homeostatic_system()
        baseline = measure_baseline(system, steps=500)

        # Create a fresh system and apply disease
        diseased = _make_homeostatic_system()
        p = Perturbation(
            name="source_removed",
            kind="reaction_removal",
            target_reaction="source",
        )
        p.apply(diseased)

        # Run diseased system to let symptoms develop
        diseased.run(500)

        concentrations = {
            name: diseased.state[name]
            for name in diseased.chemistry.molecules
        }
        symptoms = detect_symptoms(concentrations, baseline)
        assert len(symptoms) > 0

    def test_symptom_has_details(self):
        baseline = Baseline(
            steady_state={"A": 10.0},
            ranges=[HealthRange("A", 8.0, 12.0)],
        )
        symptoms = detect_symptoms({"A": 20.0}, baseline)
        s = symptoms[0]
        assert s.molecule == "A"
        assert s.value == 20.0
        assert s.healthy_range.low == 8.0
        assert s.healthy_range.high == 12.0
        assert s.deviation > 0
