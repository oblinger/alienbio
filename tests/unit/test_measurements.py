"""Tests for M7.1 Measurement Protocol."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AllConcentrationsMeasurement,
    AtomImpl,
    ChemistryImpl,
    ConcentrationMeasurement,
    MoleculeCountMeasurement,
    MoleculeImpl,
    RateMeasurement,
    ReactionCountMeasurement,
    ReactionImpl,
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


class TestConcentrationMeasurement:

    def test_measure_known_concentration(self):
        """M7.1 key test: measure known state, assert correct concentration."""
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 7.5, "B": 2.5})
        m = ConcentrationMeasurement()
        assert m.measure(state, "A") == 7.5
        assert m.measure(state, "B") == 2.5

    def test_measure_zero(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 0.0, "B": 0.0})
        m = ConcentrationMeasurement()
        assert m.measure(state, "A") == 0.0

    def test_measure_unknown_raises(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 1.0})
        m = ConcentrationMeasurement()
        with pytest.raises(KeyError):
            m.measure(state, "nonexistent")

    def test_has_name_and_description(self):
        m = ConcentrationMeasurement()
        assert m.name == "concentration"
        assert len(m.description) > 0


class TestAllConcentrationsMeasurement:

    def test_returns_all(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 3.0, "B": 7.0})
        m = AllConcentrationsMeasurement()
        result = m.measure(state)
        assert result == {"A": 3.0, "B": 7.0}

    def test_returns_dict(self):
        chem = _make_chemistry()
        state = StateImpl(chem)
        m = AllConcentrationsMeasurement()
        result = m.measure(state)
        assert isinstance(result, dict)
        assert len(result) == 2


class TestRateMeasurement:

    def test_measure_rate(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        m = RateMeasurement()
        # rate = 0.1 * [A] = 0.1 * 10 = 1.0
        assert m.measure(state, "r1") == pytest.approx(1.0)

    def test_rate_depends_on_concentration(self):
        chem = _make_chemistry()
        m = RateMeasurement()
        s1 = StateImpl(chem, initial={"A": 5.0})
        s2 = StateImpl(chem, initial={"A": 20.0})
        assert m.measure(s1, "r1") == pytest.approx(0.5)
        assert m.measure(s2, "r1") == pytest.approx(2.0)

    def test_measure_unknown_reaction_raises(self):
        chem = _make_chemistry()
        state = StateImpl(chem, initial={"A": 1.0})
        m = RateMeasurement()
        with pytest.raises(KeyError):
            m.measure(state, "nonexistent")

    def test_has_name(self):
        m = RateMeasurement()
        assert m.name == "rate"


class TestMoleculeCountMeasurement:

    def test_count(self):
        chem = _make_chemistry()
        state = StateImpl(chem)
        m = MoleculeCountMeasurement()
        assert m.measure(state) == 2


class TestReactionCountMeasurement:

    def test_count(self):
        chem = _make_chemistry()
        state = StateImpl(chem)
        m = ReactionCountMeasurement()
        assert m.measure(state) == 1
