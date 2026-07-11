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
