"""Tests for M11.3 Task Difficulty Scaling."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AgentInterface,
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    MoleculeImpl,
    Perturbation,
    ReactionImpl,
    StateImpl,
    generate_diagnosis_task,
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


def _make_system() -> BioSystem:
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
    r1 = ReactionImpl(
        "r1", reactants={a: 1.0}, products={b: 1.0},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/r1"),
    )
    chem = ChemistryImpl(
        "test", atoms={"C": carbon},
        molecules={"A": a, "B": b}, reactions={"r1": r1},
        dat=MockDat("chem/test"),
    )
    state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
    return BioSystem(chem, state, dt=0.1)


def _make_perturbations(n: int) -> list:
    return [
        Perturbation(f"p{i}", "rate_change", "r1", factor=0.1 * (i + 1))
        for i in range(n)
    ]


class TestDifficultyScaling:

    def test_difficulty_1_has_2_candidates(self):
        system = _make_system()
        perturbs = _make_perturbations(10)
        task = generate_diagnosis_task(system, perturbs, difficulty=1, seed=42)
        assert task.num_candidates == 2

    def test_difficulty_2_has_4_candidates(self):
        system = _make_system()
        perturbs = _make_perturbations(10)
        task = generate_diagnosis_task(system, perturbs, difficulty=2, seed=42)
        assert task.num_candidates == 4

    def test_difficulty_5_has_10_candidates(self):
        system = _make_system()
        perturbs = _make_perturbations(10)
        task = generate_diagnosis_task(system, perturbs, difficulty=5, seed=42)
        assert task.num_candidates == 10

    def test_capped_at_pool_size(self):
        system = _make_system()
        perturbs = _make_perturbations(3)
        task = generate_diagnosis_task(system, perturbs, difficulty=10, seed=42)
        assert task.num_candidates == 3

    def test_correct_index_is_valid(self):
        system = _make_system()
        perturbs = _make_perturbations(10)
        task = generate_diagnosis_task(system, perturbs, difficulty=3, seed=42)
        assert 0 <= task.correct_index < task.num_candidates

    def test_reproducible_with_seed(self):
        system = _make_system()
        perturbs = _make_perturbations(10)
        t1 = generate_diagnosis_task(system, perturbs, difficulty=3, seed=99)
        t2 = generate_diagnosis_task(system, perturbs, difficulty=3, seed=99)
        assert t1.correct_index == t2.correct_index
        assert t1.num_candidates == t2.num_candidates

    def test_difficulty_1_easier_than_5(self):
        """M11.3 key test: difficulty=1 easier than difficulty=5.

        An oracle always scores 1.0 regardless of difficulty, but
        a random agent's expected score is 1/N where N is num_candidates.
        So difficulty=1 (N=2) has expected random score 0.5,
        while difficulty=5 (N=10) has expected random score 0.1.
        """
        system = _make_system()
        perturbs = _make_perturbations(10)

        easy = generate_diagnosis_task(system, perturbs, difficulty=1, seed=42)
        hard = generate_diagnosis_task(system, perturbs, difficulty=5, seed=42)

        # Random baseline: 1/num_candidates
        easy_random = 1.0 / easy.num_candidates
        hard_random = 1.0 / hard.num_candidates

        assert easy_random > hard_random
