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


class TestCreateRoot:
    """Tests for create_root() entity creation."""

    def test_create_root_creates_entity_with_dat(self):
        """create_root() creates an entity anchored to a DAT."""
        from alienbio import Entity, create_root

        with tempfile.TemporaryDirectory() as tmpdir:
            root = create_root(f"{tmpdir}/test_root")

            assert isinstance(root, Entity)
            assert root.dat is not None
            assert root.parent is None
            assert root.local_name == "test_root"

    def test_create_root_uses_path_last_component_as_name(self):
        """create_root() derives name from last path component."""
        from alienbio import create_root

        with tempfile.TemporaryDirectory() as tmpdir:
            root = create_root(f"{tmpdir}/runs/exp1")

            assert root.local_name == "exp1"

    def test_create_root_accepts_explicit_name(self):
        """create_root() accepts explicit name kwarg."""
        from alienbio import create_root

        with tempfile.TemporaryDirectory() as tmpdir:
            root = create_root(f"{tmpdir}/runs/exp1", name="my_experiment")

            assert root.local_name == "my_experiment"

    def test_create_root_accepts_entity_type(self):
        """create_root() creates instance of specified entity type."""
        from alienbio import Entity, create_root

        class World(Entity):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            root = create_root(f"{tmpdir}/runs/exp1", World)

            assert isinstance(root, World)
            assert type(root) is World

    def test_create_root_passes_kwargs_to_entity(self):
        """create_root() passes kwargs to entity constructor."""
        from alienbio import create_root

        with tempfile.TemporaryDirectory() as tmpdir:
            root = create_root(
                f"{tmpdir}/runs/exp1",
                description="My experiment"
            )

            assert root.description == "My experiment"

    def test_create_root_children_have_parent_chain(self):
        """Children of root entity have parent chains to root."""
        from alienbio import Entity, create_root

        with tempfile.TemporaryDirectory() as tmpdir:
            root = create_root(f"{tmpdir}/runs/exp1")
            child = Entity("child", parent=root)
            grandchild = Entity("grandchild", parent=child)

            # Parent chain leads to root
            assert grandchild.parent is child
            assert child.parent is root
            assert root.parent is None

            # Root has DAT, children don't
            assert root.dat is not None
            assert child.dat is None
            assert grandchild.dat is None

    def test_create_root_save_persists_tree(self):
        """Saving root entity persists entire tree."""
        from alienbio import Entity, create_root

        with tempfile.TemporaryDirectory() as tmpdir:
            root = create_root(f"{tmpdir}/runs/exp1")
            Entity("child1", parent=root)
            Entity("child2", parent=root)

            root.save()

            # Check entities.yaml was created
            entities_file = Path(tmpdir) / "runs" / "exp1" / "entities.yaml"
            assert entities_file.exists()
