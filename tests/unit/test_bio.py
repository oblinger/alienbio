"""Unit tests for bio module: BioMolecule, BioReaction, BioChemistry, State, Simulator."""

import pytest
from unittest.mock import MagicMock

from alienbio import (
    BioMolecule,
    BioReaction,
    BioChemistry,
    State,
    Simulator,
    SimpleSimulator,
    Entity,
    Context,
    set_context,
    ctx,
)
from alienbio.infra.entity import get_entity_type


class MockDat:
    """Mock DAT for testing."""

    def __init__(self, path: str):
        self._path = path

    def get_path_name(self) -> str:
        return self._path

    def get_path(self) -> str:
        return f"/tmp/{self._path}"

    def save(self) -> None:
        pass


class TestBioMolecule:
    """Tests for BioMolecule class."""

    def test_create_molecule_with_parent(self):
        """Create molecule as child of parent entity."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        mol = BioMolecule("glucose", parent=parent)

        assert mol.local_name == "glucose"
        assert mol.parent is parent
        assert "glucose" in parent.children

    def test_create_molecule_with_dat(self):
        """Create molecule as root entity."""
        dat = MockDat("molecules/glucose")
        mol = BioMolecule("glucose", dat=dat)

        assert mol.local_name == "glucose"
        assert mol.dat() is dat

    def test_molecule_properties(self):
        """Molecule stores arbitrary properties."""
        dat = MockDat("molecules/glucose")
        props = {"molecular_weight": 180.16, "formula": "C6H12O6"}
        mol = BioMolecule("glucose", dat=dat, properties=props)

        assert mol.properties == props
        assert mol.get_property("molecular_weight") == 180.16
        assert mol.get_property("missing", default=0) == 0

    def test_set_property(self):
        """Can update molecule properties."""
        dat = MockDat("molecules/glucose")
        mol = BioMolecule("glucose", dat=dat)
        mol.set_property("color", "white")

        assert mol.get_property("color") == "white"

    def test_properties_returns_copy(self):
        """Properties returns a copy, not original."""
        dat = MockDat("molecules/glucose")
        mol = BioMolecule("glucose", dat=dat, properties={"x": 1})

        props = mol.properties
        props["y"] = 2
        assert "y" not in mol.properties

    def test_molecule_to_dict(self):
        """to_dict includes properties."""
        dat = MockDat("molecules/glucose")
        mol = BioMolecule("glucose", dat=dat, properties={"weight": 180})

        d = mol.to_dict()
        assert d["type"] == "Molecule"
        assert d["name"] == "glucose"
        assert d["properties"] == {"weight": 180}

    def test_molecule_inherits_entity(self):
        """BioMolecule is an Entity."""
        dat = MockDat("molecules/glucose")
        mol = BioMolecule("glucose", dat=dat)

        assert isinstance(mol, Entity)

    def test_molecule_type_registered(self):
        """BioMolecule registered as 'Molecule'."""
        cls = get_entity_type("Molecule")
        assert cls is BioMolecule


class TestBioReaction:
    """Tests for BioReaction class."""

    def test_create_reaction(self):
        """Create reaction with reactants and products."""
        dat = MockDat("chemistry/glycolysis")
        chem = BioChemistry("glycolysis", dat=dat)
        glucose = BioMolecule("glucose", parent=chem)
        atp = BioMolecule("atp", parent=chem)

        reaction = BioReaction(
            "step1",
            reactants={glucose: 1},
            products={atp: 2},
            rate=0.1,
            parent=chem,
        )

        assert reaction.local_name == "step1"
        assert glucose in reaction.reactants
        assert atp in reaction.products
        assert reaction.rate == 0.1

    def test_reaction_stoichiometry(self):
        """Reaction stores stoichiometric coefficients."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)
        c = BioMolecule("C", parent=chem)

        # 2A + B -> 3C
        reaction = BioReaction(
            "r1",
            reactants={a: 2, b: 1},
            products={c: 3},
            parent=chem,
        )

        assert reaction.reactants[a] == 2
        assert reaction.reactants[b] == 1
        assert reaction.products[c] == 3

    def test_reaction_rate_constant(self):
        """Constant rate returns same value."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        reaction = BioReaction("r1", rate=0.5, parent=chem)

        state = State(chem)
        assert reaction.get_rate(state) == 0.5

    def test_reaction_rate_function(self):
        """Rate function called with state."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        mol = BioMolecule("enzyme", parent=chem)

        def rate_fn(state):
            return state["enzyme"] * 0.1

        reaction = BioReaction("r1", rate=rate_fn, parent=chem)

        state = State(chem, initial={"enzyme": 5.0})
        assert reaction.get_rate(state) == 0.5

    def test_add_reactant_product(self):
        """Can add reactants and products after creation."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)

        reaction = BioReaction("r1", parent=chem)
        reaction.add_reactant(a, 2)
        reaction.add_product(b, 1)

        assert reaction.reactants[a] == 2
        assert reaction.products[b] == 1

    def test_reaction_to_dict(self):
        """to_dict includes reactants, products, rate."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)

        reaction = BioReaction(
            "r1",
            reactants={a: 1},
            products={b: 1},
            rate=0.1,
            parent=chem,
        )

        d = reaction.to_dict()
        assert d["type"] == "Reaction"
        assert d["reactants"] == {"A": 1}
        assert d["products"] == {"B": 1}
        assert d["rate"] == 0.1

    def test_reaction_to_dict_omits_rate_function(self):
        """to_dict omits callable rate."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)

        reaction = BioReaction("r1", rate=lambda s: 0.1, parent=chem)

        d = reaction.to_dict()
        assert "rate" not in d

    def test_reaction_type_registered(self):
        """BioReaction registered as 'Reaction'."""
        cls = get_entity_type("Reaction")
        assert cls is BioReaction


class TestBioChemistry:
    """Tests for BioChemistry class."""

    def test_create_chemistry(self):
        """Create chemistry container."""
        dat = MockDat("chemistry/glycolysis")
        chem = BioChemistry("glycolysis", dat=dat, description="Sugar breakdown")

        assert chem.local_name == "glycolysis"
        assert chem.description == "Sugar breakdown"

    def test_chemistry_contains_molecules(self):
        """BioChemistry tracks molecule children."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        glucose = BioMolecule("glucose", parent=chem)
        atp = BioMolecule("atp", parent=chem)

        mols = chem.molecules
        assert "glucose" in mols
        assert "atp" in mols
        assert mols["glucose"] is glucose

    def test_chemistry_contains_reactions(self):
        """BioChemistry tracks reaction children."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)
        r1 = BioReaction("r1", parent=chem)
        r2 = BioReaction("r2", parent=chem)

        rxns = chem.reactions
        assert "r1" in rxns
        assert "r2" in rxns
        assert rxns["r1"] is r1

    def test_chemistry_filters_by_type(self):
        """molecules/reactions only return correct types."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        mol = BioMolecule("A", parent=chem)
        rxn = BioReaction("r1", parent=chem)
        # Also add a plain Entity
        plain = Entity("plain", parent=chem)

        assert "A" in chem.molecules
        assert "r1" not in chem.molecules

        assert "r1" in chem.reactions
        assert "A" not in chem.reactions

        # Plain entity in children but not in molecules/reactions
        assert "plain" in chem.children

    def test_chemistry_iter_molecules(self):
        """iter_molecules yields molecule children."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)
        BioMolecule("B", parent=chem)
        BioReaction("r1", parent=chem)

        mols = list(chem.iter_molecules())
        assert len(mols) == 2
        assert all(isinstance(m, BioMolecule) for m in mols)

    def test_chemistry_get_molecule(self):
        """get_molecule returns molecule by name."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        mol = BioMolecule("A", parent=chem)
        BioReaction("r1", parent=chem)

        assert chem.get_molecule("A") is mol
        assert chem.get_molecule("r1") is None  # reaction, not molecule
        assert chem.get_molecule("missing") is None

    def test_chemistry_validate_ok(self):
        """validate returns empty list for valid chemistry."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)
        BioReaction("r1", reactants={a: 1}, products={b: 1}, parent=chem)

        errors = chem.validate()
        assert errors == []

    def test_chemistry_validate_missing_reactant(self):
        """validate catches missing reactant."""
        dat1 = MockDat("chemistry/test1")
        dat2 = MockDat("chemistry/test2")
        chem1 = BioChemistry("test1", dat=dat1)
        chem2 = BioChemistry("test2", dat=dat2)

        a = BioMolecule("A", parent=chem1)  # in different chemistry!
        b = BioMolecule("B", parent=chem2)

        BioReaction("r1", reactants={a: 1}, products={b: 1}, parent=chem2)

        errors = chem2.validate()
        assert len(errors) == 1
        assert "reactant A not in chemistry" in errors[0]

    def test_chemistry_to_dict(self):
        """to_dict includes counts."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)
        BioMolecule("B", parent=chem)
        BioReaction("r1", parent=chem)

        d = chem.to_dict()
        assert d["type"] == "BioChemistry"
        assert d["molecule_count"] == 2
        assert d["reaction_count"] == 1

    def test_chemistry_type_registered(self):
        """BioChemistry registered as 'BioChemistry'."""
        cls = get_entity_type("BioChemistry")
        assert cls is BioChemistry


class TestState:
    """Tests for State class."""

    def test_create_state(self):
        """Create state for chemistry."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)
        BioMolecule("B", parent=chem)

        state = State(chem)

        assert state.chemistry is chem
        assert "A" in state
        assert "B" in state
        assert state["A"] == 0.0  # default

    def test_state_initial_values(self):
        """Create state with initial concentrations."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)
        BioMolecule("B", parent=chem)

        state = State(chem, initial={"A": 1.0, "B": 2.0})

        assert state["A"] == 1.0
        assert state["B"] == 2.0

    def test_state_setitem(self):
        """Can set concentration values."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)

        state = State(chem)
        state["A"] = 5.0

        assert state["A"] == 5.0

    def test_state_unknown_molecule_raises(self):
        """Setting unknown molecule raises KeyError."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)

        state = State(chem)
        with pytest.raises(KeyError, match="Unknown molecule"):
            state["X"] = 1.0

    def test_state_initial_unknown_raises(self):
        """Initial with unknown molecule raises KeyError."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)

        with pytest.raises(KeyError, match="Unknown molecule"):
            State(chem, initial={"X": 1.0})

    def test_state_get_default(self):
        """get returns default for missing keys."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)

        state = State(chem)
        assert state.get("missing", 99) == 99

    def test_state_molecule_access(self):
        """Can access by molecule object."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        mol = BioMolecule("A", parent=chem)

        state = State(chem, initial={"A": 3.0})

        assert state.get_molecule(mol) == 3.0

        state.set_molecule(mol, 5.0)
        assert state["A"] == 5.0

    def test_state_iter(self):
        """Can iterate over molecule names."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)
        BioMolecule("B", parent=chem)

        state = State(chem)
        names = list(state)

        assert "A" in names
        assert "B" in names

    def test_state_len(self):
        """len returns number of molecules."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)
        BioMolecule("B", parent=chem)

        state = State(chem)
        assert len(state) == 2

    def test_state_copy(self):
        """copy creates independent state."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)

        state1 = State(chem, initial={"A": 1.0})
        state2 = state1.copy()

        state2["A"] = 5.0
        assert state1["A"] == 1.0  # unchanged

    def test_state_to_dict(self):
        """to_dict for serialization."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)

        state = State(chem, initial={"A": 1.0})
        d = state.to_dict()

        assert d["chemistry"] == "test"
        assert d["concentrations"]["A"] == 1.0

    def test_state_from_dict(self):
        """from_dict recreates state."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        BioMolecule("A", parent=chem)

        data = {"concentrations": {"A": 2.0}}
        state = State.from_dict(chem, data)

        assert state["A"] == 2.0


class TestSimulator:
    """Tests for Simulator class."""

    def test_simple_simulator_step(self):
        """SimpleSimulator applies reactions once."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)

        # A -> B with rate 0.1
        BioReaction("r1", reactants={a: 1}, products={b: 1}, rate=0.1, parent=chem)

        state = State(chem, initial={"A": 10.0, "B": 0.0})
        sim = SimpleSimulator(chem, dt=1.0)

        new_state = sim.step(state)

        assert new_state["A"] == pytest.approx(9.9)
        assert new_state["B"] == pytest.approx(0.1)

    def test_simulator_step_stoichiometry(self):
        """Simulator respects stoichiometry."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)

        # 2A -> B with rate 0.5
        BioReaction("r1", reactants={a: 2}, products={b: 1}, rate=0.5, parent=chem)

        state = State(chem, initial={"A": 10.0, "B": 0.0})
        sim = SimpleSimulator(chem, dt=1.0)

        new_state = sim.step(state)

        # rate * coef: A decreases by 0.5*2=1.0, B increases by 0.5*1=0.5
        assert new_state["A"] == pytest.approx(9.0)
        assert new_state["B"] == pytest.approx(0.5)

    def test_simulator_step_no_negative(self):
        """Simulator clamps reactants to 0."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)

        # A -> B with high rate
        BioReaction("r1", reactants={a: 1}, products={b: 1}, rate=100, parent=chem)

        state = State(chem, initial={"A": 1.0, "B": 0.0})
        sim = SimpleSimulator(chem, dt=1.0)

        new_state = sim.step(state)

        assert new_state["A"] >= 0  # clamped
        assert new_state["B"] == pytest.approx(100.0)

    def test_simulator_run(self):
        """run returns timeline of states."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)

        BioReaction("r1", reactants={a: 1}, products={b: 1}, rate=0.1, parent=chem)

        state = State(chem, initial={"A": 10.0, "B": 0.0})
        sim = SimpleSimulator(chem, dt=1.0)

        timeline = sim.run(state, steps=10)

        assert len(timeline) == 11  # initial + 10 steps
        assert timeline[0]["A"] == 10.0
        assert timeline[-1]["A"] < 10.0  # decreased
        assert timeline[-1]["B"] > 0.0  # increased

    def test_simulator_run_preserves_initial(self):
        """run doesn't modify initial state."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)

        BioReaction("r1", reactants={a: 1}, products={b: 1}, rate=0.1, parent=chem)

        state = State(chem, initial={"A": 10.0, "B": 0.0})
        sim = SimpleSimulator(chem, dt=1.0)

        sim.run(state, steps=10)

        assert state["A"] == 10.0  # unchanged

    def test_simulator_dt(self):
        """dt affects reaction magnitude."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem)
        b = BioMolecule("B", parent=chem)

        BioReaction("r1", reactants={a: 1}, products={b: 1}, rate=0.1, parent=chem)

        state = State(chem, initial={"A": 10.0, "B": 0.0})

        # dt=0.5 should halve the effect
        sim = SimpleSimulator(chem, dt=0.5)
        new_state = sim.step(state)

        assert new_state["A"] == pytest.approx(9.95)  # 10 - 0.1*0.5
        assert new_state["B"] == pytest.approx(0.05)


class TestIntegration:
    """Integration tests for bio module."""

    def test_full_chemistry_simulation(self):
        """End-to-end test: build chemistry, simulate, check results."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("glycolysis", dat=dat, description="Simplified glycolysis")

        # Create molecules
        glucose = BioMolecule("glucose", parent=chem)
        pyruvate = BioMolecule("pyruvate", parent=chem)
        atp = BioMolecule("atp", parent=chem)

        # Glucose -> 2 Pyruvate + 2 ATP
        BioReaction(
            "glycolysis_step",
            reactants={glucose: 1},
            products={pyruvate: 2, atp: 2},
            rate=0.1,
            parent=chem,
        )

        # Validate chemistry
        errors = chem.validate()
        assert errors == []

        # Create initial state
        state = State(chem, initial={"glucose": 10.0, "pyruvate": 0.0, "atp": 0.0})

        # Run simulation
        sim = SimpleSimulator(chem, dt=1.0)
        timeline = sim.run(state, steps=50)

        # Check results
        final = timeline[-1]
        assert final["glucose"] < 10.0  # consumed
        assert final["pyruvate"] > 0.0  # produced
        assert final["atp"] > 0.0  # produced
        assert final["pyruvate"] == final["atp"]  # equal amounts

    def test_entity_tree_structure(self):
        """BioChemistry maintains proper entity tree structure."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        mol = BioMolecule("A", parent=chem)
        rxn = BioReaction("r1", parent=chem)

        # All are in same tree
        assert mol.root() is chem
        assert rxn.root() is chem

        # Parent relationships correct
        assert mol.parent is chem
        assert rxn.parent is chem

        # All share same dat
        assert mol.dat() is dat
        assert rxn.dat() is dat

    def test_chemistry_serialization_roundtrip(self):
        """BioChemistry can be serialized and inspected."""
        dat = MockDat("chemistry/test")
        chem = BioChemistry("test", dat=dat)
        a = BioMolecule("A", parent=chem, properties={"weight": 100})
        b = BioMolecule("B", parent=chem)
        BioReaction("r1", reactants={a: 1}, products={b: 1}, rate=0.1, parent=chem)

        # Serialize
        d = chem.to_dict(recursive=True)

        # Check structure
        assert d["type"] == "BioChemistry"
        assert d["molecule_count"] == 2
        assert d["reaction_count"] == 1
        assert "children" in d
        assert "A" in d["children"]
        assert "r1" in d["children"]
        assert d["children"]["A"]["properties"] == {"weight": 100}
