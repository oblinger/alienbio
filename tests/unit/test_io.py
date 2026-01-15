"""Tests for IO class: prefix bindings, formatting, parsing."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alienbio.infra.entity import Entity
from alienbio.infra.io import IO


class MockDat:
    """Mock Dat for testing without full DAT dependency."""

    def __init__(self, path_name: str):
        self._path_name = path_name

    def get_path_name(self) -> str:
        return self._path_name


class TestIOCreation:
    """Tests for IO instantiation."""

    def test_create_default(self):
        """IO can be created with defaults."""
        io = IO()
        assert io.prefixes == {}


class TestPrefixBindings:
    """Tests for prefix binding operations."""

    def test_bind_prefix(self):
        """bind_prefix adds prefix binding."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        assert "W" in io.prefixes
        assert io.prefixes["W"] is world

    def test_bind_multiple_prefixes(self):
        """Multiple prefixes can be bound."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)
        io.bind_prefix("C", compartment)

        assert len(io.prefixes) == 2
        assert io.prefixes["W"] is world
        assert io.prefixes["C"] is compartment

    def test_resolve_prefix(self):
        """resolve_prefix returns bound entity."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        assert io.resolve_prefix("W") is world

    def test_resolve_unbound_prefix_raises(self):
        """resolve_prefix raises KeyError for unbound prefix."""
        io = IO()

        with pytest.raises(KeyError, match="Prefix 'X' is not bound"):
            io.resolve_prefix("X")

    def test_unbind_prefix(self):
        """unbind_prefix removes binding and returns entity."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)
        removed = io.unbind_prefix("W")

        assert removed is world
        assert "W" not in io.prefixes

    def test_unbind_nonexistent_prefix(self):
        """unbind_prefix returns None for nonexistent prefix."""
        io = IO()

        removed = io.unbind_prefix("X")
        assert removed is None

    def test_prefixes_returns_copy(self):
        """prefixes property returns a copy."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        io.bind_prefix("W", world)

        prefixes = io.prefixes
        prefixes["X"] = world

        assert "X" not in io.prefixes


class TestRef:
    """Tests for entity reference strings."""

    def test_ref_with_no_prefixes(self):
        """ref() uses full name when no prefixes bound."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        result = io.ref(compartment)

        assert result == "runs/exp1.cytoplasm"

    def test_ref_with_matching_prefix(self):
        """ref() uses matching prefix."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.ref(compartment)

        assert result == "W:cytoplasm"

    def test_ref_exact_match(self):
        """ref() handles exact prefix match (no path)."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        result = io.ref(world)

        assert result == "W:"

    def test_ref_nested_path(self):
        """ref() builds dotted path for nested entities."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        io.bind_prefix("W", world)

        result = io.ref(molecule)

        assert result == "W:cytoplasm.glucose"

    def test_ref_prefers_shorter_path(self):
        """ref() prefers shorter prefix path."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        # Bind both world and compartment as prefixes
        io.bind_prefix("W", world)
        io.bind_prefix("C", compartment)

        result = io.ref(molecule)

        # C:glucose is shorter than W:cytoplasm.glucose
        assert result == "C:glucose"

    def test_ref_no_matching_prefix(self):
        """ref() uses full name when no prefix matches."""
        io = IO()
        dat1 = MockDat("runs/exp1")
        world1 = Entity("world1", dat=dat1)

        dat2 = MockDat("runs/exp2")
        world2 = Entity("world2", dat=dat2)
        compartment = Entity("cytoplasm", parent=world2)

        # Only bind world1, but entity is under world2
        io.bind_prefix("W", world1)

        result = io.ref(compartment)

        # Falls back to full name
        assert result == "runs/exp2.cytoplasm"


class TestLookup:
    """Tests for entity lookup."""

    def test_lookup_with_path(self):
        """lookup() resolves prefix and walks path."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.lookup("W:cytoplasm")

        assert result is compartment

    def test_lookup_nested_path(self):
        """lookup() handles dotted paths."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        io.bind_prefix("W", world)

        result = io.lookup("W:cytoplasm.glucose")

        assert result is molecule

    def test_lookup_prefix_only(self):
        """lookup() returns prefix target when no path."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        result = io.lookup("W:")

        assert result is world

    def test_lookup_missing_colon_raises(self):
        """lookup() raises for string without colon."""
        io = IO()

        with pytest.raises(ValueError, match="missing prefix separator"):
            io.lookup("nocolon")

    def test_lookup_empty_prefix_raises(self):
        """lookup() raises for empty prefix."""
        io = IO()

        with pytest.raises(ValueError, match="empty prefix"):
            io.lookup(":path")

    def test_lookup_unbound_prefix_raises(self):
        """lookup() raises for unbound prefix."""
        io = IO()

        with pytest.raises(KeyError, match="Prefix 'X' is not bound"):
            io.lookup("X:path")

    def test_lookup_invalid_path_raises(self):
        """lookup() raises for invalid path."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        with pytest.raises(KeyError, match="No child named"):
            io.lookup("W:nonexistent")


class TestPathBinding:
    """Tests for binding prefixes to path strings."""

    def test_bind_path_string(self):
        """bind_prefix accepts a path string."""
        io = IO()
        io.bind_prefix("R", "runs/exp1")

        assert "R" in io.prefixes
        assert io.prefixes["R"] == "runs/exp1"

    def test_resolve_d_prefix(self):
        """D: prefix always resolves to data root."""
        io = IO()

        # D: should work even with no bindings
        root = io.resolve_prefix("D")
        assert root is not None
        # It's a _RootEntity
        assert root.local_name == ""

    def test_lookup_d_prefix(self):
        """lookup('D:') returns data root."""
        io = IO()

        root = io.lookup("D:")
        assert root is not None
        assert root.local_name == ""

    def test_lookup_prefix_only_returns_bound_entity(self):
        """lookup('W:') returns the bound entity (same as resolve_prefix)."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        # These should be equivalent
        assert io.lookup("W:") is world
        assert io.resolve_prefix("W") is world

    def test_ref_exact_prefix_match(self):
        """ref() returns 'W:' when entity is exact prefix target."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        assert io.ref(world) == "W:"


class TestAbsoluteRef:
    """Tests for absolute reference format </dat/path.entity.path>."""

    def test_absolute_ref_dat_root(self):
        """ref(absolute=True) returns </dat/path> for DAT root entity."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        result = io.ref(world, absolute=True)

        assert result == "</runs/exp1>"

    def test_absolute_ref_child(self):
        """ref(absolute=True) returns </dat/path.child> for child entity."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cytoplasm = Entity("cytoplasm", parent=world)

        result = io.ref(cytoplasm, absolute=True)

        assert result == "</runs/exp1.cytoplasm>"

    def test_absolute_ref_nested(self):
        """ref(absolute=True) returns </dat/path.child.grandchild> for nested."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        cytoplasm = Entity("cytoplasm", parent=world)
        glucose = Entity("glucose", parent=cytoplasm)

        result = io.ref(glucose, absolute=True)

        assert result == "</runs/exp1.cytoplasm.glucose>"

    def test_absolute_ref_no_dat_raises(self):
        """ref(absolute=True) raises if entity has no DAT anchor."""
        io = IO()
        # Create orphan entity with a mock dat that we'll remove
        dat = MockDat("temp")
        entity = Entity("orphan", dat=dat)
        entity._top = None  # Remove DAT to simulate orphan

        with pytest.raises(ValueError, match="no DAT anchor"):
            io.ref(entity, absolute=True)


class TestResolveRefs:
    """Tests for resolve_refs - replacing <PREFIX:path> strings with entities."""

    def test_resolve_refs_string(self):
        """resolve_refs replaces <PREFIX:path> with entity."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.resolve_refs("<W:cytoplasm>")

        assert result is compartment

    def test_resolve_refs_plain_string(self):
        """resolve_refs leaves plain strings unchanged."""
        io = IO()

        result = io.resolve_refs("just a string")

        assert result == "just a string"

    def test_resolve_refs_dict(self):
        """resolve_refs processes dict values."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.resolve_refs({
            "name": "glucose",
            "location": "<W:cytoplasm>",
            "count": 100
        })

        assert result["name"] == "glucose"
        assert result["location"] is compartment
        assert result["count"] == 100

    def test_resolve_refs_list(self):
        """resolve_refs processes list items."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        io.bind_prefix("W", world)

        result = io.resolve_refs(["<W:cytoplasm>", "<W:cytoplasm.glucose>"])

        assert result[0] is compartment
        assert result[1] is molecule

    def test_resolve_refs_nested(self):
        """resolve_refs handles nested structures."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.resolve_refs({
            "molecules": [
                {"name": "glucose", "location": "<W:cytoplasm>"},
                {"name": "ATP", "location": "<W:cytoplasm>"}
            ]
        })

        assert result["molecules"][0]["location"] is compartment
        assert result["molecules"][1]["location"] is compartment

    def test_resolve_refs_non_string_passthrough(self):
        """resolve_refs passes through non-string scalars."""
        io = IO()

        result = io.resolve_refs({"count": 42, "active": True, "value": None})

        assert result == {"count": 42, "active": True, "value": None}


class TestInsertRefs:
    """Tests for insert_refs - replacing entities with <PREFIX:path> strings."""

    def test_insert_refs_entity(self):
        """insert_refs replaces entity with <PREFIX:path>."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.insert_refs(compartment)

        assert result == "<W:cytoplasm>"

    def test_insert_refs_dict(self):
        """insert_refs processes dict values."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.insert_refs({
            "name": "glucose",
            "location": compartment,
            "count": 100
        })

        assert result["name"] == "glucose"
        assert result["location"] == "<W:cytoplasm>"
        assert result["count"] == 100

    def test_insert_refs_list(self):
        """insert_refs processes list items."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        io.bind_prefix("W", world)

        result = io.insert_refs([compartment, molecule])

        assert result == ["<W:cytoplasm>", "<W:cytoplasm.glucose>"]

    def test_insert_refs_nested(self):
        """insert_refs handles nested structures."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.insert_refs({
            "molecules": [
                {"name": "glucose", "location": compartment},
                {"name": "ATP", "location": compartment}
            ]
        })

        assert result["molecules"][0]["location"] == "<W:cytoplasm>"
        assert result["molecules"][1]["location"] == "<W:cytoplasm>"


class TestResolveInsertRoundtrip:
    """Tests for resolve_refs/insert_refs roundtrip."""

    def test_roundtrip_structure(self):
        """insert_refs then resolve_refs roundtrips a structure."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        io.bind_prefix("W", world)

        original = {
            "name": "reaction",
            "location": compartment,
            "reactants": [molecule],
            "count": 5
        }

        serialized = io.insert_refs(original)
        restored = io.resolve_refs(serialized)

        assert restored["name"] == "reaction"
        assert restored["location"] is compartment
        assert restored["reactants"][0] is molecule
        assert restored["count"] == 5


class TestRefLookupRoundtrip:
    """Tests for ref/lookup roundtrip."""

    def test_roundtrip_direct_child(self):
        """ref then lookup roundtrips for direct child."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        ref_str = io.ref(compartment)
        found = io.lookup(ref_str)

        assert found is compartment

    def test_roundtrip_nested(self):
        """ref then lookup roundtrips for nested entity."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        io.bind_prefix("W", world)

        ref_str = io.ref(molecule)
        found = io.lookup(ref_str)

        assert found is molecule

    def test_roundtrip_exact_prefix(self):
        """ref then lookup roundtrips for prefix target."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        ref_str = io.ref(world)
        found = io.lookup(ref_str)

        assert found is world


class TestEntityStrWithContext:
    """Tests for Entity.__str__ using context-aware formatting."""

    def test_str_uses_prefix_when_context_available(self):
        """Entity.__str__ uses PREFIX:path when IO is set up."""
        from alienbio import IO, set_io, io

        # Set up fresh IO instance
        set_io(IO())

        try:
            dat = MockDat("runs/exp1")
            world = Entity("world", dat=dat)
            compartment = Entity("cytoplasm", parent=world)

            io().bind_prefix("W", world)

            # str() should now use the prefix
            assert str(world) == "W:"
            assert str(compartment) == "W:cytoplasm"
        finally:
            # Clean up IO
            set_io(None)

    def test_str_falls_back_without_context(self):
        """Entity.__str__ falls back to full_name without IO."""
        from alienbio import set_io

        # Ensure no IO is set
        set_io(None)

        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        # Should fall back to full_name
        assert str(world) == "runs/exp1"
        assert str(compartment) == "runs/exp1.cytoplasm"

    def test_str_uses_shortest_prefix(self):
        """Entity.__str__ uses the shortest matching prefix."""
        from alienbio import IO, set_io, io

        set_io(IO())

        try:
            dat = MockDat("runs/exp1")
            world = Entity("world", dat=dat)
            compartment = Entity("cytoplasm", parent=world)
            molecule = Entity("glucose", parent=compartment)

            io().bind_prefix("W", world)
            io().bind_prefix("C", compartment)

            # Molecule should use shorter C: prefix
            assert str(molecule) == "C:glucose"
        finally:
            set_io(None)
