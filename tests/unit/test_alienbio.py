"""Tests for alienbio top-level operators."""

import tempfile
from contextvars import ContextVar
from pathlib import Path

import pytest

from alienbio import Context, create, ctx, do, load, o, save, set_context


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
        """do() resolves a dotted name to an object."""
        result = do("catalog.kegg1")
        assert result is not None
        assert result["_name"] == "catalog.kegg1"
        assert result["_parts"] == ["catalog", "kegg1"]

    def test_do_handles_deep_paths(self):
        """do() handles deeply nested dotted paths."""
        result = do("catalog.kegg1.molecule_gen")
        assert result["_parts"] == ["catalog", "kegg1", "molecule_gen"]


class TestCreate:
    """Tests for create() instantiation."""

    def test_create_from_string_spec(self):
        """create() instantiates from a string prototype name."""
        result = create("catalog.kegg1.molecule_gen")
        assert result["_proto"] == "catalog.kegg1.molecule_gen"
        assert "_resolved" in result

    def test_create_from_dict_spec(self):
        """create() instantiates from a dict specification."""
        spec = {"_proto": "catalog.kegg1.molecule_gen", "params": {"count": 10}}
        result = create(spec)
        assert result["_proto"] == "catalog.kegg1.molecule_gen"
        assert result["_spec"] == spec


class TestSaveLoad:
    """Tests for save() and load() persistence."""

    def test_save_creates_directory(self):
        """save() creates the target directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            save({"name": "test"}, "test/item1")

            assert (Path(tmpdir) / "test" / "item1").exists()
            assert (Path(tmpdir) / "test" / "item1" / "_spec.yaml").exists()

    def test_load_returns_object(self):
        """load() returns an object from a data path."""
        result = load("test/item1")
        assert result["_loaded"] is True
        assert "test/item1" in result["_path"]

    def test_save_load_roundtrip(self):
        """save() then load() round-trips an object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            obj = {"name": "test_obj", "value": 42}
            save(obj, "roundtrip/test1")
            loaded = load("roundtrip/test1")

            assert loaded["_loaded"] is True
            assert "roundtrip/test1" in loaded["_path"]


class TestProxy:
    """Tests for the 'o' proxy object."""

    def test_proxy_accesses_context_attrs(self):
        """o.attr accesses context attributes."""
        context = Context(config={"proxy_test": True})
        set_context(context)

        assert o.config == {"proxy_test": True}

    def test_proxy_accesses_data_path(self):
        """o.data_path accesses context data_path."""
        assert o.data_path == ctx().data_path
