"""Tests for Reaction: entities representing chemical transformations."""

from __future__ import annotations

import pytest

from alienbio.bio import AtomImpl, MoleculeImpl, ReactionImpl


class MockDat:
    def __init__(self, path: str):
        self._path = path

    def get_path_name(self) -> str:
        return self._path

    def get_path(self) -> str:
        return f"/tmp/{self._path}"

    def save(self) -> None:
        pass


class TestReactionHydrateUnknownMolecule:
    """M8: hydrate must not silently drop unknown reactant/product references.

    A typo'd reactant/product name that isn't in `molecules` used to be
    silently skipped, turning the reaction into a spontaneous product
    generator (or a reactant-less sink). It must now raise.
    """

    def test_hydrate_unknown_reactant_string_raises(self):
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))

        with pytest.raises(KeyError, match="typo_reactant"):
            ReactionImpl.hydrate(
                {"reactants": ["typo_reactant"], "products": ["A"], "rate": 0.1},
                molecules={"A": a},
                local_name="r1",
            )

    def test_hydrate_unknown_product_string_raises(self):
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))

        with pytest.raises(KeyError, match="typo_product"):
            ReactionImpl.hydrate(
                {"reactants": ["A"], "products": ["typo_product"], "rate": 0.1},
                molecules={"A": a},
                local_name="r1",
            )

    def test_hydrate_unknown_reactant_dict_form_raises(self):
        """The {name: coef} form must also validate the molecule name."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))

        with pytest.raises(KeyError, match="ghost"):
            ReactionImpl.hydrate(
                {"reactants": [{"ghost": 2}], "products": ["A"]},
                molecules={"A": a},
                local_name="r1",
            )

    def test_hydrate_known_molecules_works(self):
        """Normal hydration with all-known molecule names still succeeds."""
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))

        rxn = ReactionImpl.hydrate(
            {"reactants": ["A"], "products": ["B"], "rate": 0.1},
            molecules={"A": a, "B": b},
            local_name="r1",
        )
        assert a in rxn.reactants
        assert b in rxn.products
        assert rxn.reactants[a] == 1


class TestReactionModifiers:
    """F008: catalysts/regulators are a first-class ``modifiers`` edge — molecules
    acting on a reaction without being stoichiometrically consumed."""

    def _mols(self):
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
        e = MoleculeImpl("E", atoms={carbon: 3}, bdepth=0, dat=MockDat("mol/E"))
        return a, b, e

    def test_modifier_not_a_reactant_or_product(self):
        """A modifier is neither consumed nor produced."""
        a, b, e = self._mols()
        rxn = ReactionImpl(
            "r1", reactants={a: 1.0}, products={b: 1.0},
            modifiers={e: "catalyst"}, dat=MockDat("rxn/r1"),
        )
        assert e not in rxn.reactants
        assert e not in rxn.products
        assert rxn.modifiers[e] == "catalyst"

    def test_empty_modifiers_default(self):
        """A reaction with no modifiers has an empty dict and omits the key."""
        a, b, _ = self._mols()
        rxn = ReactionImpl(
            "r1", reactants={a: 1.0}, products={b: 1.0}, dat=MockDat("rxn/r1")
        )
        assert rxn.modifiers == {}
        assert "modifiers" not in rxn.attributes()

    def test_modifiers_round_trip(self):
        """attributes() -> hydrate() preserves the modifier and its role tag."""
        a, b, e = self._mols()
        rxn = ReactionImpl(
            "r1", reactants={a: 1.0}, products={b: 1.0},
            modifiers={e: "catalyst"}, rate=0.3, dat=MockDat("rxn/r1"),
        )
        attrs = rxn.attributes()
        assert attrs["modifiers"] == {"E": "catalyst"}

        rebuilt = ReactionImpl.hydrate(
            attrs, molecules={"A": a, "B": b, "E": e}, local_name="r1"
        )
        assert {m.local_name: role for m, role in rebuilt.modifiers.items()} == {
            "E": "catalyst"
        }

    def test_hydrate_list_form_defaults_role(self):
        """A bare list of modifier names hydrates with an empty role tag."""
        a, b, e = self._mols()
        rxn = ReactionImpl.hydrate(
            {"reactants": ["A"], "products": ["B"], "modifiers": ["E"]},
            molecules={"A": a, "B": b, "E": e},
            local_name="r1",
        )
        assert {m.local_name: role for m, role in rxn.modifiers.items()} == {"E": ""}

    def test_hydrate_unknown_modifier_raises(self):
        """A modifier naming an unknown molecule must raise, not silently drop."""
        a, b, _ = self._mols()
        with pytest.raises(KeyError, match="ghost_enzyme"):
            ReactionImpl.hydrate(
                {"reactants": ["A"], "products": ["B"],
                 "modifiers": {"ghost_enzyme": "catalyst"}},
                molecules={"A": a, "B": b},
                local_name="r1",
            )
