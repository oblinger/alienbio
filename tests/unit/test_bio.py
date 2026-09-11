"""Unit tests for bio module: Atom, Molecule, Reaction, Chemistry (the M1 State/Simulator tests went with T056)."""

import pytest
from unittest.mock import MagicMock

from alienbio import (
    # Protocols (for type checking)
    Atom,
    Molecule,
    Reaction,
    Chemistry,
    Simulator,
    # Implementation classes (for instantiation)
    AtomImpl,
    MoleculeImpl,
    ReactionImpl,
    ChemistryImpl,
    # Atom utilities
    COMMON_ATOMS,
    get_atom,
    # Other
    Entity,
)
from alienbio.infra.entity import get_entity_class


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
        cls = get_entity_class("Molecule")
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
        """The rate is a number (a rate LAW is `rate_law`, compiled by rate_expr)."""
        reaction = ReactionImpl("r1", rate=0.5, dat=MockDat("reactions/r1"))
        assert reaction.rate == 0.5

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

    def test_reaction_type_registered(self):
        """ReactionImpl registered as 'Reaction'."""
        cls = get_entity_class("Reaction")
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
        cls = get_entity_class("Chemistry")
        assert cls is ChemistryImpl
