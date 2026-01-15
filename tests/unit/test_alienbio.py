"""Tests for alienbio top-level operators."""

from contextvars import ContextVar

import pytest

from alienbio import io, set_io, IO, Entity, Dat


class TestIO:
    """Tests for io() function access."""

    def test_io_returns_io_instance(self):
        """io() returns an IO object."""
        instance = io()
        assert isinstance(instance, IO)

    def test_io_uses_contextvar(self):
        """io() uses ContextVar for thread safety."""
        from alienbio.infra.io import _io_var

        assert isinstance(_io_var, ContextVar)

    def test_io_creates_default_if_none(self):
        """io() creates a default IO if none exists."""
        set_io(None)
        instance = io()
        assert instance is not None
        assert isinstance(instance, IO)

    def test_set_io_changes_instance(self):
        """set_io() changes the active IO instance."""
        original = io()
        new_io = IO()
        new_io.bind_prefix("TEST", "test/path")
        set_io(new_io)
        assert io() is new_io
        assert "TEST" in io().prefixes
        set_io(original)


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

    def test_io_functions_exported(self):
        """io() and set_io() are exported from alienbio."""
        from alienbio import io, set_io
        assert callable(io)
        assert callable(set_io)

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
