"""Opt-in conservation checks: atom/mass balance over reactions + a total-quantity canary.

This module is **additive and opt-in** — nothing in the existing simulation path imports it,
so it does not change any current behavior (F012 Q2: scope to the composition path first,
migrate the legacy ``splice``/carve path later).

Conservation is defined over a **generalized conserved-quantity vector** per species, not over
atoms specifically (F012 Q3): ``molecule_quantity`` supplies atoms as the *molecular* instance
of that quantity, but ``reaction_imbalance``/``check_conservation`` accept any
``quantity`` callable, so a future biomass/headcount quantity for count-based (demographic)
species plugs in with no change here. A reaction is well-formed when, for every element/label,
``Σ stoich·quantity`` over products equals that over reactants.

**Boundary/exchange reactions** (empty reactants, e.g. a Source ``∅ → X``, or empty products,
e.g. a Sink ``X → ∅``) are legitimate exchanges with the environment and are exempt from the
internal-balance requirement. Non-consumed ``modifiers`` (catalysts/regulators) never enter the
balance — they are not stoichiometrically consumed or produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .chemistry import ChemistryImpl
    from .molecule import MoleculeImpl
    from .reaction import ReactionImpl
    from .world_state import WorldStateImpl

# A conserved-quantity vector: label (element symbol, or a demographic label) -> amount.
ConservedVector = Dict[str, float]

# Numerical tolerance for treating a net imbalance as zero (float stoichiometry).
_TOL = 1e-9


def molecule_quantity(molecule: "MoleculeImpl") -> ConservedVector:
    """The conserved quantity carried by a molecule — its atom composition.

    Atoms are the *molecular* instance of the generic conserved quantity; the keys are atom
    symbols. Returns an empty dict for an atom-free molecule (legal in the legacy path).
    """
    return {atom.symbol: float(count) for atom, count in molecule.atoms.items()}


def is_boundary_reaction(reaction: "ReactionImpl") -> bool:
    """True if the reaction exchanges with the environment (empty reactants or products).

    Source (``∅ → X``) and Sink (``X → ∅``) legitimately inject/remove matter and are exempt
    from the internal-balance requirement.
    """
    return not reaction.reactants or not reaction.products


def reaction_imbalance(
    reaction: "ReactionImpl",
    quantity: Callable[["MoleculeImpl"], ConservedVector] = molecule_quantity,
) -> ConservedVector:
    """Net conserved-quantity change (products − reactants) per label.

    An empty result means the reaction is balanced. Only labels whose net magnitude exceeds
    ``_TOL`` are returned.
    """
    net: ConservedVector = {}
    for mol, stoich in reaction.reactants.items():
        for label, amount in quantity(mol).items():
            net[label] = net.get(label, 0.0) - stoich * amount
    for mol, stoich in reaction.products.items():
        for label, amount in quantity(mol).items():
            net[label] = net.get(label, 0.0) + stoich * amount
    return {label: v for label, v in net.items() if abs(v) > _TOL}


@dataclass(frozen=True)
class BalanceViolation:
    """A reaction that fails the conservation check."""

    reaction: str
    imbalance: ConservedVector
    reason: str


class ConservationError(ValueError):
    """Raised by ``validate_conservation`` when a chemistry has balance violations."""


def check_conservation(
    chemistry: "ChemistryImpl",
    *,
    quantity: Callable[["MoleculeImpl"], ConservedVector] = molecule_quantity,
    require_atoms: bool = False,
    exempt_boundary: bool = True,
) -> List[BalanceViolation]:
    """Return every reaction that is not conserved (empty list ⇒ the chemistry is clean).

    Args:
        chemistry: the chemistry whose reactions are checked.
        quantity: per-molecule conserved-quantity accessor (atoms by default).
        require_atoms: when True, an internal reaction whose participants lack any conserved
            quantity is itself a violation — this prevents an atom-free molecule from silently
            "passing" balance (used by the strict composition path).
        exempt_boundary: when True, boundary/exchange reactions are skipped (Source/Sink).
    """
    violations: List[BalanceViolation] = []
    for name, reaction in chemistry.reactions.items():
        if exempt_boundary and is_boundary_reaction(reaction):
            continue
        if require_atoms:
            missing = [
                mol.name
                for mol in list(reaction.reactants) + list(reaction.products)
                if not quantity(mol)
            ]
            if missing:
                violations.append(
                    BalanceViolation(name, {}, f"participants carry no conserved quantity: {missing}")
                )
                continue
        imbalance = reaction_imbalance(reaction, quantity)
        if imbalance:
            violations.append(BalanceViolation(name, imbalance, "not balanced"))
    return violations


#: ``conservation_outcome`` verdicts. ``"vacuous: no atoms"`` is the one a
#: clean ``check_conservation`` hides: no internal reaction had a participant
#: carrying a conserved quantity, so the balance was ``{}`` by construction and
#: proved nothing (T088 bio/conservation 1).
BALANCED = "balanced"
VACUOUS = "vacuous: no atoms"


def conservation_outcome(
    chemistry: "ChemistryImpl",
    *,
    quantity: Callable[["MoleculeImpl"], ConservedVector] = molecule_quantity,
    exempt_boundary: bool = True,
) -> str:
    """What a default ``check_conservation`` pass actually established.

    ``"violated: N reaction(s)"`` when the check finds an imbalance;
    :data:`VACUOUS` when no checked internal reaction has any participant
    carrying a conserved quantity (every skeleton-minted world today: its pools
    carry no atoms, so ``X → Y`` and ``X → 2Y`` both net to ``{}``);
    ``"partial: K of N internal reactions carry no atoms"`` when only some do;
    :data:`BALANCED` when every checked reaction was balanced over real
    quantities. A chemistry with no internal reaction is :data:`BALANCED`
    (nothing to conserve).
    """
    violations = check_conservation(
        chemistry, quantity=quantity, exempt_boundary=exempt_boundary
    )
    if violations:
        return f"violated: {len(violations)} reaction(s)"
    internal = [
        r
        for r in chemistry.reactions.values()
        if not (exempt_boundary and is_boundary_reaction(r))
    ]
    empty = [
        r
        for r in internal
        if not any(quantity(m) for m in list(r.reactants) + list(r.products))
    ]
    if internal and len(empty) == len(internal):
        return VACUOUS
    if empty:
        return f"partial: {len(empty)} of {len(internal)} internal reactions carry no atoms"
    return BALANCED


def validate_conservation(chemistry: "ChemistryImpl", **kwargs) -> None:
    """Raise ``ConservationError`` if any reaction is not conserved; else return None.

    Thin fail-visibly wrapper over ``check_conservation`` (same keyword arguments).
    """
    violations = check_conservation(chemistry, **kwargs)
    if violations:
        detail = "; ".join(f"{v.reaction} ({v.reason}: {v.imbalance})" for v in violations)
        raise ConservationError(f"{len(violations)} reaction(s) violate conservation: {detail}")


def total_quantity(
    state: "WorldStateImpl",
    per_index_quantity: List[ConservedVector],
) -> ConservedVector:
    """Total conserved quantity across a whole world state — the conservation *canary*.

    Extensive sum over compartments of ``Σ_molecule amount · quantity``, where ``amount`` is
    the volume-aware count ``multiplicity · volume · concentration`` (``WorldState.amount``).
    ``per_index_quantity[j]`` is the conserved vector for molecule index ``j``. For a world
    whose internal reactions are balanced and whose flows conserve, this total is invariant
    across simulation steps — but only there: a boundary reaction (a Source or Sink, exempt
    from the check and present in every generated world) and a population law (births and
    deaths change the count, ``population.py``) move it legitimately, so on such a world a
    drift is not by itself a leak. Nothing in ``src/`` calls it today.
    """
    total: ConservedVector = {}
    num_molecules = state.num_molecules
    for compartment in range(state.num_compartments):
        for j in range(num_molecules):
            amt = state.amount(compartment, j)
            if amt == 0.0:
                continue
            for label, per_unit in per_index_quantity[j].items():
                total[label] = total.get(label, 0.0) + amt * per_unit
    return total
