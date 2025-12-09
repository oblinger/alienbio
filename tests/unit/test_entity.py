"""Tests for Entity base class and naming system."""

from typing import Optional
from unittest.mock import MagicMock

import pytest

from alienbio.infra.entity import Entity


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
        assert entity.name == "world"
        assert entity.dat is dat
        assert entity.parent is None

    def test_create_with_parent(self):
        """Entity can be created with a parent."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        assert child.name == "compartment"
        assert child.parent is parent
        assert child.dat is None

    def test_create_requires_parent_or_dat(self):
        """Entity requires either parent or DAT anchor."""
        with pytest.raises(ValueError, match="parent or a DAT anchor"):
            Entity("orphan")

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


class TestQualifiedName:
    """Tests for qualified name resolution."""

    def test_qualified_name_from_dat(self):
        """Entity with DAT uses DAT path as qualified name."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        assert entity.qualified_name == "runs/exp1"

    def test_qualified_name_from_parent(self):
        """Entity walks up to parent's qualified name."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        assert child.qualified_name == "runs/exp1.compartment"

    def test_qualified_name_nested(self):
        """Nested entities build dotted path."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        assert molecule.qualified_name == "runs/exp1.cytoplasm.glucose"

    def test_qualified_name_no_anchor_raises(self):
        """Entity with no DAT and no parent raises ValueError."""
        # This can't happen through normal construction, but test the property
        dat = MockDat("temp")
        entity = Entity("orphan", dat=dat)
        entity._dat = None
        entity._parent = None

        with pytest.raises(ValueError, match="no DAT anchor and no parent"):
            _ = entity.qualified_name

    def test_dual_anchored_uses_own_dat(self):
        """Entity with both parent and DAT uses its own DAT."""
        parent_dat = MockDat("runs/exp1")
        parent = Entity("world", dat=parent_dat)

        child_dat = MockDat("compartments/cytoplasm")
        child = Entity("cytoplasm", parent=parent, dat=child_dat)

        # Own DAT takes precedence
        assert child.qualified_name == "compartments/cytoplasm"


class TestLookup:
    """Tests for child entity lookup."""

    def test_lookup_empty_path(self):
        """lookup('') returns self."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        assert entity.lookup("") is entity

    def test_lookup_direct_child(self):
        """lookup finds direct child."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        assert parent.lookup("compartment") is child

    def test_lookup_nested_path(self):
        """lookup finds nested entities via dotted path."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        assert world.lookup("cytoplasm.glucose") is molecule

    def test_lookup_missing_raises(self):
        """lookup raises KeyError for missing child."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        with pytest.raises(KeyError, match="No child named"):
            entity.lookup("nonexistent")


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

    def test_str_uses_qualified_name(self):
        """__str__ returns qualified name."""
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
        """__str__ falls back to <Entity:name> for orphan."""
        dat = MockDat("temp")
        entity = Entity("orphan", dat=dat)
        entity._dat = None
        entity._parent = None

        assert str(entity) == "<Entity:orphan>"

    def test_repr_includes_all_fields(self):
        """__repr__ includes name, description, dat, parent, children."""
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
