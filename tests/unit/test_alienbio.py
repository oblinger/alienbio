"""Tests for alienbio top-level operators."""

import pytest

from alienbio import IO, Entity, Dat, Bio, bio


class TestBioIO:
    """Tests for bio.io pegboard access."""

    def test_bio_io_returns_io_instance(self):
        """bio.io returns an IO object."""
        assert isinstance(bio.io, IO)

    def test_bio_io_lazy_creates_default(self):
        """bio.io lazily creates a default IO if none exists."""
        # Create a fresh Bio instance
        fresh_bio = Bio()
        assert fresh_bio._io is None  # Not initialized yet
        io_instance = fresh_bio.io  # Access triggers lazy init
        assert io_instance is not None
        assert isinstance(io_instance, IO)

    def test_bio_io_can_be_replaced(self):
        """bio.io can be replaced with a custom IO instance."""
        fresh_bio = Bio()
        new_io = IO()
        new_io.bind_prefix("TEST", "test/path")
        fresh_bio.io = new_io
        assert fresh_bio.io is new_io
        assert "TEST" in fresh_bio.io.prefixes


class TestModuleExports:
    """Tests for alienbio module exports."""

    def test_core_exports_available(self):
        """Core classes are exported from alienbio."""
        from alienbio import Entity, IO, Dat, Bio, bio
        assert Entity is not None
        assert IO is not None
        assert Dat is not None
        assert Bio is not None
        assert bio is not None

    def test_spec_lang_exports_available(self):
        """Spec language classes are exported from alienbio."""
        from alienbio import Evaluable, Quoted, Reference, hydrate, dehydrate
        assert Evaluable is not None
        assert Quoted is not None
        assert Reference is not None
        assert callable(hydrate)
        assert callable(dehydrate)

    def test_bio_protocol_exports_available(self):
        """Bio protocol classes are exported from alienbio."""
        from alienbio import Molecule, Reaction, Chemistry, State, Simulator
        assert Molecule is not None
        assert Reaction is not None
        assert Chemistry is not None
        assert State is not None
        assert Simulator is not None
