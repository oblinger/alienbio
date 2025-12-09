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
        assert io.data_path == Path("data")
        assert io.prefixes == {}

    def test_create_with_data_path(self):
        """IO can be created with custom data path."""
        io = IO(data_path=Path("/custom/path"))
        assert io.data_path == Path("/custom/path")


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


class TestFormat:
    """Tests for entity formatting."""

    def test_format_with_no_prefixes(self):
        """format() uses full name when no prefixes bound."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        result = io.format(compartment)

        assert result == "runs/exp1.cytoplasm"

    def test_format_with_matching_prefix(self):
        """format() uses matching prefix."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.format(compartment)

        assert result == "W:cytoplasm"

    def test_format_exact_match(self):
        """format() handles exact prefix match (no path)."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        result = io.format(world)

        assert result == "W:"

    def test_format_nested_path(self):
        """format() builds dotted path for nested entities."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        io.bind_prefix("W", world)

        result = io.format(molecule)

        assert result == "W:cytoplasm.glucose"

    def test_format_prefers_shorter_path(self):
        """format() prefers shorter prefix path."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        # Bind both world and compartment as prefixes
        io.bind_prefix("W", world)
        io.bind_prefix("C", compartment)

        result = io.format(molecule)

        # C:glucose is shorter than W:cytoplasm.glucose
        assert result == "C:glucose"

    def test_format_no_matching_prefix(self):
        """format() uses full name when no prefix matches."""
        io = IO()
        dat1 = MockDat("runs/exp1")
        world1 = Entity("world1", dat=dat1)

        dat2 = MockDat("runs/exp2")
        world2 = Entity("world2", dat=dat2)
        compartment = Entity("cytoplasm", parent=world2)

        # Only bind world1, but entity is under world2
        io.bind_prefix("W", world1)

        result = io.format(compartment)

        # Falls back to full name
        assert result == "runs/exp2.cytoplasm"


class TestParse:
    """Tests for string parsing."""

    def test_parse_with_path(self):
        """parse() resolves prefix and walks path."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        result = io.parse("W:cytoplasm")

        assert result is compartment

    def test_parse_nested_path(self):
        """parse() handles dotted paths."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        io.bind_prefix("W", world)

        result = io.parse("W:cytoplasm.glucose")

        assert result is molecule

    def test_parse_prefix_only(self):
        """parse() returns prefix target when no path."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        result = io.parse("W:")

        assert result is world

    def test_parse_missing_colon_raises(self):
        """parse() raises for string without colon."""
        io = IO()

        with pytest.raises(ValueError, match="missing prefix separator"):
            io.parse("nocolon")

    def test_parse_empty_prefix_raises(self):
        """parse() raises for empty prefix."""
        io = IO()

        with pytest.raises(ValueError, match="empty prefix"):
            io.parse(":path")

    def test_parse_unbound_prefix_raises(self):
        """parse() raises for unbound prefix."""
        io = IO()

        with pytest.raises(KeyError, match="Prefix 'X' is not bound"):
            io.parse("X:path")

    def test_parse_invalid_path_raises(self):
        """parse() raises for invalid path."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        with pytest.raises(KeyError, match="No child named"):
            io.parse("W:nonexistent")


class TestFormatParseRoundtrip:
    """Tests for format/parse roundtrip."""

    def test_roundtrip_direct_child(self):
        """format then parse roundtrips for direct child."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)

        io.bind_prefix("W", world)

        formatted = io.format(compartment)
        parsed = io.parse(formatted)

        assert parsed is compartment

    def test_roundtrip_nested(self):
        """format then parse roundtrips for nested entity."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)
        compartment = Entity("cytoplasm", parent=world)
        molecule = Entity("glucose", parent=compartment)

        io.bind_prefix("W", world)

        formatted = io.format(molecule)
        parsed = io.parse(formatted)

        assert parsed is molecule

    def test_roundtrip_exact_prefix(self):
        """format then parse roundtrips for prefix target."""
        io = IO()
        dat = MockDat("runs/exp1")
        world = Entity("world", dat=dat)

        io.bind_prefix("W", world)

        formatted = io.format(world)
        parsed = io.parse(formatted)

        assert parsed is world
