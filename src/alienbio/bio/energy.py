"""Opt-in energy accounting: reaction free-energy (ΔG) + a total-free-energy canary.

This module is **additive and opt-in** — nothing in the existing simulation path imports it,
so it does not change any current behavior (mirrors F012's ``bio/conservation.py`` posture).
Energy is ``bio/conservation.py``'s scalar sibling: where conservation books a per-element
conserved-quantity *vector* and demands it net to zero, energy books a single scalar
``Σ stoich·formation_energy`` per reaction (F018 Q2: a molecule's ``formation_energy`` is an
opaque assigned scalar, like ``atoms`` — never derived from atom composition/bond count).

**Accounted, not equated.** A reaction legitimately releases (ΔG < 0, exothermic) or absorbs
(ΔG > 0, endothermic) free energy — the invariant is only that the books balance against a
sink, never that a per-reaction ΔG is zero. This module ships the **heat-sink** form first
(F018 Q1, lean C, ship A first): every reaction's ΔG is assumed to flow to/from an implicit
heat reservoir, so the only opt-in constraint offered here is *spontaneity* — an uncoupled
reaction must run downhill (ΔG ≤ 0).

**Extension point (not implemented here):** an explicit energy-carrier (ATP-analog) species
would let an uphill reaction "couple" to carrier consumption so the *coupled* ΔG is ≤ 0 even
though the bare reaction ΔG is positive. That would take the shape of a
``couple(reaction, carrier, n) -> float`` helper computing a coupled ΔG (bare ΔG minus
``n * carrier.formation_energy``), and ``check_energy``/``reaction_delta_g`` would need a way
to know which reactions are coupled (e.g. an optional ``coupled: Mapping[reaction_name, ...]``
argument). Left undone until a Skeleton block needs coupled uphill work (F018 plan step 3).

**Boundary/exchange reactions** (empty reactants, e.g. a Source ``∅ → X``, or empty products,
e.g. a Sink ``X → ∅``) exchange with the environment and are exempt from the internal
spontaneity requirement, exactly as in ``conservation.py``. Non-consumed ``modifiers``
(catalysts/regulators) never enter ΔG — they are not stoichiometrically consumed or produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, TYPE_CHECKING

from .conservation import is_boundary_reaction

if TYPE_CHECKING:
    from .chemistry import ChemistryImpl
    from .molecule import MoleculeImpl
    from .reaction import ReactionImpl
    from .world_state import WorldStateImpl

# Numerical tolerance for treating a net free-energy change as zero (float stoichiometry).
_TOL = 1e-9


def _formation_energy(molecule: "MoleculeImpl") -> float:
    """A molecule's formation energy, or ``0.0`` if it is energy-neutral (``None``)."""
    energy = molecule.formation_energy
    return energy if energy is not None else 0.0


def reaction_delta_g(reaction: "ReactionImpl") -> float:
    """Net free-energy change of a reaction (products − reactants).

    ``Σ stoich·formation_energy`` over products minus the same sum over reactants. A
    molecule whose ``formation_energy`` is ``None`` (energy-neutral) contributes ``0.0``.
    ``modifiers`` are never stoichiometrically consumed or produced and do not enter ΔG.
    """
    delta = 0.0
    for mol, stoich in reaction.reactants.items():
        delta -= stoich * _formation_energy(mol)
    for mol, stoich in reaction.products.items():
        delta += stoich * _formation_energy(mol)
    return delta


@dataclass(frozen=True)
class EnergyViolation:
    """A reaction that fails the (opt-in) energy check."""

    reaction: str
    delta_g: float
    reason: str


class EnergyError(ValueError):
    """Raised by ``validate_energy`` when a chemistry has energy violations."""


def check_energy(
    chemistry: "ChemistryImpl",
    *,
    spontaneity: bool = False,
    exempt_boundary: bool = True,
) -> List[EnergyViolation]:
    """Return every reaction that fails the (opt-in) energy check (empty ⇒ clean).

    Args:
        chemistry: the chemistry whose reactions are checked.
        spontaneity: when True, any uncoupled internal reaction with ΔG > ``_TOL`` is a
            violation — an uncoupled reaction must run downhill. When False (default),
            no constraint is applied and this always returns ``[]`` (energy is booked, not
            constrained, until spontaneity is explicitly opted into).
        exempt_boundary: when True, boundary/exchange reactions are skipped (Source/Sink) —
            they legitimately exchange free energy with the environment.
    """
    violations: List[EnergyViolation] = []
    if not spontaneity:
        return violations
    for name, reaction in chemistry.reactions.items():
        if exempt_boundary and is_boundary_reaction(reaction):
            continue
        delta_g = reaction_delta_g(reaction)
        if delta_g > _TOL:
            violations.append(
                EnergyViolation(name, delta_g, "uncoupled reaction runs uphill (ΔG > 0)")
            )
    return violations


def validate_energy(chemistry: "ChemistryImpl", **kwargs) -> None:
    """Raise ``EnergyError`` if any reaction violates the energy check; else return None.

    Thin fail-visibly wrapper over ``check_energy`` (same keyword arguments).
    """
    violations = check_energy(chemistry, **kwargs)
    if violations:
        detail = "; ".join(f"{v.reaction} ({v.reason}: ΔG={v.delta_g})" for v in violations)
        raise EnergyError(f"{len(violations)} reaction(s) violate energy accounting: {detail}")


def total_free_energy(
    state: "WorldStateImpl",
    per_index_formation: List[float],
) -> float:
    """Total free energy across a whole world state — the energy *canary*.

    Extensive sum over compartments of ``Σ_molecule amount · formation_energy``, where
    ``amount`` is the volume-aware count ``multiplicity · volume · concentration``
    (``WorldState.amount``), paralleling ``conservation.total_quantity``.
    ``per_index_formation[j]`` is the formation energy for molecule index ``j`` (``0.0`` for
    an energy-neutral molecule). For a closed, balanced system this total is invariant across
    simulation steps; a per-step drift is a leak and should fail loudly.
    """
    total = 0.0
    num_molecules = state.num_molecules
    for compartment in range(state.num_compartments):
        for j in range(num_molecules):
            amt = state.amount(compartment, j)
            if amt == 0.0:
                continue
            total += amt * per_index_formation[j]
    return total
