"""Tests for Entity base class and naming system."""

from typing import Optional
from unittest.mock import MagicMock

import pytest

from alienbio.infra.entity import (
    Entity,
    get_entity_type,
    get_entity_types,
    register_entity_type,
)


class MockDat:
    """Mock Dat for testing Entity without full DAT dependency."""

    def __init__(self, path_name: str):
        self._path_name = path_name

    def get_path_name(self) -> str:
        return self._path_name


class TestEntityCreation:
    """Tests for Entity instantiation."""

    def test_create_with_dat(self):
        """Entity can be created with a DAT anchor."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)
        assert entity.local_name == "world"
        assert entity.dat is dat
        assert entity.parent is None

    def test_create_with_parent(self):
        """Entity can be created with a parent."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        assert child.local_name == "compartment"
        assert child.parent is parent
        assert child.dat is None

    def test_create_requires_parent_or_dat(self):
        """Entity requires either parent or DAT anchor."""
        with pytest.raises(ValueError, match="'orphan' must have either a parent or a DAT"):
            Entity("orphan")

    def test_create_with_space_in_name_raises(self):
        """Entity name cannot contain spaces."""
        dat = MockDat("runs/exp1")
        with pytest.raises(ValueError, match="contains spaces"):
            Entity("invalid name", dat=dat)

    def test_create_with_both_parent_and_dat(self):
        """Entity can have both parent and DAT (dual-anchored)."""
        parent_dat = MockDat("runs/exp1")
        parent = Entity("world", dat=parent_dat)

        child_dat = MockDat("runs/exp1/compartment")
        child = Entity("compartment", parent=parent, dat=child_dat)

        assert child.parent is parent
        assert child.dat is child_dat

    def test_create_with_description(self):
        """Entity can have a description."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat, description="Main simulation world")
        assert entity.description == "Main simulation world"


class TestParentChildRelationship:
    """Tests for bidirectional parent-child links."""

    def test_parent_registers_child(self):
        """Setting parent registers entity in parent's children."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        assert "compartment" in parent.children
        assert parent.children["compartment"] is child

    def test_children_returns_copy(self):
        """Children property returns a copy, not the internal dict."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        Entity("child1", parent=parent)

        children = parent.children
        children["fake"] = "value"

        assert "fake" not in parent.children

    def test_add_child_sets_parent(self):
        """add_child() sets the child's parent."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)

        # Create with dat so we can reassign parent
        child_dat = MockDat("temp")
        child = Entity("compartment", dat=child_dat)

        parent.add_child(child)

        assert child.parent is parent
        assert "compartment" in parent.children

    def test_add_child_returns_child(self):
        """add_child() returns the child for chaining."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child_dat = MockDat("temp")
        child = Entity("compartment", dat=child_dat)

        result = parent.add_child(child)
        assert result is child

    def test_remove_child(self):
        """remove_child() removes child and clears its parent."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        removed = parent.remove_child("compartment")

        assert removed is child
        assert child.parent is None
        assert "compartment" not in parent.children

    def test_remove_nonexistent_child(self):
        """remove_child() returns None for nonexistent child."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)

        removed = parent.remove_child("nonexistent")
        assert removed is None

    def test_duplicate_child_name_raises(self):
        """Adding child with duplicate name raises ValueError."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        Entity("compartment", parent=parent)

        child_dat = MockDat("temp")
        child2 = Entity("compartment", dat=child_dat)

        with pytest.raises(ValueError, match="already has child named"):
            parent.add_child(child2)

    def test_set_parent_moves_child(self):
        """set_parent() moves child between parents."""
        dat = MockDat("runs/exp1")
        parent1 = Entity("world1", dat=dat)
        parent2 = Entity("world2", dat=dat)

        child = Entity("compartment", parent=parent1)
        assert "compartment" in parent1.children

        child.set_parent(parent2)

        assert "compartment" not in parent1.children
        assert "compartment" in parent2.children
        assert child.parent is parent2


class TestFullName:
    """Tests for full name resolution."""

    def test_full_name_from_dat(self):
        """Entity with DAT uses DAT path as full name."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        assert entity.full_name == "runs/exp1"

    def test_full_name_from_parent(self):
        """Entity walks up to parent's full name."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        assert child.full_name == "runs/exp1.compartment"

    def test_full_name_nested(self):
        """Nested entities build dotted path."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        assert molecule.full_name == "runs/exp1.cytoplasm.glucose"

    def test_full_name_no_anchor_raises(self):
        """Entity with no DAT and no parent raises ValueError."""
        # This can't happen through normal construction, but test the property
        dat = MockDat("temp")
        entity = Entity("orphan", dat=dat)
        entity._dat = None
        entity._parent = None

        with pytest.raises(ValueError, match="no DAT anchor and no parent"):
            _ = entity.full_name

    def test_dual_anchored_uses_own_dat(self):
        """Entity with both parent and DAT uses its own DAT."""
        parent_dat = MockDat("runs/exp1")
        parent = Entity("world", dat=parent_dat)

        child_dat = MockDat("compartments/cytoplasm")
        child = Entity("cytoplasm", parent=parent, dat=child_dat)

        # Own DAT takes precedence
        assert child.full_name == "compartments/cytoplasm"


class TestToDict:
    """Tests for to_dict serialization."""

    def test_to_dict_basic(self):
        """to_dict returns dict with type and name."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        result = entity.to_dict()

        assert result == {"type": "Entity", "name": "world"}

    def test_to_dict_with_description(self):
        """to_dict includes description if present."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat, description="Main world")

        result = entity.to_dict()

        assert result == {"type": "Entity", "name": "world", "description": "Main world"}

    def test_to_dict_excludes_structural_fields(self):
        """to_dict does not include parent, children, dat."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        result = child.to_dict()

        assert "parent" not in result
        assert "children" not in result
        assert "dat" not in result


class TestToDictRecursive:
    """Tests for recursive to_dict serialization."""

    def test_to_dict_recursive_single_child(self):
        """to_dict(recursive=True) includes children."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        Entity("cytoplasm", parent=world)

        result = world.to_dict(recursive=True)

        assert result["name"] == "world"
        assert "children" in result
        assert "cytoplasm" in result["children"]
        assert result["children"]["cytoplasm"]["name"] == "cytoplasm"

    def test_to_dict_recursive_nested(self):
        """to_dict(recursive=True) recurses into nested children."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cytoplasm = Entity("cytoplasm", parent=world)
        Entity("glucose", parent=cytoplasm)

        result = world.to_dict(recursive=True)

        assert "children" in result
        assert "cytoplasm" in result["children"]
        cyto_dict = result["children"]["cytoplasm"]
        assert "children" in cyto_dict
        assert "glucose" in cyto_dict["children"]
        assert cyto_dict["children"]["glucose"]["name"] == "glucose"

    def test_to_dict_recursive_no_children(self):
        """to_dict(recursive=True) omits children key for leaf."""
        dat = MockDat("runs/exp1")
        entity = Entity("leaf", dat=dat)

        result = entity.to_dict(recursive=True)

        assert result == {"type": "Entity", "name": "leaf"}
        assert "children" not in result

    def test_to_dict_recursive_preserves_description(self):
        """to_dict(recursive=True) includes descriptions."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat, description="Main world")
        Entity("cytoplasm", parent=world, description="Cell compartment")

        result = world.to_dict(recursive=True)

        assert result["description"] == "Main world"
        assert result["children"]["cytoplasm"]["description"] == "Cell compartment"

    def test_to_dict_non_recursive_omits_children(self):
        """to_dict() without recursive=True omits children."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        Entity("cytoplasm", parent=world)

        result = world.to_dict()  # recursive=False by default

        assert result == {"type": "Entity", "name": "world"}
        assert "children" not in result


class TestToStr:
    """Tests for to_str tree representation."""

    def test_to_str_leaf(self):
        """to_str returns just name for leaf entity."""
        dat = MockDat("runs/exp1")
        entity = Entity("glucose", dat=dat)

        assert entity.to_str() == "glucose"

    def test_to_str_with_children(self):
        """to_str shows children in parentheses."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        Entity("cytoplasm", parent=world)
        Entity("nucleus", parent=world)

        result = world.to_str()

        assert result == "world(cytoplasm, nucleus)"

    def test_to_str_nested(self):
        """to_str recurses into children."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cytoplasm = Entity("cytoplasm", parent=world)
        Entity("glucose", parent=cytoplasm)
        Entity("ATP", parent=cytoplasm)

        result = world.to_str()

        assert result == "world(cytoplasm(glucose, ATP))"

    def test_to_str_depth_zero(self):
        """to_str with depth=0 returns just name."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        Entity("cytoplasm", parent=world)

        result = world.to_str(depth=0)

        assert result == "world"

    def test_to_str_depth_one(self):
        """to_str with depth=1 shows immediate children only."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cytoplasm = Entity("cytoplasm", parent=world)
        Entity("glucose", parent=cytoplasm)

        result = world.to_str(depth=1)

        assert result == "world(cytoplasm)"

    def test_to_str_depth_two(self):
        """to_str with depth=2 shows two levels."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cytoplasm = Entity("cytoplasm", parent=world)
        glucose = Entity("glucose", parent=cytoplasm)
        Entity("atom", parent=glucose)

        result = world.to_str(depth=2)

        assert result == "world(cytoplasm(glucose))"


class TestTreeTraversal:
    """Tests for tree traversal methods."""

    def test_root_returns_self_if_no_parent(self):
        """root() returns self for root entity."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        assert entity.root() is entity

    def test_root_returns_topmost_ancestor(self):
        """root() returns the topmost ancestor."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        assert molecule.root() is world
        assert compartment.root() is world

    def test_ancestors_iterates_to_root(self):
        """ancestors() yields parents from immediate to root."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        ancestors = list(molecule.ancestors())

        assert len(ancestors) == 2
        assert ancestors[0] is compartment
        assert ancestors[1] is world

    def test_ancestors_empty_for_root(self):
        """ancestors() yields nothing for root entity."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        assert list(entity.ancestors()) == []

    def test_descendants_depth_first(self):
        """descendants() yields all descendants depth-first."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        comp1 = Entity("comp1", parent=world)
        comp2 = Entity("comp2", parent=world)
        mol1 = Entity("mol1", parent=comp1)
        mol2 = Entity("mol2", parent=comp1)

        descendants = list(world.descendants())

        assert len(descendants) == 4
        # comp1 comes before comp2 (dict order), mol1/mol2 before comp2
        assert comp1 in descendants
        assert comp2 in descendants
        assert mol1 in descendants
        assert mol2 in descendants

    def test_descendants_empty_for_leaf(self):
        """descendants() yields nothing for leaf entity."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        leaf = Entity("leaf", parent=world)

        assert list(leaf.descendants()) == []


class TestDatAnchor:
    """Tests for DAT anchor management."""

    def test_find_dat_anchor_returns_own_dat(self):
        """find_dat_anchor() returns own DAT if present."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        assert entity.find_dat_anchor() is dat

    def test_find_dat_anchor_walks_up(self):
        """find_dat_anchor() walks up to find nearest DAT."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        assert molecule.find_dat_anchor() is dat
        assert compartment.find_dat_anchor() is dat

    def test_find_dat_anchor_returns_none_if_orphan(self):
        """find_dat_anchor() returns None if no DAT in ancestry."""
        dat = MockDat("temp")
        entity = Entity("orphan", dat=dat)
        entity._dat = None
        entity._parent = None

        assert entity.find_dat_anchor() is None

    def test_set_dat(self):
        """set_dat() updates the DAT anchor."""
        dat1 = MockDat("runs/exp1")
        entity = Entity("world", dat=dat1)

        dat2 = MockDat("runs/exp2")
        entity.set_dat(dat2)

        assert entity.dat is dat2


class TestStringRepresentation:
    """Tests for __str__ and __repr__."""

    def test_str_uses_full_name(self):
        """__str__ returns full name."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        assert str(entity) == "runs/exp1"

    def test_str_with_parent(self):
        """__str__ builds path through parent."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        assert str(child) == "runs/exp1.compartment"

    def test_str_fallback_for_orphan(self):
        """__str__ falls back to <Entity:local_name> for orphan."""
        dat = MockDat("temp")
        entity = Entity("orphan", dat=dat)
        entity._dat = None
        entity._parent = None

        assert str(entity) == "<Entity:orphan>"

    def test_repr_includes_all_fields(self):
        """__repr__ includes local_name, description, dat, parent, children."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat, description="Main world")
        child = Entity("compartment", parent=parent)

        repr_str = repr(parent)

        assert "name='world'" in repr_str
        assert "description='Main world'" in repr_str
        assert "dat='runs/exp1'" in repr_str
        assert "children=['compartment']" in repr_str

    def test_repr_minimal(self):
        """__repr__ omits empty fields."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        repr_str = repr(entity)

        assert "name='world'" in repr_str
        assert "dat='runs/exp1'" in repr_str
        assert "description" not in repr_str
        assert "children" not in repr_str
        assert "parent" not in repr_str


# Test subclasses for type registry testing
class Molecule(Entity):
    """Test subclass using class name as type."""

    __slots__ = ("formula",)

    def __init__(self, name, *, parent=None, dat=None, description="", formula=""):
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.formula = formula

    def to_dict(self, recursive=False, _root_dat=None):
        result = super().to_dict(recursive=recursive, _root_dat=_root_dat)
        if self.formula:
            result["formula"] = self.formula
        return result


class Compartment(Entity, type_name="C"):
    """Test subclass using short type_name."""

    __slots__ = ("volume",)

    def __init__(self, name, *, parent=None, dat=None, description="", volume=0.0):
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.volume = volume

    def to_dict(self, recursive=False, _root_dat=None):
        result = super().to_dict(recursive=recursive, _root_dat=_root_dat)
        if self.volume:
            result["volume"] = self.volume
        return result


class Reaction(Entity, type_name="R"):
    """Test subclass with short type_name for reactions."""

    __slots__ = ("rate",)

    def __init__(self, name, *, parent=None, dat=None, description="", rate=0.0):
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.rate = rate

    def to_dict(self, recursive=False, _root_dat=None):
        result = super().to_dict(recursive=recursive, _root_dat=_root_dat)
        if self.rate:
            result["rate"] = self.rate
        return result


class TestTypeRegistry:
    """Tests for entity type registration."""

    def test_entity_registered_as_entity(self):
        """Base Entity is registered as 'Entity'."""
        assert get_entity_type("Entity") is Entity

    def test_subclass_registered_by_class_name(self):
        """Subclass without type_name is registered by class name."""
        assert get_entity_type("Molecule") is Molecule

    def test_subclass_registered_by_type_name(self):
        """Subclass with type_name is registered by that name."""
        assert get_entity_type("C") is Compartment
        assert get_entity_type("R") is Reaction

    def test_get_entity_types_returns_all(self):
        """get_entity_types returns all registered types."""
        types = get_entity_types()
        assert "Entity" in types
        assert "Molecule" in types
        assert "C" in types
        assert "R" in types

    def test_unknown_type_raises(self):
        """get_entity_type raises KeyError for unknown type."""
        with pytest.raises(KeyError, match="Unknown entity type"):
            get_entity_type("NonexistentType")


class TestSubclassSerialization:
    """Tests for subclass serialization."""

    def test_molecule_to_dict_includes_type(self):
        """Molecule.to_dict includes type='Molecule'."""
        dat = MockDat("runs/exp1")
        mol = Molecule("glucose", dat=dat, formula="C6H12O6")

        result = mol.to_dict()

        assert result["type"] == "Molecule"
        assert result["name"] == "glucose"
        assert result["formula"] == "C6H12O6"

    def test_compartment_to_dict_includes_short_type(self):
        """Compartment.to_dict includes type='C' (short name)."""
        dat = MockDat("runs/exp1")
        comp = Compartment("cytoplasm", dat=dat, volume=1.5)

        result = comp.to_dict()

        assert result["type"] == "C"
        assert result["name"] == "cytoplasm"
        assert result["volume"] == 1.5

    def test_recursive_to_dict_preserves_types(self):
        """Recursive to_dict preserves subclass types."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cyto = Compartment("cytoplasm", parent=world, volume=1.0)
        Molecule("glucose", parent=cyto, formula="C6H12O6")

        result = world.to_dict(recursive=True)

        assert result["type"] == "Entity"
        assert result["children"]["cytoplasm"]["type"] == "C"
        assert result["children"]["cytoplasm"]["children"]["glucose"]["type"] == "Molecule"


class TestSubclassTree:
    """Tests for trees with mixed entity subclasses."""

    def test_mixed_entity_tree(self):
        """Can create tree with mixed entity types."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cyto = Compartment("cytoplasm", parent=world, volume=1.0)
        glucose = Molecule("glucose", parent=cyto, formula="C6H12O6")
        rxn = Reaction("glycolysis", parent=cyto, rate=0.1)

        assert world.children["cytoplasm"] is cyto
        assert cyto.children["glucose"] is glucose
        assert cyto.children["glycolysis"] is rxn
        assert isinstance(cyto, Compartment)
        assert isinstance(glucose, Molecule)
        assert isinstance(rxn, Reaction)

    def test_to_str_works_with_subclasses(self):
        """to_str works correctly with subclass tree."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cyto = Compartment("cytoplasm", parent=world)
        Molecule("glucose", parent=cyto)
        Molecule("atp", parent=cyto)

        result = world.to_str()

        assert result == "world(cytoplasm(glucose, atp))"
