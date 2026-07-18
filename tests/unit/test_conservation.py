"""Tests for the opt-in conservation module (bio/conservation.py)."""

from __future__ import annotations

from typing import cast

import pytest

from alienbio.bio import makers as _makers  # noqa: F401  (registers mk.M/mk.R/mk.C)
from alienbio.bio.atom import AtomImpl
from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.infra.mk import mk
from alienbio.bio.conservation import (
    ConservationError,
    check_conservation,
    is_boundary_reaction,
    molecule_quantity,
    reaction_imbalance,
    total_quantity,
    validate_conservation,
)

H = AtomImpl("H", "Hydrogen", 1.0)
O = AtomImpl("O", "Oxygen", 16.0)


def _mol(name: str, atoms=None) -> MoleculeImpl:
    return cast(MoleculeImpl, mk.M(name, atoms=atoms))


def _rxn(name: str, reactants=None, products=None, modifiers=None) -> ReactionImpl:
    return cast(
        ReactionImpl,
        mk.R(name, reactants=reactants, products=products, modifiers=modifiers),
    )


def _chem(*reactions) -> ChemistryImpl:
    # A real ChemistryImpl (check_conservation reads chemistry.reactions).
    return cast(ChemistryImpl, mk.C("test", [WATER, H2, O2, FREE_X, FREE_Y], list(reactions)))


# molecules
WATER = _mol("water", {H: 2, O: 1})
H2 = _mol("h2", {H: 2})
O2 = _mol("o2", {O: 2})
FREE_X = _mol("x")  # atom-free (legacy-style)
FREE_Y = _mol("y")


def test_molecule_quantity_is_atom_composition():
    assert molecule_quantity(WATER) == {"H": 2.0, "O": 1.0}
    assert molecule_quantity(FREE_X) == {}


def test_is_boundary_reaction():
    source = _rxn("source", reactants=None, products={WATER: 1})
    sink = _rxn("sink", reactants={WATER: 1}, products=None)
    internal = _rxn("internal", reactants={H2: 2, O2: 1}, products={WATER: 2})
    assert is_boundary_reaction(source)
    assert is_boundary_reaction(sink)
    assert not is_boundary_reaction(internal)


def test_reaction_imbalance_balanced_and_unbalanced():
    # 2 H2 + O2 -> 2 H2O  (H: 4=4, O: 2=2) balanced
    balanced = _rxn("bal", reactants={H2: 2, O2: 1}, products={WATER: 2})
    assert reaction_imbalance(balanced) == {}
    # H2 -> H2O  (O appears from nowhere)
    unbalanced = _rxn("imbal", reactants={H2: 1}, products={WATER: 1})
    assert reaction_imbalance(unbalanced) == {"O": 1.0}


def test_modifiers_do_not_affect_balance():
    # a catalyst molecule is not consumed/produced -> must not enter the balance
    balanced = _rxn(
        "cat", reactants={H2: 2, O2: 1}, products={WATER: 2}, modifiers={WATER: "catalyst"}
    )
    assert reaction_imbalance(balanced) == {}


def test_check_conservation_exempts_boundary():
    source = _rxn("source", reactants=None, products={WATER: 1})
    balanced = _rxn("bal", reactants={H2: 2, O2: 1}, products={WATER: 2})
    assert check_conservation(_chem(source, balanced)) == []


def test_check_conservation_flags_internal_imbalance():
    unbalanced = _rxn("imbal", reactants={H2: 1}, products={WATER: 1})
    violations = check_conservation(_chem(unbalanced))
    assert len(violations) == 1
    assert violations[0].reaction == "imbal"
    assert violations[0].imbalance == {"O": 1.0}


def test_require_atoms_flags_atom_free_participants():
    atom_free = _rxn("free", reactants={FREE_X: 1}, products={FREE_Y: 1})
    # without require_atoms it "passes" (both empty vectors) — the hazard
    assert check_conservation(_chem(atom_free)) == []
    # with require_atoms it is a violation
    violations = check_conservation(_chem(atom_free), require_atoms=True)
    assert len(violations) == 1
    assert violations[0].reaction == "free"


def test_require_atoms_still_exempts_boundary():
    # a Source of an atom-free species is still a legitimate boundary exchange
    source = _rxn("src", reactants=None, products={FREE_X: 1})
    assert check_conservation(_chem(source), require_atoms=True) == []


def test_validate_conservation_raises_on_imbalance():
    unbalanced = _rxn("imbal", reactants={H2: 1}, products={WATER: 1})
    with pytest.raises(ConservationError):
        validate_conservation(_chem(unbalanced))
    # balanced chemistry returns None
    balanced = _rxn("bal", reactants={H2: 2, O2: 1}, products={WATER: 2})
    assert validate_conservation(_chem(balanced)) is None


def test_total_quantity_is_extensive_and_multiplicity_weighted():
    tree = CompartmentTreeImpl()
    cell = tree.add_root("cell")
    state = WorldStateImpl(tree=tree, num_molecules=2)
    state.set(cell, 0, 2.0)  # index 0 = water
    state.set(cell, 1, 1.0)  # index 1 = o2
    state.set_multiplicity(cell, 3.0)
    per_index = [molecule_quantity(WATER), molecule_quantity(O2)]
    total = total_quantity(state, per_index)
    # H: 3 * (2 * 2)                     = 12
    # O: 3 * (2 * 1  +  1 * 2)           = 12
    assert total == {"H": 12.0, "O": 12.0}
