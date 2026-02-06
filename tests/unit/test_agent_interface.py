"""Tests for M7.3 Agent Interface."""

from __future__ import annotations

import pytest

from alienbio.bio import (
    AgentInterface,
    AtomImpl,
    BioSystem,
    ChemistryImpl,
    MoleculeImpl,
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


def _make_system() -> BioSystem:
    """BioSystem with A, B and reaction r1: A -> B at rate 0.1*[A]."""
    carbon = AtomImpl("C", name="Carbon", atomic_weight=12.0)
    a = MoleculeImpl("A", atoms={carbon: 1}, bdepth=0, dat=MockDat("mol/A"))
    b = MoleculeImpl("B", atoms={carbon: 2}, bdepth=0, dat=MockDat("mol/B"))
    r1 = ReactionImpl(
        "r1", reactants={a: 1.0}, products={b: 1.0},
        rate=lambda state: 0.1 * state["A"],
        dat=MockDat("rxn/r1"),
    )
    chem = ChemistryImpl(
        "test", atoms={"C": carbon},
        molecules={"A": a, "B": b}, reactions={"r1": r1},
        dat=MockDat("chem/test"),
    )
    state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
    return BioSystem(chem, state, dt=0.1)


# === Available measurements and actions ===

class TestAvailable:

    def test_available_measurements(self):
        iface = AgentInterface(_make_system())
        measurements = iface.available_measurements()
        names = {m["name"] for m in measurements}
        assert "concentration" in names
        assert "all_concentrations" in names
        assert "rate" in names
        assert "molecule_count" in names
        assert "reaction_count" in names

    def test_available_actions(self):
        iface = AgentInterface(_make_system())
        actions = iface.available_actions()
        names = {a["name"] for a in actions}
        assert "add_molecule" in names
        assert "remove_molecule" in names
        assert "set_concentration" in names
        assert "adjust_rate" in names

    def test_measurements_have_descriptions(self):
        iface = AgentInterface(_make_system())
        for m in iface.available_measurements():
            assert "description" in m
            assert len(m["description"]) > 0

    def test_actions_have_descriptions(self):
        iface = AgentInterface(_make_system())
        for a in iface.available_actions():
            assert "description" in a
            assert len(a["description"]) > 0

    def test_measurements_have_params(self):
        iface = AgentInterface(_make_system())
        for m in iface.available_measurements():
            assert "params" in m


# === Measure via API ===

class TestMeasure:

    def test_measure_concentration(self):
        """M7.3 key test: call API method, assert valid response."""
        iface = AgentInterface(_make_system())
        assert iface.measure("concentration", molecule="A") == 10.0
        assert iface.measure("concentration", molecule="B") == 0.0

    def test_measure_all_concentrations(self):
        iface = AgentInterface(_make_system())
        result = iface.measure("all_concentrations")
        assert result == {"A": 10.0, "B": 0.0}

    def test_measure_rate(self):
        iface = AgentInterface(_make_system())
        rate = iface.measure("rate", reaction_name="r1")
        assert rate == pytest.approx(1.0)  # 0.1 * 10.0

    def test_measure_molecule_count(self):
        iface = AgentInterface(_make_system())
        assert iface.measure("molecule_count") == 2

    def test_measure_reaction_count(self):
        iface = AgentInterface(_make_system())
        assert iface.measure("reaction_count") == 1

    def test_measure_unknown_raises(self):
        iface = AgentInterface(_make_system())
        with pytest.raises(KeyError):
            iface.measure("nonexistent")


# === Act via API ===

class TestAct:

    def test_act_add_molecule(self):
        """M7.3 key test: call API method, assert state change."""
        iface = AgentInterface(_make_system())
        iface.act("add_molecule", molecule="A", amount=5.0)
        assert iface.system.state["A"] == 15.0

    def test_act_remove_molecule(self):
        iface = AgentInterface(_make_system())
        iface.act("remove_molecule", molecule="A", amount=3.0)
        assert iface.system.state["A"] == 7.0

    def test_act_set_concentration(self):
        iface = AgentInterface(_make_system())
        iface.act("set_concentration", molecule="B", value=99.0)
        assert iface.system.state["B"] == 99.0

    def test_act_updates_system_state(self):
        system = _make_system()
        iface = AgentInterface(system)
        iface.act("add_molecule", molecule="B", amount=5.0)
        # State is updated on the system itself
        assert system.state["B"] == 5.0

    def test_act_unknown_raises(self):
        iface = AgentInterface(_make_system())
        with pytest.raises(KeyError):
            iface.act("nonexistent")

    def test_measure_after_act_reflects_change(self):
        iface = AgentInterface(_make_system())
        iface.act("add_molecule", molecule="A", amount=10.0)
        assert iface.measure("concentration", molecule="A") == 20.0


# === Describe ===

class TestDescribe:

    def test_describe_returns_string(self):
        iface = AgentInterface(_make_system())
        desc = iface.describe()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_describe_lists_measurements(self):
        iface = AgentInterface(_make_system())
        desc = iface.describe()
        assert "concentration" in desc
        assert "rate" in desc

    def test_describe_lists_actions(self):
        iface = AgentInterface(_make_system())
        desc = iface.describe()
        assert "add_molecule" in desc
        assert "set_concentration" in desc

    def test_describe_includes_params(self):
        iface = AgentInterface(_make_system())
        desc = iface.describe()
        assert "molecule" in desc
