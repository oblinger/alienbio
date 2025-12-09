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
        assert entity.dat() is dat
        assert entity.parent is None

    def test_create_with_parent(self):
        """Entity can be created with a parent."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        assert child.local_name == "compartment"
        assert child.parent is parent
        assert child.dat() is dat  # Child accesses tree's DAT

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
        """Entity can have both parent and DAT (sub-root)."""
        parent_dat = MockDat("runs/exp1")
        parent = Entity("world", dat=parent_dat)

        child_dat = MockDat("runs/exp1/compartment")
        child = Entity("compartment", parent=parent, dat=child_dat)

        assert child.parent is parent
        assert child.dat() is child_dat  # Sub-root has its own DAT

    def test_create_with_description(self):
        """Entity can have a description."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat, description="Main simulation world")
        assert entity.description == "Main simulation world"


class TestParentChildRelationship:
    """Tests for bidirectional parent-child links."""

    def test_parent_registers_child(self):
        """Setting parent registers entity in parent's args."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        assert "compartment" in parent.children
        assert parent.children["compartment"] is child

    def test_args_returns_copy(self):
        """Children property returns a copy, not the internal dict."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        Entity("child1", parent=parent)

        args = parent.children
        args["fake"] = "value"

        assert "fake" not in parent.children

    def test_set_parent_attaches_root_entity(self):
        """set_parent() can attach a root entity as a child."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)

        # Create with dat so we can reassign parent
        child_dat = MockDat("temp")
        child = Entity("compartment", dat=child_dat)

        child.set_parent(parent)

        assert child.parent is parent
        assert "compartment" in parent.children

    def test_detach_moves_to_orphan_root(self):
        """detach() moves child to orphan root."""
        from alienbio import ctx, set_context, Context

        # Use fresh context to avoid naming collisions
        set_context(Context())
        try:
            dat = MockDat("runs/exp1")
            parent = Entity("world", dat=dat)
            child = Entity("compartment", parent=parent)

            child.detach()

            # Child is no longer under original parent
            assert "compartment" not in parent.children
            # Child is now under orphan root
            assert child.parent is ctx().io.orphan_root
            assert "compartment" in ctx().io.orphan_root.children
            # Child remains valid
            assert child.dat() is not None
        finally:
            set_context(None)

    def test_orphan_root_lazy_loading(self):
        """Orphan root is created lazily on first access."""
        from alienbio import ctx, set_context, Context

        set_context(Context())
        try:
            # Access orphan_root triggers lazy creation
            orphan_root = ctx().io.orphan_root
            assert orphan_root is not None
            assert orphan_root.local_name == "orphans"
            # ORPHAN prefix should be bound
            assert "ORPHAN" in ctx().io.prefixes
        finally:
            set_context(None)

    def test_save_on_orphan_raises(self):
        """Saving orphan root raises ValueError."""
        from alienbio import ctx, set_context, Context

        set_context(Context())
        try:
            dat = MockDat("runs/exp1")
            parent = Entity("world", dat=dat)
            child = Entity("orphan_child", parent=parent)

            child.detach()

            # Trying to save the orphan root should raise
            with pytest.raises(ValueError, match="Cannot save orphan"):
                ctx().io.orphan_root.save()

            # Trying to save an orphaned child's root also raises
            with pytest.raises(ValueError, match="Cannot save orphan"):
                child.root().save()
        finally:
            set_context(None)

    def test_reattach_orphaned_entity(self):
        """Orphaned entity can be re-attached to a new parent."""
        from alienbio import ctx, set_context, Context

        set_context(Context())
        try:
            dat = MockDat("runs/exp1")
            parent1 = Entity("world1", dat=dat)
            parent2 = Entity("world2", dat=dat)
            child = Entity("movable", parent=parent1)

            # Detach from parent1
            child.detach()
            assert child.parent is ctx().io.orphan_root

            # Re-attach to parent2
            child.set_parent(parent2)
            assert child.parent is parent2
            assert "movable" in parent2.children
            assert "movable" not in ctx().io.orphan_root.children
        finally:
            set_context(None)

    def test_detach_subtree_moves_all_descendants(self):
        """Detaching a subtree moves entire subtree to orphan root."""
        from alienbio import ctx, set_context, Context

        set_context(Context())
        try:
            dat = MockDat("runs/exp1")
            root = Entity("root", dat=dat)
            child = Entity("child", parent=root)
            grandchild = Entity("grandchild", parent=child)

            # Detach child (which has grandchild)
            child.detach()

            # Child is now under orphan root
            assert child.parent is ctx().io.orphan_root
            # Grandchild still under child
            assert grandchild.parent is child
            # Grandchild's root is now orphan root
            assert grandchild.root() is ctx().io.orphan_root
        finally:
            set_context(None)

    def test_duplicate_child_name_raises(self):
        """Adding child with duplicate name raises ValueError."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        Entity("compartment", parent=parent)

        child_dat = MockDat("temp")
        child2 = Entity("compartment", dat=child_dat)

        with pytest.raises(ValueError, match="already has child named"):
            child2.set_parent(parent)

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

    def test_detached_entity_has_orphan_full_name(self):
        """Detached entity has full_name from orphan DAT."""
        from alienbio import set_context, Context

        # Use fresh context to avoid naming collisions in orphan root
        set_context(Context())
        try:
            dat = MockDat("runs/exp1")
            parent = Entity("world", dat=dat)
            child = Entity("compartment", parent=parent)

            child.detach()

            # Full name now comes from orphan root
            assert child.full_name == "<orphans>.compartment"
        finally:
            set_context(None)

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
        """to_dict returns dict with head and name."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        result = entity.to_dict()

        assert result == {"head": "Entity", "name": "world"}

    def test_to_dict_with_description(self):
        """to_dict includes description if present."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat, description="Main world")

        result = entity.to_dict()

        assert result == {"head": "Entity", "name": "world", "description": "Main world"}

    def test_to_dict_excludes_structural_fields(self):
        """to_dict does not include parent, args, dat."""
        dat = MockDat("runs/exp1")
        parent = Entity("world", dat=dat)
        child = Entity("compartment", parent=parent)

        result = child.to_dict()

        assert "parent" not in result
        assert "args" not in result
        assert "dat" not in result


class TestToDictRecursive:
    """Tests for recursive to_dict serialization."""

    def test_to_dict_recursive_single_child(self):
        """to_dict(recursive=True) includes args."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        Entity("cytoplasm", parent=world)

        result = world.to_dict(recursive=True)

        assert result["name"] == "world"
        assert "args" in result
        assert "cytoplasm" in result["args"]
        assert result["args"]["cytoplasm"]["name"] == "cytoplasm"

    def test_to_dict_recursive_nested(self):
        """to_dict(recursive=True) recurses into nested args."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cytoplasm = Entity("cytoplasm", parent=world)
        Entity("glucose", parent=cytoplasm)

        result = world.to_dict(recursive=True)

        assert "args" in result
        assert "cytoplasm" in result["args"]
        cyto_dict = result["args"]["cytoplasm"]
        assert "args" in cyto_dict
        assert "glucose" in cyto_dict["args"]
        assert cyto_dict["args"]["glucose"]["name"] == "glucose"

    def test_to_dict_recursive_no_args(self):
        """to_dict(recursive=True) omits args key for leaf."""
        dat = MockDat("runs/exp1")
        entity = Entity("leaf", dat=dat)

        result = entity.to_dict(recursive=True)

        assert result == {"head": "Entity", "name": "leaf"}
        assert "args" not in result

    def test_to_dict_recursive_preserves_description(self):
        """to_dict(recursive=True) includes descriptions."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat, description="Main world")
        Entity("cytoplasm", parent=world, description="Cell compartment")

        result = world.to_dict(recursive=True)

        assert result["description"] == "Main world"
        assert result["args"]["cytoplasm"]["description"] == "Cell compartment"

    def test_to_dict_non_recursive_omits_args(self):
        """to_dict() without recursive=True omits args."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        Entity("cytoplasm", parent=world)

        result = world.to_dict()  # recursive=False by default

        assert result == {"head": "Entity", "name": "world"}
        assert "args" not in result


class TestToStr:
    """Tests for to_str tree representation."""

    def test_to_str_leaf(self):
        """to_str returns just name for leaf entity."""
        dat = MockDat("runs/exp1")
        entity = Entity("glucose", dat=dat)

        assert entity.to_str() == "glucose"

    def test_to_str_with_args(self):
        """to_str shows args in parentheses."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        Entity("cytoplasm", parent=world)
        Entity("nucleus", parent=world)

        result = world.to_str()

        assert result == "world(cytoplasm, nucleus)"

    def test_to_str_nested(self):
        """to_str recurses into args."""
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
        """to_str with depth=1 shows immediate args only."""
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


class TestDatAccess:
    """Tests for DAT access via dat() and root() methods."""

    def test_dat_on_root(self):
        """dat() returns DAT for root entity."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        assert entity.dat() is dat

    def test_dat_on_child_returns_tree_dat(self):
        """dat() returns tree's DAT for all entities in tree."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        assert molecule.dat() is dat
        assert compartment.dat() is dat
        assert world.dat() is dat

    def test_dat_on_detached_returns_orphan_dat(self):
        """dat() returns orphan DAT for detached entities."""
        from alienbio import set_context, Context
        from alienbio.infra.io import _OrphanDat

        # Use fresh context to avoid naming collisions
        set_context(Context())
        try:
            dat = MockDat("runs/exp1")
            world = Entity("world", dat=dat)
            child = Entity("child", parent=world)

            # Detach the child
            child.detach()

            # Detached entities have the orphan DAT
            assert isinstance(child.dat(), _OrphanDat)
        finally:
            set_context(None)

    def test_root_returns_self_for_root(self):
        """root() returns self for root entity."""
        dat = MockDat("runs/exp1")
        entity = Entity("world", dat=dat)

        assert entity.root() is entity

    def test_root_returns_ancestor_with_dat(self):
        """root() returns the ancestor with DAT anchor."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        assert molecule.root() is world
        assert compartment.root() is world


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

    def test_str_for_orphan_uses_orphan_prefix(self):
        """__str__ uses ORPHAN: prefix for detached entities."""
        from alienbio import ctx, set_context, Context

        # Set up a context
        set_context(Context())
        try:
            dat = MockDat("runs/exp1")
            parent = Entity("world", dat=dat)
            child = Entity("myentity", parent=parent)

            child.detach()

            # Should show ORPHAN:myentity
            assert str(child) == "ORPHAN:myentity"
        finally:
            set_context(None)

    def test_repr_includes_all_fields(self):
        """__repr__ includes local_name, description, dat, parent, args."""
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
        assert "args" not in repr_str
        assert "parent" not in repr_str


# Test subclasses for head registry testing
class SampleMol(Entity, head="SampleMol"):
    """Test subclass using explicit head to avoid conflicts."""

    __slots__ = ("formula",)

    def __init__(self, name, *, parent=None, dat=None, description="", formula=""):
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.formula = formula

    def attributes(self):
        result = super().attributes()
        if self.formula:
            result["formula"] = self.formula
        return result


class Compartment(Entity, head="C"):
    """Test subclass using short head."""

    __slots__ = ("volume",)

    def __init__(self, name, *, parent=None, dat=None, description="", volume=0.0):
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.volume = volume

    def attributes(self):
        result = super().attributes()
        if self.volume:
            result["volume"] = self.volume
        return result


class Reaction(Entity, head="R"):
    """Test subclass with short head for reactions."""

    __slots__ = ("rate",)

    def __init__(self, name, *, parent=None, dat=None, description="", rate=0.0):
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.rate = rate

    def attributes(self):
        result = super().attributes()
        if self.rate:
            result["rate"] = self.rate
        return result


class TestTypeRegistry:
    """Tests for entity head registration."""

    def test_entity_registered_as_entity(self):
        """Base Entity is registered as 'Entity'."""
        assert get_entity_type("Entity") is Entity

    def test_subclass_registered_by_class_name(self):
        """Subclass with head_name is registered by that name."""
        assert get_entity_type("SampleMol") is SampleMol

    def test_subclass_registered_by_head_name(self):
        """Subclass with head_name is registered by that name."""
        assert get_entity_type("C") is Compartment
        assert get_entity_type("R") is Reaction

    def test_get_entity_types_returns_all(self):
        """get_entity_types returns all registered heads."""
        heads = get_entity_types()
        assert "Entity" in heads
        assert "SampleMol" in heads
        assert "C" in heads
        assert "R" in heads

    def test_unknown_head_raises(self):
        """get_entity_type raises KeyError for unknown head."""
        with pytest.raises(KeyError, match="Unknown entity head"):
            get_entity_type("NonexistentType")


class TestSubclassSerialization:
    """Tests for subclass serialization."""

    def test_molecule_to_dict_includes_head(self):
        """SampleMol.to_dict includes head='SampleMol'."""
        dat = MockDat("runs/exp1")
        mol = SampleMol("glucose", dat=dat, formula="C6H12O6")

        result = mol.to_dict()

        assert result["head"] == "SampleMol"
        assert result["name"] == "glucose"
        assert result["formula"] == "C6H12O6"

    def test_compartment_to_dict_includes_short_head(self):
        """Compartment.to_dict includes head='C' (short name)."""
        dat = MockDat("runs/exp1")
        comp = Compartment("cytoplasm", dat=dat, volume=1.5)

        result = comp.to_dict()

        assert result["head"] == "C"
        assert result["name"] == "cytoplasm"
        assert result["volume"] == 1.5

    def test_recursive_to_dict_preserves_heads(self):
        """Recursive to_dict preserves subclass heads."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cyto = Compartment("cytoplasm", parent=world, volume=1.0)
        SampleMol("glucose", parent=cyto, formula="C6H12O6")

        result = world.to_dict(recursive=True)

        assert result["head"] == "Entity"
        assert result["args"]["cytoplasm"]["head"] == "C"
        assert result["args"]["cytoplasm"]["args"]["glucose"]["head"] == "SampleMol"


class TestSubclassTree:
    """Tests for trees with mixed entity subclasses."""

    def test_mixed_entity_tree(self):
        """Can create tree with mixed entity heads."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cyto = Compartment("cytoplasm", parent=world, volume=1.0)
        glucose = SampleMol("glucose", parent=cyto, formula="C6H12O6")
        rxn = Reaction("glycolysis", parent=cyto, rate=0.1)

        assert world.children["cytoplasm"] is cyto
        assert cyto.children["glucose"] is glucose
        assert cyto.children["glycolysis"] is rxn
        assert isinstance(cyto, Compartment)
        assert isinstance(glucose, SampleMol)
        assert isinstance(rxn, Reaction)

    def test_to_str_works_with_subclasses(self):
        """to_str works correctly with subclass tree."""
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cyto = Compartment("cytoplasm", parent=world)
        SampleMol("glucose", parent=cyto)
        SampleMol("atp", parent=cyto)

        result = world.to_str()

        assert result == "world(cytoplasm(glucose, atp))"
