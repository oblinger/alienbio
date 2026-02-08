"""Shared builders and agents for demo scripts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List, TYPE_CHECKING

# Ensure the package is importable when running demos standalone.
_root = Path(__file__).resolve().parent.parent / "src"
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from alienbio.bio import (
    AgentInterface,
    AtomImpl,
    Baseline,
    BioSystem,
    ChemistryImpl,
    MoleculeImpl,
    Perturbation,
    ReactionImpl,
    StateImpl,
    Task,
    generate_organism,
    generate_perturbations,
    measure_baseline,
)

if TYPE_CHECKING:
    from alienbio.bio import Organism


class _MockDat:
    """Minimal DAT stub for demo systems."""

    def __init__(self, path: str) -> None:
        self._path = path

    def get_path_name(self) -> str:
        return self._path

    def get_path(self) -> str:
        return f"/tmp/{self._path}"

    def save(self) -> None:
        pass


def make_homeostatic_system(seed: int = 42) -> BioSystem:
    """Create a 3-molecule A<->B<->C equilibrium system.

    Returns a BioSystem that converges to stable equilibrium.
    """
    c_atom = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={c_atom: 1}, bdepth=0, dat=_MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={c_atom: 1}, bdepth=0, dat=_MockDat("mol/B"))
    c = MoleculeImpl("C", atoms={c_atom: 1}, bdepth=0, dat=_MockDat("mol/C"))

    r_ab = ReactionImpl(
        "r_ab", reactants={a: 1.0}, products={b: 1.0},
        rate=lambda s: 0.1 * s["A"], dat=_MockDat("rxn/r_ab"),
    )
    r_ba = ReactionImpl(
        "r_ba", reactants={b: 1.0}, products={a: 1.0},
        rate=lambda s: 0.05 * s["B"], dat=_MockDat("rxn/r_ba"),
    )
    r_bc = ReactionImpl(
        "r_bc", reactants={b: 1.0}, products={c: 1.0},
        rate=lambda s: 0.08 * s["B"], dat=_MockDat("rxn/r_bc"),
    )
    r_cb = ReactionImpl(
        "r_cb", reactants={c: 1.0}, products={b: 1.0},
        rate=lambda s: 0.04 * s["C"], dat=_MockDat("rxn/r_cb"),
    )

    chem = ChemistryImpl(
        "abc", atoms={"C": c_atom},
        molecules={"A": a, "B": b, "C": c},
        reactions={"r_ab": r_ab, "r_ba": r_ba, "r_bc": r_bc, "r_cb": r_cb},
        dat=_MockDat("chem/abc"),
    )
    state = StateImpl(chem, initial={"A": 10.0, "B": 0.0, "C": 0.0})
    return BioSystem(chem, state, dt=0.1)


def make_disease_system(
    seed: int = 42,
) -> tuple[BioSystem, Baseline, List[Perturbation]]:
    """Create a homeostatic system with baseline and perturbations.

    Returns:
        ``(system, baseline, perturbations)``
    """
    system = make_homeostatic_system(seed)
    baseline = measure_baseline(system, steps=500)
    # Reset to steady state for fresh perturbation
    system2 = make_homeostatic_system(seed)
    system2.run(500)
    perturbations = generate_perturbations(system2, seed=seed)
    return system2, baseline, perturbations


def make_organism(seed: int = 42) -> "Organism":
    """Create a multi-compartment organism from the homeostatic chemistry."""
    system = make_homeostatic_system(seed)
    return generate_organism(system.chemistry, num_organs=3, seed=seed)


# --- Simple agents ---

def oracle_agent(interface: AgentInterface, task: Task) -> Any:
    """Agent that always returns the correct answer (for diagnosis tasks)."""
    from alienbio.bio import DiagnoseTask
    if isinstance(task, DiagnoseTask):
        return task.correct_index
    return 0


def random_agent(interface: AgentInterface, task: Task) -> Any:
    """Agent that picks a random candidate."""
    import random
    from alienbio.bio import DiagnoseTask
    if isinstance(task, DiagnoseTask):
        return random.randrange(task.num_candidates)
    return 0


def zero_agent(interface: AgentInterface, task: Task) -> Any:
    """Agent that always returns 0."""
    return 0
