"""Module-doc findings on serialization: ``ChemistryImpl.hydrate`` of a
chemistry's own ``attributes()`` must rebuild the same chemistry.

Repro (before the fix): ``attributes()`` writes reactants/products as
``{name: coef}`` but ``ReactionImpl.hydrate`` iterated them as a list, so
``A + 2B -> 3C`` reloaded as ``A + B -> C``; ``ChemistryImpl.hydrate`` never
read ``data["atoms"]`` and ``MoleculeImpl.hydrate`` skipped atoms, so every
composition was lost and ``check_conservation`` saw nothing.
"""

from __future__ import annotations

import pytest

from alienbio.bio.atom import AtomImpl
from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.conservation import check_conservation
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.reaction import Modulation, ReactionImpl
from alienbio.infra.entity import MockDat


def _chem() -> ChemistryImpl:
    h = AtomImpl("H", "Hydrogen", 1.008)
    o = AtomImpl("O", "Oxygen", 15.999)
    h2 = MoleculeImpl("h2", dat=MockDat("mol/h2"), atoms={h: 2}, bdepth=0)
    o2 = MoleculeImpl("o2", dat=MockDat("mol/o2"), atoms={o: 2}, bdepth=0)
    water = MoleculeImpl(
        "water", dat=MockDat("mol/water"), atoms={h: 2, o: 1}, bdepth=1,
        formation_energy=-2.5,
    )
    enz = MoleculeImpl("enz", dat=MockDat("mol/enz"))
    burn = ReactionImpl(
        "burn", reactants={h2: 2, o2: 1}, products={water: 2},
        modifiers={enz: Modulation(kind="activator", a=0.5)},
        rate=0.3, dat=MockDat("rxn/burn"),
    )
    return ChemistryImpl(
        "c", atoms={"H": h, "O": o},
        molecules={"h2": h2, "o2": o2, "water": water, "enz": enz},
        reactions={"burn": burn}, dat=MockDat("chem/c"),
    )


def test_hydrate_of_attributes_is_the_identity() -> None:
    chem = _chem()
    back = ChemistryImpl.hydrate(chem.attributes())
    assert back.attributes() == chem.attributes()
    rxn = back.reactions["burn"]
    assert {m.name: c for m, c in rxn.reactants.items()} == {"h2": 2, "o2": 1}
    assert {m.name: c for m, c in rxn.products.items()} == {"water": 2}
    assert back.molecules["water"].symbol == "H2O"
    assert back.molecules["water"].formation_energy == -2.5
    assert set(back.atoms) == {"H", "O"}


def test_conservation_sees_the_atoms_after_a_round_trip() -> None:
    chem = _chem()
    assert check_conservation(chem, require_atoms=True) == []
    back = ChemistryImpl.hydrate(chem.attributes())
    assert check_conservation(back, require_atoms=True) == []
    # an unbalanced reload would now be caught, so the atoms are really there
    data = chem.attributes()
    data["reactions"]["burn"]["products"] = {"water": 1}
    assert check_conservation(ChemistryImpl.hydrate(data), require_atoms=True)


def test_a_molecule_naming_an_atom_the_chemistry_lacks_refuses() -> None:
    data = _chem().attributes()
    del data["atoms"]["O"]
    with pytest.raises(KeyError, match="'O'"):
        ChemistryImpl.hydrate(data)


def test_molecule_hydrate_without_a_registry_refuses_atoms() -> None:
    with pytest.raises(ValueError, match="atoms"):
        MoleculeImpl.hydrate({"name": "w", "atoms": {"H": 2}})


def test_reaction_hydrate_takes_both_side_forms() -> None:
    mols = {n: MoleculeImpl(n, dat=MockDat(f"mol/{n}")) for n in "ABC"}
    as_dict = ReactionImpl.hydrate(
        {"reactants": {"A": 1, "B": 2}, "products": {"C": 3}}, molecules=mols
    )
    as_list = ReactionImpl.hydrate(
        {"reactants": ["A", {"B": 2}], "products": [{"C": 3}]}, molecules=mols
    )
    for rxn in (as_dict, as_list):
        assert {m.name: c for m, c in rxn.reactants.items()} == {"A": 1, "B": 2}
        assert {m.name: c for m, c in rxn.products.items()} == {"C": 3}


def test_a_list_form_modifier_dict_keeps_every_key() -> None:
    mols = {n: MoleculeImpl(n, dat=MockDat(f"mol/{n}")) for n in "ABEF"}
    rxn = ReactionImpl.hydrate(
        {"reactants": ["A"], "products": ["B"],
         "modifiers": [{"E": "catalyst", "F": "inhibitor"}]},
        molecules=mols,
    )
    assert {m.name: r for m, r in rxn.modifiers.items()} == {
        "E": "catalyst", "F": "inhibitor",
    }


def test_a_side_entry_of_the_wrong_type_refuses() -> None:
    mols = {n: MoleculeImpl(n, dat=MockDat(f"mol/{n}")) for n in "AB"}
    with pytest.raises(TypeError, match="reactant"):
        ReactionImpl.hydrate({"reactants": [3], "products": ["B"]}, molecules=mols)


# ── E1: subgraph keeps modifiers and the rate law ────────────────────────────


def test_subgraph_keeps_each_reactions_modifiers_and_rate_law() -> None:
    mols = {n: MoleculeImpl(n, dat=MockDat(f"mol/{n}")) for n in ("S", "P", "E")}
    law = ("div", ("species", "S"), ("add", ("const", 0.5), ("species", "S")))
    rxn = ReactionImpl(
        "mm", reactants={mols["S"]: 1}, products={mols["P"]: 1},
        modifiers={mols["E"]: Modulation(kind="activator", a=2.0)},
        rate=0.3, rate_law=law, dat=MockDat("rxn/mm"),
    )
    chem = ChemistryImpl("c", molecules=mols, reactions={"mm": rxn}, dat=MockDat("chem/c"))
    sub = chem.subgraph(["S", "P", "E", "mm"])
    kept = sub.reactions["mm"]
    assert {m.name: r for m, r in kept.modifiers.items()} == {"E": Modulation(kind="activator", a=2.0)}
    assert kept.rate_law == rxn.rate_law
    # a modifier outside the kept nodes is dropped, like a reactant would be
    assert sub.reactions["mm"].modifiers and not chem.subgraph(["S", "P", "mm"]).reactions["mm"].modifiers


# ── E2: validate checks modifiers ────────────────────────────────────────────


def test_validate_reports_a_modifier_missing_from_the_molecules() -> None:
    mols = {n: MoleculeImpl(n, dat=MockDat(f"mol/{n}")) for n in ("A", "B")}
    stray = MoleculeImpl("E", dat=MockDat("mol/E"))
    rxn = ReactionImpl(
        "r", reactants={mols["A"]: 1}, products={mols["B"]: 1},
        modifiers={stray: "catalyst"}, dat=MockDat("rxn/r"),
    )
    chem = ChemistryImpl("c", molecules=mols, reactions={"r": rxn}, dat=MockDat("chem/c"))
    assert chem.validate() == ["Reaction r: modifier E not in chemistry"]


# ── E3: a dict key must equal its entity's name ──────────────────────────────


def test_a_key_that_differs_from_its_entitys_name_refuses() -> None:
    glucose = MoleculeImpl("glucose", name="Glucose", dat=MockDat("mol/glucose"))
    with pytest.raises(ValueError, match="'glucose' differs from its entity's name 'Glucose'"):
        ChemistryImpl("c", molecules={"glucose": glucose}, dat=MockDat("chem/c"))
    a = MoleculeImpl("A", dat=MockDat("mol/A"))
    r = ReactionImpl("r1", reactants={a: 1}, products={}, dat=MockDat("rxn/r1"))
    with pytest.raises(ValueError, match="reaction key 'r2'"):
        ChemistryImpl("c", molecules={"A": a}, reactions={"r2": r}, dat=MockDat("chem/c"))
