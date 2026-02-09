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
    MockDat,
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


def make_homeostatic_system(seed: int = 42) -> BioSystem:
    """Create a 3-molecule zynol↔brevix↔corthan equilibrium system.

    Returns a BioSystem that converges to stable equilibrium.
    """
    zr = AtomImpl("Zr", name="Zyrium", atomic_weight=14.7)
    zynol = MoleculeImpl("zynol", atoms={zr: 1}, bdepth=0, dat=MockDat("mol/zynol"))
    brevix = MoleculeImpl("brevix", atoms={zr: 1}, bdepth=0, dat=MockDat("mol/brevix"))
    corthan = MoleculeImpl("corthan", atoms={zr: 1}, bdepth=0, dat=MockDat("mol/corthan"))

    r_zb = ReactionImpl(
        "r_zb", reactants={zynol: 1.0}, products={brevix: 1.0},
        rate=lambda s: 0.1 * s["zynol"], dat=MockDat("rxn/r_zb"),
    )
    r_bz = ReactionImpl(
        "r_bz", reactants={brevix: 1.0}, products={zynol: 1.0},
        rate=lambda s: 0.05 * s["brevix"], dat=MockDat("rxn/r_bz"),
    )
    r_bc = ReactionImpl(
        "r_bc", reactants={brevix: 1.0}, products={corthan: 1.0},
        rate=lambda s: 0.08 * s["brevix"], dat=MockDat("rxn/r_bc"),
    )
    r_cb = ReactionImpl(
        "r_cb", reactants={corthan: 1.0}, products={brevix: 1.0},
        rate=lambda s: 0.04 * s["corthan"], dat=MockDat("rxn/r_cb"),
    )

    chem = ChemistryImpl(
        "zbc", atoms={"Zr": zr},
        molecules={"zynol": zynol, "brevix": brevix, "corthan": corthan},
        reactions={"r_zb": r_zb, "r_bz": r_bz, "r_bc": r_bc, "r_cb": r_cb},
        dat=MockDat("chem/zbc"),
    )
    state = StateImpl(chem, initial={"zynol": 10.0, "brevix": 0.0, "corthan": 0.0})
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
