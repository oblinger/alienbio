"""Shared demo utilities — builders and agent functions for all demos."""

from __future__ import annotations

import random as _random
from typing import Any, Dict, List, Tuple

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
    generate_perturbations,
    measure_baseline,
)
from alienbio.scenarios.organ_generator import Organism, generate_organism


class MockDat:
    """Stub DAT for demo systems."""
    def __init__(self, path: str):
        self._path = path
    def get_path_name(self) -> str:
        return self._path
    def get_path(self) -> str:
        return f"/tmp/{self._path}"
    def save(self) -> None:
        pass


def make_homeostatic_chemistry(seed: int = 42) -> ChemistryImpl:
    """3-molecule chemistry with source/degradation for each — reaches equilibrium.

    Steady states: A ≈ 10.0, B ≈ 5.0, C ≈ 2.0
    """
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
    c = MoleculeImpl("C", atoms={carbon: 3}, bdepth=0, dat=MockDat("mol/C"))

    reactions = {
        "source_a": ReactionImpl(
            "source_a", reactants={}, products={a: 1.0},
            rate=1.0, dat=MockDat("rxn/source_a"),
        ),
        "degrade_a": ReactionImpl(
            "degrade_a", reactants={a: 1.0}, products={},
            rate=lambda s: 0.1 * s["A"], dat=MockDat("rxn/degrade_a"),
        ),
        "source_b": ReactionImpl(
            "source_b", reactants={}, products={b: 1.0},
            rate=0.5, dat=MockDat("rxn/source_b"),
        ),
        "degrade_b": ReactionImpl(
            "degrade_b", reactants={b: 1.0}, products={},
            rate=lambda s: 0.1 * s["B"], dat=MockDat("rxn/degrade_b"),
        ),
        "source_c": ReactionImpl(
            "source_c", reactants={}, products={c: 1.0},
            rate=0.2, dat=MockDat("rxn/source_c"),
        ),
        "degrade_c": ReactionImpl(
            "degrade_c", reactants={c: 1.0}, products={},
            rate=lambda s: 0.1 * s["C"], dat=MockDat("rxn/degrade_c"),
        ),
    }

    return ChemistryImpl(
        "homeostatic",
        atoms={"C": carbon},
        molecules={"A": a, "B": b, "C": c},
        reactions=reactions,
        dat=MockDat("chem/homeostatic"),
    )


def make_homeostatic_system(seed: int = 42) -> BioSystem:
    """Build a 3-molecule homeostatic BioSystem."""
    chem = make_homeostatic_chemistry(seed)
    state = StateImpl(chem, initial={"A": 8.0, "B": 3.0, "C": 1.0})
    return BioSystem(chem, state, dt=0.1)


def make_disease_system(
    seed: int = 42,
) -> Tuple[BioSystem, Baseline, List[Perturbation]]:
    """Build a system with measured baseline and generated perturbations."""
    system = make_homeostatic_system(seed)
    baseline = measure_baseline(system, steps=500)
    perturbs = generate_perturbations(system, seed=seed)
    return system, baseline, perturbs


def make_organism(seed: int = 42) -> Tuple[Organism, ChemistryImpl]:
    """Generate a multi-compartment organism."""
    chem = make_homeostatic_chemistry(seed)
    org = generate_organism(chem, num_organs=3, seed=seed, transport_rate=0.01)
    return org, chem


# --- Demo agents ---

def oracle_agent(interface: AgentInterface, task: Any) -> Any:
    """Perfect agent — returns the correct answer."""
    if hasattr(task, "correct_index"):
        return task.correct_index
    return 0


def random_agent(interface: AgentInterface, task: Any) -> Any:
    """Random agent — guesses randomly."""
    if hasattr(task, "num_candidates"):
        return _random.randint(0, task.num_candidates - 1)
    return _random.random()


def zero_agent(interface: AgentInterface, task: Any) -> Any:
    """Always-zero agent — always predicts 0."""
    return 0
