"""Tests for M11 Diagnosis and Cure Tasks."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AgentInterface,
    AtomImpl,
    Baseline,
    BioSystem,
    ChemistryImpl,
    CureTask,
    DiagnoseTask,
    HealthRange,
    MoleculeImpl,
    Perturbation,
    ReactionImpl,
    StateImpl,
    measure_baseline,
    run_experiment,
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
    """System with source/degradation for A and B."""
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


# === M11.1 Diagnosis Task ===

class TestDiagnoseTask:

    def test_is_task(self):
        from alienbio.bio import Task
        candidates = [
            Perturbation("p0", "rate_change", "source", factor=0.1),
            Perturbation("p1", "reaction_removal", "degrade"),
        ]
        task = DiagnoseTask(candidates, applied_index=0)
        assert isinstance(task, Task)

    def test_name_and_description(self):
        candidates = [
            Perturbation("p0", "rate_change", "source", factor=0.1),
            Perturbation("p1", "reaction_removal", "degrade"),
        ]
        task = DiagnoseTask(candidates, applied_index=1)
        assert task.name == "diagnose"
        assert "2" in task.description

    def test_oracle_scores_one(self):
        """M11.1 key test: oracle agent with full info scores 1.0."""
        system = _make_homeostatic_system()
        iface = AgentInterface(system)

        candidates = [
            Perturbation("p0", "rate_change", "source", factor=0.1),
            Perturbation("p1", "reaction_removal", "degrade"),
        ]
        task = DiagnoseTask(candidates, applied_index=1)

        # Oracle knows the correct answer
        result = task.score(iface, prediction=1)
        assert result.score == 1.0
        assert result.details["correct"]

    def test_wrong_answer_scores_zero(self):
        system = _make_homeostatic_system()
        iface = AgentInterface(system)

        candidates = [
            Perturbation("p0", "rate_change", "source", factor=0.1),
            Perturbation("p1", "reaction_removal", "degrade"),
        ]
        task = DiagnoseTask(candidates, applied_index=1)

        result = task.score(iface, prediction=0)
        assert result.score == 0.0
        assert not result.details["correct"]

    def test_properties(self):
        candidates = [
            Perturbation("p0", "rate_change", "source", factor=0.1),
        ]
        task = DiagnoseTask(candidates, applied_index=0)
        assert task.num_candidates == 1
        assert task.correct_index == 0
        assert len(task.candidates) == 1

    def test_oracle_agent_via_experiment(self):
        """Oracle agent via run_experiment scores 1.0."""
        system = _make_homeostatic_system()
        iface = AgentInterface(system)

        candidates = [
            Perturbation("p0", "rate_change", "source", factor=0.1),
            Perturbation("p1", "reaction_removal", "degrade"),
            Perturbation("p2", "rate_change", "source_b", factor=5.0),
        ]
        task = DiagnoseTask(candidates, applied_index=2)

        def oracle(interface, t):
            return t.correct_index

        result = run_experiment(iface, task, oracle)
        assert result.score == 1.0


# === M11.2 Cure Task ===

class TestCureTask:

    def test_is_task(self):
        from alienbio.bio import Task
        baseline = Baseline(
            steady_state={"A": 10.0},
            ranges=[HealthRange("A", 8.0, 12.0)],
        )
        task = CureTask(baseline)
        assert isinstance(task, Task)

    def test_name_and_description(self):
        baseline = Baseline(
            steady_state={"A": 10.0},
            ranges=[HealthRange("A", 8.0, 12.0)],
        )
        task = CureTask(baseline)
        assert task.name == "cure"
        assert len(task.description) > 0

    def test_correct_cure_scores_one(self):
        """M11.2 key test: applying correct cure returns organism to healthy range."""
        # Create healthy system and measure baseline
        healthy = _make_homeostatic_system()
        baseline = measure_baseline(healthy, steps=500)

        # Create diseased system (source removed)
        diseased = _make_homeostatic_system()
        p = Perturbation("source_removed", "reaction_removal", "source")
        p.apply(diseased)
        diseased.run(300)  # let disease develop

        iface = AgentInterface(diseased)
        task = CureTask(baseline, recovery_steps=500)

        # Cure: restore the source reaction rate
        # Since we zeroed it, set it back to 1.0
        diseased.chemistry.reactions["source"].set_rate(1.0)

        result = task.score(iface, prediction=None)
        assert result.score == 1.0

    def test_no_cure_scores_low(self):
        """Diseased system without cure should score low."""
        healthy = _make_homeostatic_system()
        baseline = measure_baseline(healthy, steps=500)

        diseased = _make_homeostatic_system()
        p = Perturbation("source_removed", "reaction_removal", "source")
        p.apply(diseased)
        diseased.run(300)

        iface = AgentInterface(diseased)
        task = CureTask(baseline, recovery_steps=500)

        # No cure applied — A should be near 0
        result = task.score(iface, prediction=None)
        assert result.score < 1.0

    def test_score_details(self):
        baseline = Baseline(
            steady_state={"A": 10.0, "B": 5.0},
            ranges=[
                HealthRange("A", 8.0, 12.0),
                HealthRange("B", 3.0, 7.0),
            ],
        )
        system = _make_homeostatic_system()
        iface = AgentInterface(system)
        task = CureTask(baseline, recovery_steps=100)

        result = task.score(iface, prediction=None)
        assert "molecules" in result.details
        assert "in_range" in result.details
        assert "total" in result.details

    def test_properties(self):
        baseline = Baseline(
            steady_state={"A": 10.0},
            ranges=[HealthRange("A", 8.0, 12.0)],
        )
        task = CureTask(baseline, recovery_steps=300)
        assert task.recovery_steps == 300
        assert task.baseline is baseline
