"""Tests for dvc_dat integration via alienbio operators.

Scope note (2026-10-07): the dvc-dat repo moved into ``~/ob/grove/dvc-dat``
and went to 3.0, which retired the module-level ``do()`` function, the
``Dat.spec`` attribute and the runnable-spec surface this file used to pin
(five classes: ``TestDoResolves``, ``TestYamlStringSpec``,
``TestCallableFunctions``, ``TestDatWithProperSpec``, and the two
string-spec/attribute cases). None of it is reachable from ``alienbio``:
``src/`` imports ``Dat`` as a duck-typed anchor type and nothing else, and
dvc-dat owns its own ``tests/test_dat.py`` / ``test_do.py`` for its API. So
those cases were removed rather than ported — a second copy of a
dependency's API tests, pinned to a dead major version, is the duplication
the single-source rule forbids. What stays is the part alienbio does rely
on: the ``Dat.create`` / ``Dat.load`` round-trip and the entity
serialization layer over it.
"""

import tempfile
from pathlib import Path

import pytest

from alienbio import Dat
from dvc_dat import Dat as DvcDat


def save(obj, path):
    """Helper to save object as Dat (replaces old context.save)."""
    spec = obj if isinstance(obj, dict) else {"value": obj}
    return Dat.create(path=str(path), spec=spec)


def load(path):
    """Helper to load Dat (replaces old context.load)."""
    return Dat.load(str(path))


def create(spec, path):
    """Helper to create Dat from a dict spec (replaces old context.create)."""
    return Dat.create(path=str(path), spec=spec)


class TestCreate:
    """Tests for create() instantiation via dvc_dat."""


    def test_create_from_dict_returns_dat(self):
        """create() from dict spec returns a Dat."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec = {"custom_key": "custom_value", "count": 10}
            result = create(spec, path=f"{tmpdir}/create_dict")
            assert isinstance(result, Dat)
            assert result.get_spec()["custom_key"] == "custom_value"
            assert result.get_spec()["count"] == 10


class TestSaveLoadRoundtrip:
    """Tests for save() and load() persistence via Dat."""

    def test_save_creates_dat_folder(self):
        """save() creates a Dat folder with _spec_.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save({"name": "test", "value": 123}, f"{tmpdir}/test/item1")

            spec_path = Path(tmpdir) / "test" / "item1" / "_spec_.yaml"
            assert spec_path.exists()
            assert isinstance(result, Dat)

    def test_save_returns_dat(self):
        """save() returns a Dat object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save({"name": "test"}, f"{tmpdir}/test/item2")

            assert isinstance(result, Dat)

    def test_load_returns_dat(self):
        """load() returns a Dat object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Dat first
            save({"name": "test_load"}, f"{tmpdir}/test/load_test")

            # Load it
            result = load(f"{tmpdir}/test/load_test")

            assert isinstance(result, Dat)

    def test_save_load_roundtrip_dict(self):
        """save() then load() round-trips a dict through Dat."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = {"name": "roundtrip_test", "value": 42, "nested": {"a": 1}}
            save(original, f"{tmpdir}/roundtrip/test1")

            loaded = load(f"{tmpdir}/roundtrip/test1")

            assert loaded.get_spec()["name"] == "roundtrip_test"
            assert loaded.get_spec()["value"] == 42
            assert loaded.get_spec()["nested"]["a"] == 1

    def test_save_wraps_non_dict_in_value_key(self):
        """save() wraps non-dict values in a 'value' key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save("just a string", f"{tmpdir}/test/string_val")

            loaded = load(f"{tmpdir}/test/string_val")
            assert loaded.get_spec()["value"] == "just a string"


class TestDatOperations:
    """Tests for Dat-specific operations."""

    def test_dat_exposes_its_spec(self):
        """A loaded dat still hands back the spec it was created from — the
        one dvc-dat surface alienbio's io/entity layer reads (3.0 replaced
        the ``spec`` attribute with a ``get_spec()`` accessor)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save({"key": "value"}, f"{tmpdir}/test/spec_test")
            loaded = load(f"{tmpdir}/test/spec_test")

            assert loaded.get_spec()["key"] == "value"

    def test_dat_has_path(self):
        """Dat objects have a _path attribute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save({"key": "value"}, f"{tmpdir}/test/path_test")
            loaded = load(f"{tmpdir}/test/path_test")

            assert hasattr(loaded, "_path")
            assert "path_test" in str(loaded._path)


class TestDataFolderOperations:
    """Tests for saving/loading DATs from the data folder."""

    def test_save_to_fixtures_subfolder(self):
        """save() can write to a fixtures/ subfolder in data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dat = save({"name": "in_fixtures", "value": 999}, f"{tmpdir}/fixtures/test_item")

            assert isinstance(dat, Dat)
            spec_path = Path(tmpdir) / "fixtures" / "test_item" / "_spec_.yaml"
            assert spec_path.exists()

    def test_load_from_fixtures_subfolder(self):
        """load() can read from a fixtures/ subfolder in data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save first
            save({"name": "loadable", "value": 123}, f"{tmpdir}/fixtures/loadable_item")

            # Load it back
            dat = load(f"{tmpdir}/fixtures/loadable_item")

            assert isinstance(dat, Dat)
            assert dat.get_spec()["name"] == "loadable"
            assert dat.get_spec()["value"] == 123

    def test_roundtrip_nested_subfolder(self):
        """save/load roundtrip works with nested subfolders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = {
                "name": "deeply_nested",
                "data": {"level1": {"level2": {"value": 42}}}
            }
            save(original, f"{tmpdir}/fixtures/nested/deep/item")

            loaded = load(f"{tmpdir}/fixtures/nested/deep/item")

            assert loaded.get_spec()["name"] == "deeply_nested"
            assert loaded.get_spec()["data"]["level1"]["level2"]["value"] == 42


# Define mock entity subclasses here to avoid import order issues
from alienbio.infra.entity import Entity as EntityBase


class MockMolecule(EntityBase, head="TM"):
    """Mock subclass for molecules."""

    __slots__ = ("formula",)

    def __init__(self, name, *, parent=None, dat=None, description="", formula=""):
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.formula = formula

    def attributes(self):
        result = super().attributes()
        if self.formula:
            result["formula"] = self.formula
        return result


class MockCompartment(EntityBase, head="TC"):
    """Mock subclass for compartments."""

    __slots__ = ("volume",)

    def __init__(self, name, *, parent=None, dat=None, description="", volume=0.0):
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.volume = volume

    def attributes(self):
        result = super().attributes()
        if self.volume:
            result["volume"] = self.volume
        return result


class MockReaction(EntityBase, head="TR"):
    """Mock subclass for reactions."""

    __slots__ = ("rate",)

    def __init__(self, name, *, parent=None, dat=None, description="", rate=0.0):
        super().__init__(name, parent=parent, dat=dat, description=description)
        self.rate = rate

    def attributes(self):
        result = super().attributes()
        if self.rate:
            result["rate"] = self.rate
        return result


class TestEntitySaveLoad:
    """Tests for entity tree save/load with type dispatch."""

    def test_save_creates_entities_yaml(self):
        """Entity.save() creates entities.yaml file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a DAT first
            dat = save({"name": "test_world"}, f"{tmpdir}/test/world1")

            # Create entity tree
            from alienbio.infra.entity import Entity

            world = Entity("world", dat=dat)
            Entity("child1", parent=world)

            # Save the entity tree
            world.save()

            # Check entities.yaml exists
            entities_file = Path(tmpdir) / "test" / "world1" / "entities.yaml"
            assert entities_file.exists()

    def test_save_includes_type_field(self):
        """entities.yaml includes type field for each entity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import yaml

            dat = save({"name": "test"}, f"{tmpdir}/test/world2")

            from alienbio.infra.entity import Entity

            world = Entity("world", dat=dat)
            world.save()

            entities_file = Path(tmpdir) / "test" / "world2" / "entities.yaml"
            with open(entities_file) as f:
                data = yaml.safe_load(f)

            assert data["head"] == "Entity"
            assert data["name"] == "world"

    def test_save_subclass_preserves_head(self):
        """Saving a subclass preserves its head name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import yaml

            dat = save({"name": "test"}, f"{tmpdir}/test/comp1")

            comp = MockCompartment("cytoplasm", dat=dat, volume=1.5)
            comp.save()

            entities_file = Path(tmpdir) / "test" / "comp1" / "entities.yaml"
            with open(entities_file) as f:
                data = yaml.safe_load(f)

            assert data["head"] == "TC"  # Short head
            assert data["name"] == "cytoplasm"
            assert data["volume"] == 1.5

    def test_save_mixed_tree(self):
        """Saving a tree with mixed types preserves all heads."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import yaml

            dat = save({"name": "test"}, f"{tmpdir}/test/mixed1")

            from alienbio.infra.entity import Entity

            world = Entity("world", dat=dat)
            cyto = MockCompartment("cytoplasm", parent=world, volume=1.0)
            MockMolecule("glucose", parent=cyto, formula="C6H12O6")
            MockReaction("glycolysis", parent=cyto, rate=0.1)

            world.save()

            entities_file = Path(tmpdir) / "test" / "mixed1" / "entities.yaml"
            with open(entities_file) as f:
                data = yaml.safe_load(f)

            assert data["head"] == "Entity"
            assert data["args"]["cytoplasm"]["head"] == "TC"
            assert data["args"]["cytoplasm"]["volume"] == 1.0
            assert data["args"]["cytoplasm"]["args"]["glucose"]["head"] == "TM"
            assert data["args"]["cytoplasm"]["args"]["glucose"]["formula"] == "C6H12O6"
            assert data["args"]["cytoplasm"]["args"]["glycolysis"]["head"] == "TR"
            assert data["args"]["cytoplasm"]["args"]["glycolysis"]["rate"] == 0.1


class TestEntityLoadWithTypes:
    """Tests for loading entities with type dispatch."""

    def test_load_entity_from_yaml(self):
        """Loading from entities.yaml creates correct types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import yaml

            # Create DAT
            dat = save({"name": "test"}, f"{tmpdir}/test/load1")

            # Write entities.yaml with a MockMolecule
            entities_file = Path(tmpdir) / "test" / "load1" / "entities.yaml"
            entity_data = {
                "head": "TM",
                "name": "glucose",
                "formula": "C6H12O6",
            }
            with open(entities_file, "w") as f:
                yaml.dump(entity_data, f)

            # Load via IO
            from alienbio.infra.io import IO

            io = IO()
            entity = io._load_dat_entity(f"{tmpdir}/test/load1")

            assert isinstance(entity, MockMolecule)
            assert entity.local_name == "glucose"
            # Note: formula won't be loaded yet because _create_entity_from_dict
            # doesn't handle custom fields - that's a future enhancement

    def test_load_with_args(self):
        """Loading entities.yaml with args creates tree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import yaml

            dat = save({"name": "test"}, f"{tmpdir}/test/load2")

            entities_file = Path(tmpdir) / "test" / "load2" / "entities.yaml"
            entity_data = {
                "head": "Entity",
                "name": "world",
                "args": {
                    "cytoplasm": {
                        "head": "TC",
                        "name": "cytoplasm",
                    }
                }
            }
            with open(entities_file, "w") as f:
                yaml.dump(entity_data, f)

            from alienbio.infra.io import IO

            io = IO()
            entity = io._load_dat_entity(f"{tmpdir}/test/load2")

            assert entity.local_name == "world"
            assert "cytoplasm" in entity.children
            assert isinstance(entity.children["cytoplasm"], MockCompartment)


class TestEntityRoundtrip:
    """Tests for complete save/load roundtrip."""

    def test_roundtrip_base_entity(self):
        """Save then load roundtrips a base Entity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from alienbio.infra.entity import Entity
            from alienbio.infra.io import IO

            # Create and save
            dat = save({"name": "test"}, f"{tmpdir}/test/rt1")
            original = Entity("world", dat=dat, description="Test world")
            original.save()

            # Clear cache and reload
            io = IO()
            loaded = io._load_dat_entity(f"{tmpdir}/test/rt1")

            assert loaded.local_name == "world"
            assert loaded.description == "Test world"
            assert isinstance(loaded, Entity)

    def test_roundtrip_preserves_tree_structure(self):
        """Save then load roundtrips tree structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from alienbio.infra.entity import Entity
            from alienbio.infra.io import IO

            dat = save({"name": "test"}, f"{tmpdir}/test/rt2")
            world = Entity("world", dat=dat)
            cyto = Entity("cytoplasm", parent=world)
            Entity("glucose", parent=cyto)
            Entity("atp", parent=cyto)

            world.save()

            io = IO()
            loaded = io._load_dat_entity(f"{tmpdir}/test/rt2")

            assert loaded.local_name == "world"
            assert "cytoplasm" in loaded.children
            assert "glucose" in loaded.children["cytoplasm"].children
            assert "atp" in loaded.children["cytoplasm"].children

    def test_roundtrip_preserves_types(self):
        """Save then load roundtrips entity types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from alienbio.infra.entity import Entity
            from alienbio.infra.io import IO

            dat = save({"name": "test"}, f"{tmpdir}/test/rt3")
            world = Entity("world", dat=dat)
            cyto = MockCompartment("cytoplasm", parent=world)
            MockMolecule("glucose", parent=cyto)

            world.save()

            io = IO()
            loaded = io._load_dat_entity(f"{tmpdir}/test/rt3")

            assert isinstance(loaded, Entity)
            assert isinstance(loaded.children["cytoplasm"], MockCompartment)
            assert isinstance(loaded.children["cytoplasm"].children["glucose"], MockMolecule)

    def test_roundtrip_with_to_str(self):
        """Roundtripped tree has same to_str output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from alienbio.infra.entity import Entity
            from alienbio.infra.io import IO

            dat = save({"name": "test"}, f"{tmpdir}/test/rt4")
            world = Entity("world", dat=dat)
            cyto = MockCompartment("cytoplasm", parent=world)
            MockMolecule("glucose", parent=cyto)
            MockMolecule("atp", parent=cyto)

            original_str = world.to_str()
            world.save()

            io = IO()
            loaded = io._load_dat_entity(f"{tmpdir}/test/rt4")
            loaded_str = loaded.to_str()

            assert loaded_str == original_str
