"""World perturbations — pure ``WorldImpl -> WorldImpl`` edits (M27 predict/intervene).

A *perturbation* is a small, surgical change to a runnable biology
:class:`~alienbio.bio.world.WorldImpl`: bump one reaction's rate, drop one
reaction, or spike one molecule's initial concentration. These are the causal
levers the ``predict`` and ``intervene`` archetypes pull — "if I change *this*,
how does the trajectory change?" — so their signatures are stable and documented.

:class:`~alienbio.bio.world.WorldImpl` is **immutable** (it derives and freezes
its ``initial_state`` at construction, and its slots never mutate). Every
perturbation therefore returns a **brand-new** ``WorldImpl``: it rebuilds the
one piece that changes (a fresh :class:`~alienbio.bio.chemistry.ChemistryImpl`
for reaction edits, a fresh :class:`~alienbio.bio.world.Compartment` for
concentration edits) while reusing every untouched node object **by identity** —
so everything else is byte-for-byte identical, exactly as
:func:`~alienbio.suite.carve.splice` reconstructs a chemistry. The edits are pure: the input ``world`` is never mutated.

Each function raises a clear error on an unknown id, so a caller pulling a lever
that does not exist fails loudly rather than silently no-op'ing.
"""

from __future__ import annotations

from ..bio.chemistry import ChemistryImpl, _mock_dat
from ..bio.rate_expr import const
from ..bio.reaction import ReactionImpl, rebuild_reaction
from ..bio.world import Compartment, WorldImpl, rebuild_world


def _rebuild_world(
    world: WorldImpl,
    reactions: dict[str, ReactionImpl],
) -> WorldImpl:
    """A new ``WorldImpl`` over ``world``'s molecules/atoms/compartments + ``reactions``.

    Molecules and atoms are reused by identity (never rebuilt); only the reaction
    table is swapped. The compartments are shared unchanged, so the new world's
    ``initial_state`` re-derives against the same molecule axis; flows and
    population laws are carried over (:func:`~alienbio.bio.world.rebuild_world`).
    """
    chem = world.chemistry
    new_chem = ChemistryImpl(
        "perturbed",
        atoms=dict(chem.atoms),
        molecules=dict(chem.molecules),
        reactions=reactions,
        dat=_mock_dat("chem/perturbed"),
    )
    return rebuild_world(world, new_chem)


def perturb_rate(world: WorldImpl, reaction_id: str, factor: float) -> WorldImpl:
    """Return a new world with exactly one reaction's rate multiplied by ``factor``.

    Every other reaction, all molecules, atoms, and compartments are identical
    (reused by identity). The perturbed reaction keeps its reactants, products,
    modifiers and description; its rate constant scales — or, for a reaction
    with a compiled ``rate_law`` (which makes ``rate`` unused), the law is
    multiplied by ``factor`` (T088: the law used to be dropped, so the
    reaction ran mass action at ``rate * factor``).

    Raises:
        KeyError: if ``reaction_id`` is not a reaction of ``world``.
    """
    chem = world.chemistry
    if reaction_id not in chem.reactions:
        raise KeyError(
            f"perturb_rate: unknown reaction {reaction_id!r}; "
            f"reactions are {sorted(chem.reactions)}"
        )
    old = chem.reactions[reaction_id]
    rate = old.rate  # numeric: ReactionImpl refuses anything else (2026-10)

    new_reactions = dict(chem.reactions)
    law = old.rate_law
    new_reactions[reaction_id] = rebuild_reaction(
        old,
        rate=rate * factor,
        rate_law=("mul", const(factor), law) if law is not None else None,
        dat=_mock_dat(f"rxn/{reaction_id}"),
    )
    return _rebuild_world(world, new_reactions)


def remove_reaction(world: WorldImpl, reaction_id: str) -> WorldImpl:
    """Return a new world with exactly one reaction dropped; molecules unchanged.

    The molecule set is left intact — only the reaction node disappears from
    ``world.chemistry.reactions``. All other reactions, atoms, and compartments
    are reused by identity.

    Raises:
        KeyError: if ``reaction_id`` is not a reaction of ``world``.
    """
    chem = world.chemistry
    if reaction_id not in chem.reactions:
        raise KeyError(
            f"remove_reaction: unknown reaction {reaction_id!r}; "
            f"reactions are {sorted(chem.reactions)}"
        )
    new_reactions = {
        rid: rxn for rid, rxn in chem.reactions.items() if rid != reaction_id
    }
    return _rebuild_world(world, new_reactions)


def spike_concentration(
    world: WorldImpl, molecule_id: str, amount: float
) -> WorldImpl:
    """Return a new world with ``amount`` added to one molecule's initial concentration.

    Edits the single compartment's initial condition only: the named molecule's
    starting concentration becomes ``current + amount`` (``current`` defaults to
    ``0.0`` when the compartment did not list it). The chemistry — molecules,
    reactions, atoms — is reused by identity, flows and population laws are
    carried over; every other concentration is unchanged.

    Raises:
        KeyError: if ``molecule_id`` is not a molecule of ``world``.
        ValueError: if ``world`` does not have exactly one compartment (the
            single-compartment world this lever targets).
    """
    chem = world.chemistry
    if molecule_id not in chem.molecules:
        raise KeyError(
            f"spike_concentration: unknown molecule {molecule_id!r}; "
            f"molecules are {sorted(chem.molecules)}"
        )
    comps = world.compartments
    if len(comps) != 1:
        raise ValueError(
            f"spike_concentration targets a single-compartment world; "
            f"got {len(comps)} compartments"
        )
    comp = comps[0]
    new_conc = dict(comp.concentrations)
    new_conc[molecule_id] = new_conc.get(molecule_id, 0.0) + amount
    new_comp = Compartment(
        comp.id,
        comp.parent,
        comp.kind,
        comp.volume,
        concentrations=new_conc,
        multiplicity=comp.multiplicity,
    )
    return rebuild_world(world, compartments=(new_comp,))
