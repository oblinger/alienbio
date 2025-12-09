"""Tests for alienbio top-level operators."""

import tempfile
from contextvars import ContextVar
from pathlib import Path

import pytest

from alienbio import Context, Dat, create, ctx, do, load, o, save, set_context


class TestCtx:
    """Tests for ctx() context access."""

    def test_ctx_returns_context(self):
        """ctx() returns a Context object."""
        context = ctx()
        assert isinstance(context, Context)

    def test_ctx_uses_contextvar(self):
        """ctx() uses ContextVar, not a plain global."""
        from alienbio import _ctx

        assert isinstance(_ctx, ContextVar)

    def test_ctx_creates_default_if_none(self):
        """ctx() creates a default Context if none exists."""
        set_context(None)
        context = ctx()
        assert context is not None
        assert isinstance(context, Context)

    def test_set_context_changes_context(self):
        """set_context() changes the active context."""
        original = ctx()
        new_context = Context(config={"test": True})
        set_context(new_context)
        assert ctx() is new_context
        assert ctx().config == {"test": True}
        set_context(original)


class TestDo:
    """Tests for do() name resolution."""

    def test_do_resolves_dotted_name(self):
        """do() resolves a dotted name to fixture data."""
        result = do("fixtures.simple")
        assert result is not None
        assert result["name"] == "simple_fixture"

    def test_do_resolves_nested_fixture(self):
        """do() resolves nested fixtures."""
        result = do("fixtures.kegg1")
        assert result["name"] == "kegg1"
        assert result["type"] == "biochemistry_model"


class TestCreate:
    """Tests for create() instantiation."""

    def test_create_from_string_spec(self):
        """create() creates a Dat from a string prototype name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = create("fixtures.simple", path=f"{tmpdir}/test_create")
            assert isinstance(result, Dat)
            assert result.get_spec()["name"] == "simple_fixture"

    def test_create_from_dict_spec(self):
        """create() creates a Dat from a dict specification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec = {"custom": "value", "count": 10}
            result = create(spec, path=f"{tmpdir}/test_dict")
            assert isinstance(result, Dat)
            assert result.get_spec()["custom"] == "value"
            assert result.get_spec()["count"] == 10


class TestSaveLoad:
    """Tests for save() and load() persistence."""

    def test_save_creates_directory(self):
        """save() creates the target directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save({"name": "test"}, f"{tmpdir}/test/item1")

            assert (Path(tmpdir) / "test" / "item1").exists()
            assert (Path(tmpdir) / "test" / "item1" / "_spec_.yaml").exists()

    def test_save_load_roundtrip(self):
        """save() then load() round-trips an object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            obj = {"name": "test_obj", "value": 42}
            save(obj, f"{tmpdir}/roundtrip/test1")
            loaded = load(f"{tmpdir}/roundtrip/test1")

            assert loaded.get_spec()["name"] == "test_obj"
            assert loaded.get_spec()["value"] == 42


class TestProxy:
    """Tests for the 'o' proxy object."""

    def test_proxy_accesses_context_attrs(self):
        """o.attr accesses context attributes."""
        context = Context(config={"proxy_test": True})
        set_context(context)

        assert o.config == {"proxy_test": True}

    def test_proxy_accesses_io(self):
        """o.io accesses context io."""
        from alienbio import IO
        assert isinstance(o.io, IO)
