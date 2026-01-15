"""Unit tests for bio module: Molecule, Reaction, Chemistry, State, Simulator."""

import pytest
from unittest.mock import MagicMock

from alienbio import (
    # Protocols (for type checking)
    Atom,
    Molecule,
    Reaction,
    Chemistry,
    State,
    Simulator,
    # Implementation classes (for instantiation)
    AtomImpl,
    MoleculeImpl,
    ReactionImpl,
    ChemistryImpl,
    StateImpl,
    ReferenceSimulatorImpl,
    # Atom utilities
    COMMON_ATOMS,
    get_atom,
    # Other
    Entity,
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


class TestAtom:
    """Tests for Atom class."""

    def test_create_atom(self):
        """Create atom with properties."""
        atom = AtomImpl("C", "Carbon", 12.011)

        assert atom.symbol == "C"
        assert atom.name == "Carbon"
        assert atom.atomic_weight == 12.011

    def test_atom_invalid_symbol(self):
        """Symbol must be 1-2 characters."""
        with pytest.raises(ValueError, match="1-2 characters"):
            AtomImpl("ABC", "Invalid", 1.0)

    def test_atom_equality(self):
        """Atoms are equal if same symbol."""
        atom1 = AtomImpl("C", "Carbon", 12.011)
        atom2 = AtomImpl("C", "Carbon", 12.011)

        assert atom1 == atom2

    def test_atom_hash(self):
        """Atoms can be dict keys."""
        atom1 = AtomImpl("C", "Carbon", 12.011)
        atom2 = AtomImpl("C", "Carbon", 12.011)

        d = {atom1: 6}
        assert d[atom2] == 6

    def test_common_atoms(self):
        """COMMON_ATOMS contains expected elements."""
        assert "C" in COMMON_ATOMS
        assert "H" in COMMON_ATOMS
        assert "O" in COMMON_ATOMS
        assert "N" in COMMON_ATOMS

        assert COMMON_ATOMS["C"].name == "Carbon"
        assert COMMON_ATOMS["H"].atomic_weight == pytest.approx(1.008)

    def test_get_atom(self):
        """get_atom retrieves by symbol."""
        carbon = get_atom("C")
        assert carbon.symbol == "C"
        assert carbon.name == "Carbon"

    def test_get_atom_unknown(self):
        """get_atom raises for unknown symbol."""
        with pytest.raises(KeyError, match="Unknown atom"):
            get_atom("Xx")


class TestMolecule:
    """Tests for Molecule class."""

    def test_create_molecule_with_parent(self):
        """Create molecule as child of parent entity."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        mol = MoleculeImpl("glucose", parent=parent)

        assert mol.local_name == "glucose"
        assert mol.parent is parent
        assert "glucose" in parent.children

    def test_create_molecule_with_dat(self):
        """Create molecule as root entity."""
        dat = MockDat("molecules/glucose")
        mol = MoleculeImpl("glucose", dat=dat)

        assert mol.local_name == "glucose"
        assert mol.dat() is dat

    def test_molecule_atoms(self):
        """Molecule stores atom composition."""
        dat = MockDat("molecules/glucose")
        C = get_atom("C")
        H = get_atom("H")
        O = get_atom("O")
        atoms = {C: 6, H: 12, O: 6}
        mol = MoleculeImpl("glucose", dat=dat, atoms=atoms, name="Glucose")

        assert mol.atoms == atoms
        assert mol.name == "Glucose"
        assert mol.symbol == "C6H12O6"
        assert mol.molecular_weight == pytest.approx(180.156)  # 6*12.011 + 12*1.008 + 6*15.999

    def test_molecule_bdepth(self):
        """Molecule has biosynthetic depth."""
        dat = MockDat("molecules/glucose")
        mol = MoleculeImpl("glucose", dat=dat, bdepth=2)

        assert mol.bdepth == 2

    def test_atoms_returns_copy(self):
        """atoms returns a copy, not original."""
        dat = MockDat("molecules/water")
        H = get_atom("H")
        O = get_atom("O")
        mol = MoleculeImpl("water", dat=dat, atoms={H: 2, O: 1})

        atoms = mol.atoms
        atoms[get_atom("C")] = 1
        assert get_atom("C") not in mol.atoms

    def test_molecule_to_dict(self):
        """to_dict includes atoms."""
        dat = MockDat("molecules/water")
        H = get_atom("H")
        O = get_atom("O")
        mol = MoleculeImpl("water", dat=dat, atoms={H: 2, O: 1}, name="Water")

        d = mol.to_dict()
        assert d["head"] == "Molecule"
        assert d["name"] == "water"  # local_name from Entity
        assert d["display_name"] == "Water"  # human-readable name when different
        assert d["atoms"] == {"H": 2, "O": 1}

    def test_molecule_inherits_entity(self):
        """MoleculeImpl is an Entity."""
        dat = MockDat("molecules/glucose")
        mol = MoleculeImpl("glucose", dat=dat)

        assert isinstance(mol, Entity)

    def test_molecule_type_registered(self):
        """MoleculeImpl registered as 'Molecule'."""
        cls = get_entity_type("Molecule")
        assert cls is MoleculeImpl


class TestReaction:
    """Tests for Reaction class."""

    def test_create_reaction(self):
        """Create reaction with reactants and products."""
        dat = MockDat("reactions/step1")
        glucose = MoleculeImpl("glucose", dat=MockDat("mol/glucose"))
        atp = MoleculeImpl("atp", dat=MockDat("mol/atp"))

        reaction = ReactionImpl(
            "step1",
            reactants={glucose: 1},
            products={atp: 2},
            rate=0.1,
            dat=dat,
        )

        assert reaction.local_name == "step1"
        assert reaction.name == "step1"
        assert glucose in reaction.reactants
        assert atp in reaction.products
        assert reaction.rate == 0.1

    def test_reaction_symbol(self):
        """Reaction symbol is formula string."""
        glucose = MoleculeImpl("glucose", dat=MockDat("mol/glucose"))
        atp = MoleculeImpl("atp", dat=MockDat("mol/atp"))
        adp = MoleculeImpl("adp", dat=MockDat("mol/adp"))

        reaction = ReactionImpl(
            "step1",
            reactants={glucose: 1, atp: 1},
            products={adp: 2},
            dat=MockDat("reactions/step1"),
        )

        # symbol is "reactant + reactant -> product + product"
        assert "->" in reaction.symbol
        assert "glucose" in reaction.symbol or "atp" in reaction.symbol

    def test_reaction_stoichiometry(self):
        """Reaction stores stoichiometric coefficients."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        c = MoleculeImpl("C", dat=MockDat("mol/C"))

        # 2A + B -> 3C
        reaction = ReactionImpl(
            "r1",
            reactants={a: 2, b: 1},
            products={c: 3},
            dat=MockDat("reactions/r1"),
        )

        assert reaction.reactants[a] == 2
        assert reaction.reactants[b] == 1
        assert reaction.products[c] == 3

    def test_reaction_rate_constant(self):
        """Constant rate returns same value."""
        dat = MockDat("chemistry/test")
        chem = ChemistryImpl("test", dat=dat)
        reaction = ReactionImpl("r1", rate=0.5, dat=MockDat("reactions/r1"))

        state = StateImpl(chem)
        assert reaction.get_rate(state) == 0.5

    def test_reaction_rate_function(self):
        """Rate function called with state."""
        enzyme = MoleculeImpl("enzyme", dat=MockDat("mol/enzyme"))
        chem = ChemistryImpl(
            "test",
            molecules={"enzyme": enzyme},
            dat=MockDat("chemistry/test"),
        )

        def rate_fn(state):
            return state["enzyme"] * 0.1

        reaction = ReactionImpl("r1", rate=rate_fn, dat=MockDat("reactions/r1"))

        state = StateImpl(chem, initial={"enzyme": 5.0})
        assert reaction.get_rate(state) == 0.5

    def test_add_reactant_product(self):
        """Can add reactants and products after creation."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        reaction = ReactionImpl("r1", dat=MockDat("reactions/r1"))
        reaction.add_reactant(a, 2)
        reaction.add_product(b, 1)

        assert reaction.reactants[a] == 2
        assert reaction.products[b] == 1

    def test_reaction_to_dict(self):
        """to_dict includes reactants, products, rate."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        reaction = ReactionImpl(
            "r1",
            reactants={a: 1},
            products={b: 1},
            rate=0.1,
            dat=MockDat("reactions/r1"),
        )

        d = reaction.to_dict()
        assert d["head"] == "Reaction"
        assert d["reactants"] == {"A": 1}
        assert d["products"] == {"B": 1}
        assert d["rate"] == 0.1

    def test_reaction_to_dict_omits_rate_function(self):
        """to_dict omits callable rate."""
        reaction = ReactionImpl("r1", rate=lambda s: 0.1, dat=MockDat("reactions/r1"))

        d = reaction.to_dict()
        assert "rate" not in d

    def test_reaction_type_registered(self):
        """ReactionImpl registered as 'Reaction'."""
        cls = get_entity_type("Reaction")
        assert cls is ReactionImpl


class TestChemistry:
    """Tests for Chemistry class."""

    def test_create_chemistry(self):
        """Create chemistry container."""
        dat = MockDat("chemistry/glycolysis")
        chem = ChemistryImpl("glycolysis", dat=dat, description="Sugar breakdown")

        assert chem.local_name == "glycolysis"
        assert chem.description == "Sugar breakdown"

    def test_chemistry_with_atoms(self):
        """Chemistry stores atoms dict."""
        C = AtomImpl("C", "Carbon", 12.011)
        H = AtomImpl("H", "Hydrogen", 1.008)
        O = AtomImpl("O", "Oxygen", 15.999)

        chem = ChemistryImpl(
            "test",
            atoms={"C": C, "H": H, "O": O},
            dat=MockDat("chemistry/test"),
        )

        assert len(chem.atoms) == 3
        assert chem.atoms["C"].name == "Carbon"

    def test_chemistry_with_molecules(self):
        """Chemistry stores molecules dict."""
        glucose = MoleculeImpl("glucose", dat=MockDat("mol/glucose"))
        atp = MoleculeImpl("atp", dat=MockDat("mol/atp"))

        chem = ChemistryImpl(
            "test",
            molecules={"glucose": glucose, "atp": atp},
            dat=MockDat("chemistry/test"),
        )

        assert len(chem.molecules) == 2
        assert chem.molecules["glucose"] is glucose
        assert chem.molecules["atp"] is atp

    def test_chemistry_with_reactions(self):
        """Chemistry stores reactions dict."""
        glucose = MoleculeImpl("glucose", dat=MockDat("mol/glucose"))
        pyruvate = MoleculeImpl("pyruvate", dat=MockDat("mol/pyruvate"))

        r1 = ReactionImpl(
            "step1",
            reactants={glucose: 1},
            products={pyruvate: 2},
            dat=MockDat("reactions/step1"),
        )

        chem = ChemistryImpl(
            "glycolysis",
            molecules={"glucose": glucose, "pyruvate": pyruvate},
            reactions={"step1": r1},
            dat=MockDat("chemistry/test"),
        )

        assert len(chem.reactions) == 1
        assert chem.reactions["step1"] is r1

    def test_chemistry_validate_ok(self):
        """validate returns empty list for valid chemistry."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        errors = chem.validate()
        assert errors == []

    def test_chemistry_validate_missing_reactant(self):
        """validate catches missing reactant."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))

        # Reaction uses 'a' but it's not in molecules dict
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            molecules={"B": b},  # Missing A!
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        errors = chem.validate()
        assert len(errors) == 1
        assert "reactant A not in chemistry" in errors[0]

    def test_chemistry_validate_missing_atom(self):
        """validate catches missing atom in molecule."""
        C = get_atom("C")
        H = get_atom("H")
        O = get_atom("O")

        # Molecule uses C, H, O but chemistry only has C, H
        mol = MoleculeImpl("water", dat=MockDat("mol/water"), atoms={H: 2, O: 1})

        chem = ChemistryImpl(
            "test",
            atoms={"C": C, "H": H},  # Missing O!
            molecules={"water": mol},
            dat=MockDat("chemistry/test"),
        )

        errors = chem.validate()
        assert len(errors) == 1
        assert "atom O not in chemistry" in errors[0]

    def test_chemistry_to_dict(self):
        """to_dict includes atoms, molecules, reactions."""
        C = get_atom("C")
        H = get_atom("H")
        a = MoleculeImpl("A", dat=MockDat("mol/A"), atoms={C: 1, H: 4})
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            atoms={"C": C, "H": H},
            molecules={"A": a, "B": b},
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        d = chem.to_dict()
        assert d["head"] == "Chemistry"
        assert "atoms" in d
        assert "molecules" in d
        assert "reactions" in d
        assert d["atoms"]["C"]["name"] == "Carbon"

    def test_chemistry_type_registered(self):
        """ChemistryImpl registered as 'Chemistry'."""
        cls = get_entity_type("Chemistry")
        assert cls is ChemistryImpl


class TestState:
    """Tests for State class."""

    def test_create_state(self):
        """Create state for chemistry."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem)

        assert state.chemistry is chem
        assert "A" in state
        assert "B" in state
        assert state["A"] == 0.0  # default

    def test_state_initial_values(self):
        """Create state with initial concentrations."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem, initial={"A": 1.0, "B": 2.0})

        assert state["A"] == 1.0
        assert state["B"] == 2.0

    def test_state_setitem(self):
        """Can set concentration values."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem)
        state["A"] = 5.0

        assert state["A"] == 5.0

    def test_state_unknown_molecule_raises(self):
        """Setting unknown molecule raises KeyError."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem)
        with pytest.raises(KeyError, match="Unknown molecule"):
            state["X"] = 1.0

    def test_state_initial_unknown_raises(self):
        """Initial with unknown molecule raises KeyError."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a},
            dat=MockDat("chemistry/test"),
        )

        with pytest.raises(KeyError, match="Unknown molecule"):
            StateImpl(chem, initial={"X": 1.0})

    def test_state_get_default(self):
        """get returns default for missing keys."""
        chem = ChemistryImpl("test", dat=MockDat("chemistry/test"))

        state = StateImpl(chem)
        assert state.get("missing", 99) == 99

    def test_state_molecule_access(self):
        """Can access by molecule object."""
        mol = MoleculeImpl("A", dat=MockDat("mol/A"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": mol},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem, initial={"A": 3.0})

        assert state.get_molecule(mol) == 3.0

        state.set_molecule(mol, 5.0)
        assert state["A"] == 5.0

    def test_state_iter(self):
        """Can iterate over molecule names."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem)
        names = list(state)

        assert "A" in names
        assert "B" in names

    def test_state_len(self):
        """len returns number of molecules."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem)
        assert len(state) == 2

    def test_state_copy(self):
        """copy creates independent state."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a},
            dat=MockDat("chemistry/test"),
        )

        state1 = StateImpl(chem, initial={"A": 1.0})
        state2 = state1.copy()

        state2["A"] = 5.0
        assert state1["A"] == 1.0  # unchanged

    def test_state_to_dict(self):
        """to_dict for serialization."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem, initial={"A": 1.0})
        d = state.to_dict()

        assert d["chemistry"] == "test"
        assert d["concentrations"]["A"] == 1.0

    def test_state_from_dict(self):
        """from_dict recreates state."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        chem = ChemistryImpl(
            "test",
            molecules={"A": a},
            dat=MockDat("chemistry/test"),
        )

        data = {"concentrations": {"A": 2.0}}
        state = StateImpl.from_dict(chem, data)

        assert state["A"] == 2.0


class TestSimulator:
    """Tests for Simulator class."""

    def test_simple_simulator_step(self):
        """ReferenceSimulatorImpl applies reactions once."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        new_state = sim.step(state)

        assert new_state["A"] == pytest.approx(9.9)
        assert new_state["B"] == pytest.approx(0.1)

    def test_simulator_step_stoichiometry(self):
        """Simulator respects stoichiometry."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 2}, products={b: 1}, rate=0.5, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        new_state = sim.step(state)

        # rate * coef: A decreases by 0.5*2=1.0, B increases by 0.5*1=0.5
        assert new_state["A"] == pytest.approx(9.0)
        assert new_state["B"] == pytest.approx(0.5)

    def test_simulator_step_no_negative(self):
        """Simulator clamps reactants to 0."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=100, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem, initial={"A": 1.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        new_state = sim.step(state)

        assert new_state["A"] >= 0  # clamped
        assert new_state["B"] == pytest.approx(100.0)

    def test_simulator_run(self):
        """run returns timeline of states."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        timeline = sim.run(state, steps=10)

        assert len(timeline) == 11  # initial + 10 steps
        assert timeline[0]["A"] == 10.0
        assert timeline[-1]["A"] < 10.0  # decreased
        assert timeline[-1]["B"] > 0.0  # increased

    def test_simulator_run_preserves_initial(self):
        """run doesn't modify initial state."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})
        sim = ReferenceSimulatorImpl(chem, dt=1.0)

        sim.run(state, steps=10)

        assert state["A"] == 10.0  # unchanged

    def test_simulator_dt(self):
        """dt affects reaction magnitude."""
        a = MoleculeImpl("A", dat=MockDat("mol/A"))
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            molecules={"A": a, "B": b},
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        state = StateImpl(chem, initial={"A": 10.0, "B": 0.0})

        # dt=0.5 should halve the effect
        sim = ReferenceSimulatorImpl(chem, dt=0.5)
        new_state = sim.step(state)

        assert new_state["A"] == pytest.approx(9.95)  # 10 - 0.1*0.5
        assert new_state["B"] == pytest.approx(0.05)


class TestIntegration:
    """Integration tests for bio module."""

    def test_full_chemistry_simulation(self):
        """End-to-end test: build chemistry, simulate, check results."""
        # Create molecules
        glucose = MoleculeImpl("glucose", dat=MockDat("mol/glucose"))
        pyruvate = MoleculeImpl("pyruvate", dat=MockDat("mol/pyruvate"))
        atp = MoleculeImpl("atp", dat=MockDat("mol/atp"))

        # Create reaction: Glucose -> 2 Pyruvate + 2 ATP
        r1 = ReactionImpl(
            "glycolysis_step",
            reactants={glucose: 1},
            products={pyruvate: 2, atp: 2},
            rate=0.1,
            dat=MockDat("rxn/glycolysis_step"),
        )

        # Build chemistry
        chem = ChemistryImpl(
            "glycolysis",
            molecules={"glucose": glucose, "pyruvate": pyruvate, "atp": atp},
            reactions={"glycolysis_step": r1},
            dat=MockDat("chemistry/glycolysis"),
            description="Simplified glycolysis",
        )

        # Validate chemistry
        errors = chem.validate()
        assert errors == []

        # Create initial state
        state = StateImpl(chem, initial={"glucose": 10.0, "pyruvate": 0.0, "atp": 0.0})

        # Run simulation
        sim = ReferenceSimulatorImpl(chem, dt=1.0)
        timeline = sim.run(state, steps=50)

        # Check results
        final = timeline[-1]
        assert final["glucose"] < 10.0  # consumed
        assert final["pyruvate"] > 0.0  # produced
        assert final["atp"] > 0.0  # produced
        assert final["pyruvate"] == final["atp"]  # equal amounts

    def test_entity_tree_structure(self):
        """Molecules in chemistry are standalone entities."""
        glucose = MoleculeImpl("glucose", dat=MockDat("mol/glucose"))
        atp = MoleculeImpl("atp", dat=MockDat("mol/atp"))

        chem = ChemistryImpl(
            "test",
            molecules={"glucose": glucose, "atp": atp},
            dat=MockDat("chemistry/test"),
        )

        # Molecules are not children of chemistry
        assert "glucose" not in chem.children
        assert "atp" not in chem.children

        # But they're in the molecules dict
        assert chem.molecules["glucose"] is glucose
        assert chem.molecules["atp"] is atp

        # Chemistry is still an entity with its own dat
        assert chem.dat().get_path_name() == "chemistry/test"

    def test_chemistry_serialization(self):
        """Chemistry can be serialized."""
        C = get_atom("C")
        H = get_atom("H")
        O = get_atom("O")

        a = MoleculeImpl("A", dat=MockDat("mol/A"), atoms={C: 1, H: 4}, bdepth=1)
        b = MoleculeImpl("B", dat=MockDat("mol/B"))
        r1 = ReactionImpl("r1", reactants={a: 1}, products={b: 1}, rate=0.1, dat=MockDat("rxn/r1"))

        chem = ChemistryImpl(
            "test",
            atoms={"C": C, "H": H, "O": O},
            molecules={"A": a, "B": b},
            reactions={"r1": r1},
            dat=MockDat("chemistry/test"),
        )

        # Serialize
        d = chem.to_dict()

        # Check structure
        assert d["head"] == "Chemistry"
        assert "atoms" in d
        assert "molecules" in d
        assert "reactions" in d
        assert d["atoms"]["C"]["name"] == "Carbon"
        assert d["molecules"]["A"]["atoms"] == {"C": 1, "H": 4}
        assert d["molecules"]["A"]["bdepth"] == 1
