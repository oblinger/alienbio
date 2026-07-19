"""Tests for the opt-in energy accounting module (bio/energy.py)."""

from __future__ import annotations

from typing import cast

import pytest

from alienbio.bio import makers as _makers  # noqa: F401  (registers mk.M/mk.R/mk.C)
from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import ReactionImpl
from alienbio.bio.world_state import WorldStateImpl
from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.infra.mk import mk
from alienbio.bio.energy import (
    EnergyError,
    check_energy,
    reaction_delta_g,
    total_free_energy,
    validate_energy,
)


def _mol(name: str, formation_energy=None) -> MoleculeImpl:
    return cast(MoleculeImpl, mk.M(name, formation_energy=formation_energy))


def _rxn(name: str, reactants=None, products=None, modifiers=None) -> ReactionImpl:
    return cast(
        ReactionImpl,
        mk.R(name, reactants=reactants, products=products, modifiers=modifiers),
    )


def _chem(*reactions) -> ChemistryImpl:
    return cast(ChemistryImpl, mk.C("test", [A, B, C, FREE_X], list(reactions)))


# molecules — A (high energy) -> B (low energy) is downhill; B -> A is uphill.
A = _mol("a", formation_energy=10.0)
B = _mol("b", formation_energy=2.0)
C = _mol("c", formation_energy=6.0)
FREE_X = _mol("x")  # no formation_energy -> energy-neutral


def test_molecule_with_no_formation_energy_books_nothing():
    assert FREE_X.formation_energy is None


def test_mk_m_backward_compat_formation_energy_defaults_none():
    plain = cast(MoleculeImpl, mk.M("plain"))
    assert plain.formation_energy is None


def test_reaction_delta_g_signed():
    # downhill: A (10) -> B (2), ΔG = 2 - 10 = -8
    downhill = _rxn("downhill", reactants={A: 1}, products={B: 1})
    assert reaction_delta_g(downhill) == pytest.approx(-8.0)
    # uphill: B (2) -> A (10), ΔG = 10 - 2 = +8
    uphill = _rxn("uphill", reactants={B: 1}, products={A: 1})
    assert reaction_delta_g(uphill) == pytest.approx(8.0)


def test_reaction_delta_g_energy_neutral_molecules_contribute_zero():
    neutral = _rxn("neutral", reactants={FREE_X: 1}, products={FREE_X: 1})
    assert reaction_delta_g(neutral) == 0.0


def test_modifiers_do_not_affect_delta_g():
    with_cat = _rxn(
        "with_cat", reactants={A: 1}, products={B: 1}, modifiers={C: "catalyst"}
    )
    without_cat = _rxn("without_cat", reactants={A: 1}, products={B: 1})
    assert reaction_delta_g(with_cat) == reaction_delta_g(without_cat)


def test_check_energy_default_applies_no_constraint():
    uphill = _rxn("uphill", reactants={B: 1}, products={A: 1})
    # spontaneity is opt-in; without it, an uphill reaction is not flagged
    assert check_energy(_chem(uphill)) == []


def test_check_energy_spontaneity_flags_uncoupled_uphill():
    uphill = _rxn("uphill", reactants={B: 1}, products={A: 1})
    violations = check_energy(_chem(uphill), spontaneity=True)
    assert len(violations) == 1
    assert violations[0].reaction == "uphill"
    assert violations[0].delta_g == pytest.approx(8.0)


def test_check_energy_spontaneity_passes_downhill():
    downhill = _rxn("downhill", reactants={A: 1}, products={B: 1})
    assert check_energy(_chem(downhill), spontaneity=True) == []


def test_check_energy_spontaneity_exempts_boundary():
    # a Source injecting a high-energy molecule from nothing looks "uphill" but is a
    # legitimate boundary exchange with the environment.
    source = _rxn("source", reactants=None, products={A: 1})
    assert check_energy(_chem(source), spontaneity=True) == []


def test_validate_energy_raises_on_uncoupled_uphill():
    uphill = _rxn("uphill", reactants={B: 1}, products={A: 1})
    with pytest.raises(EnergyError):
        validate_energy(_chem(uphill), spontaneity=True)
    downhill = _rxn("downhill", reactants={A: 1}, products={B: 1})
    assert validate_energy(_chem(downhill), spontaneity=True) is None


def test_total_free_energy_is_extensive_and_multiplicity_weighted():
    tree = CompartmentTreeImpl()
    cell = tree.add_root("cell")
    state = WorldStateImpl(tree=tree, num_molecules=2)
    state.set(cell, 0, 2.0)  # index 0 = A (formation_energy 10)
    state.set(cell, 1, 1.0)  # index 1 = B (formation_energy 2)
    state.set_multiplicity(cell, 3.0)
    per_index = [A.formation_energy, B.formation_energy]
    total = total_free_energy(state, per_index)
    # amount(A) = 3 * 1 * 2 = 6 ; amount(B) = 3 * 1 * 1 = 3
    # total = 6*10 + 3*2 = 66
    assert total == pytest.approx(66.0)


def test_total_free_energy_is_volume_aware():
    tree = CompartmentTreeImpl()
    cell = tree.add_root("cell")
    state = WorldStateImpl(tree=tree, num_molecules=1)
    state.set(cell, 0, 2.0)
    state.set_volume(cell, 5.0)
    total = total_free_energy(state, [A.formation_energy])
    # amount = 1 * 5 * 2 = 10 ; total = 10 * 10 = 100
    assert total == pytest.approx(100.0)


def test_total_free_energy_invariant_for_closed_balanced_step():
    # An isoenergetic reaction (ΔG = 0, B -> D where D shares B's formation_energy) leaves
    # total system free energy invariant as it runs to completion — a closed, balanced
    # (no-leak) system. This is the energy canary's steady-state guarantee, mirroring
    # conservation's total_quantity invariance under a balanced reaction.
    D = _mol("d", formation_energy=2.0)
    isoenergetic = _rxn("bd", reactants={B: 1}, products={D: 1})
    assert reaction_delta_g(isoenergetic) == pytest.approx(0.0)

    tree = CompartmentTreeImpl()
    cell = tree.add_root("cell")
    state = WorldStateImpl(tree=tree, num_molecules=2)
    per_index = [B.formation_energy, D.formation_energy]

    # before: 5 units of B, 0 of D
    state.set(cell, 0, 5.0)
    state.set(cell, 1, 0.0)
    before = total_free_energy(state, per_index)
    assert before == pytest.approx(10.0)  # 5 * 2

    # after: reaction B -> D runs to completion
    state.set(cell, 0, 0.0)
    state.set(cell, 1, 5.0)
    after = total_free_energy(state, per_index)
    assert after == pytest.approx(before)  # invariant: no leak for a ΔG=0 reaction
