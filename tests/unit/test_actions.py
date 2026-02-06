"""Tests for M7.2 Action Protocol."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AddMoleculeAction,
    AdjustRateAction,
    AtomImpl,
    ChemistryImpl,
    MoleculeImpl,
    ReactionImpl,
    RemoveMoleculeAction,
    SetConcentrationAction,
    StateImpl,
)


class MockDat:
    def __init__(self, path: str):
        self._path = path
    def get_path_name(self) -> str:
        return self._path
    def get_path(self) -> str:
        return f"/tmp/{self._path}"
    def save(self) -> None:
        pass


def _make_chemistry():
    """Chemistry with A, B, and reaction r1: A -> B at rate 0.1*[A]."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
    r1 = ReactionImpl(
        "r1", reactants={a: 1.0}, products={b: 1.0},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/r1"),
    )
    return ChemistryImpl(
        "test", atoms={"C": carbon},
        molecules={"A": a, "B": b}, reactions={"r1": r1},
        dat=MockDat("chem/test"),
    )


class TestAddMoleculeAction:

    def test_add_increases_concentration(self):
        """M7.2 key test: add_molecule increases concentration by expected amount."""
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 5.0, "B": 3.0})
        action = AddMoleculeAction()
        new_state = action.apply(state, "A", 2.5)
        assert new_state["A"] == 7.5

    def test_does_not_modify_original(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 5.0})
        action = AddMoleculeAction()
        action.apply(state, "A", 10.0)
        assert state["A"] == 5.0

    def test_add_to_zero(self):
        chem = _make_chemistry()
        state = StateImpl(chem)
        action = AddMoleculeAction()
        new_state = action.apply(state, "B", 3.0)
        assert new_state["B"] == 3.0

    def test_other_molecules_unchanged(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 5.0, "B": 3.0})
        action = AddMoleculeAction()
        new_state = action.apply(state, "A", 1.0)
        assert new_state["B"] == 3.0

    def test_has_name(self):
        assert AddMoleculeAction.name == "add_molecule"


class TestRemoveMoleculeAction:

    def test_remove_decreases(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 10.0})
        action = RemoveMoleculeAction()
        new_state = action.apply(state, "A", 3.0)
        assert new_state["A"] == 7.0

    def test_clamps_at_zero(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 2.0})
        action = RemoveMoleculeAction()
        new_state = action.apply(state, "A", 10.0)
        assert new_state["A"] == 0.0

    def test_does_not_modify_original(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 5.0})
        action = RemoveMoleculeAction()
        action.apply(state, "A", 3.0)
        assert state["A"] == 5.0


class TestSetConcentrationAction:

    def test_set_value(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 5.0})
        action = SetConcentrationAction()
        new_state = action.apply(state, "A", 99.0)
        assert new_state["A"] == 99.0

    def test_set_to_zero(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 5.0})
        action = SetConcentrationAction()
        new_state = action.apply(state, "A", 0.0)
        assert new_state["A"] == 0.0

    def test_does_not_modify_original(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 5.0})
        action = SetConcentrationAction()
        action.apply(state, "A", 100.0)
        assert state["A"] == 5.0


class TestAdjustRateAction:

    def test_scale_rate_up(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 10.0})
        action = AdjustRateAction()
        # Original rate = 0.1*[A] = 1.0
        action.apply(state, "r1", 2.0)
        # New rate = 2.0 * 0.1 * [A] = 2.0
        new_rate = chem.reactions["r1"].get_rate(state)
        assert new_rate == pytest.approx(2.0)

    def test_scale_rate_down(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 10.0})
        action = AdjustRateAction()
        action.apply(state, "r1", 0.5)
        new_rate = chem.reactions["r1"].get_rate(state)
        assert new_rate == pytest.approx(0.5)

    def test_constant_rate_scaling(self):
        carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
        a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
        b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
        r1 = ReactionImpl(
            "r1", reactants={a: 1.0}, products={b: 1.0},
            rate=0.5,
            dat=MockDat("rxn/r1"),
        )
        chem = ChemistryImpl(
            "test", atoms={"C": carbon},
            molecules={"A": a, "B": b}, reactions={"r1": r1},
            dat=MockDat("chem/test"),
        )
        state = StateImpl(chem, initial={"A": 1.0})
        action = AdjustRateAction()
        action.apply(state, "r1", 3.0)
        assert chem.reactions["r1"].get_rate(state) == pytest.approx(1.5)

    def test_unknown_reaction_raises(self):
        chem = _make_chemistry()
        state = StateImpl(chem)
        action = AdjustRateAction()
        with pytest.raises(KeyError):
            action.apply(state, "nonexistent", 2.0)
