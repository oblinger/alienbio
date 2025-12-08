"""Tests for dvc_dat integration via alienbio operators."""

import tempfile
from pathlib import Path

import pytest

from alienbio import Context, Dat, create, ctx, do, load, save, set_context
from dvc_dat import do as dvc_do


class TestDoResolves:
    """Tests for do() name resolution via dvc_dat."""

    def test_do_resolves_fixture(self):
        """do() resolves fixtures.simple to fixture data."""
        result = do("fixtures.simple")
        assert result["name"] == "simple_fixture"
        assert result["value"] == 42

    def test_do_resolves_molecules_fixture(self):
        """do() resolves fixtures.molecules to molecule data."""
        result = do("fixtures.molecules")
        assert result["name"] == "test_molecules"
        assert len(result["molecules"]) == 3

    def test_do_resolves_kegg1_fixture(self):
        """do() resolves fixtures.kegg1 to biochemistry model stub."""
        result = do("fixtures.kegg1")
        assert result["name"] == "kegg1"
        assert result["type"] == "biochemistry_model"

    def test_do_returns_dict(self):
        """do() returns a dict from YAML spec files."""
        result = do("fixtures.simple")
        assert isinstance(result, dict)

    def test_do_missing_raises_keyerror(self):
        """do() raises KeyError for missing names."""
        with pytest.raises(KeyError):
            do("nonexistent.thing")


class TestCreate:
    """Tests for create() instantiation via dvc_dat."""

    def test_create_from_string_returns_dat(self):
        """create() from string spec returns a Dat."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            result = create("fixtures.simple", path=f"{tmpdir}/create_str")
            assert isinstance(result, Dat)
            assert result.get_spec()["name"] == "simple_fixture"

    def test_create_from_dict_returns_dat(self):
        """create() from dict spec returns a Dat."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

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
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            result = save({"name": "test", "value": 123}, "test/item1")

            spec_path = Path(tmpdir) / "test" / "item1" / "_spec_.yaml"
            assert spec_path.exists()
            assert isinstance(result, Dat)

    def test_save_returns_dat(self):
        """save() returns a Dat object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            result = save({"name": "test"}, "test/item2")

            assert isinstance(result, Dat)

    def test_load_returns_dat(self):
        """load() returns a Dat object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            # Create a Dat first
            save({"name": "test_load"}, "test/load_test")

            # Load it
            result = load(Path(tmpdir) / "test" / "load_test")

            assert isinstance(result, Dat)

    def test_save_load_roundtrip_dict(self):
        """save() then load() round-trips a dict through Dat."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            original = {"name": "roundtrip_test", "value": 42, "nested": {"a": 1}}
            save(original, "roundtrip/test1")

            loaded = load(Path(tmpdir) / "roundtrip" / "test1")

            assert loaded.get_spec()["name"] == "roundtrip_test"
            assert loaded.get_spec()["value"] == 42
            assert loaded.get_spec()["nested"]["a"] == 1

    def test_save_wraps_non_dict_in_value_key(self):
        """save() wraps non-dict values in a 'value' key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            save("just a string", "test/string_val")

            loaded = load(Path(tmpdir) / "test" / "string_val")
            assert loaded.get_spec()["value"] == "just a string"


class TestDatOperations:
    """Tests for Dat-specific operations."""

    def test_dat_has_spec(self):
        """Dat objects have a _spec attribute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            save({"key": "value"}, "test/spec_test")
            loaded = load(Path(tmpdir) / "test" / "spec_test")

            assert hasattr(loaded, "spec")
            assert loaded.get_spec()["key"] == "value"

    def test_dat_has_path(self):
        """Dat objects have a _path attribute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            save({"key": "value"}, "test/path_test")
            loaded = load(Path(tmpdir) / "test" / "path_test")

            assert hasattr(loaded, "_path")
            assert "path_test" in str(loaded._path)


class TestYamlStringSpec:
    """Tests for YAML string specs (yaml prefix pattern)."""

    def test_do_loads_yaml_string_spec(self):
        """do() parses YAML string specs prefixed with 'yaml'."""
        result = do("fixtures.experiment_template")
        assert isinstance(result, dict)
        assert result["name"] == "experiment_from_yaml"
        assert result["dat"]["kind"] == "Dat"
        assert result["parameters"]["learning_rate"] == 0.01

    def test_create_from_yaml_string_spec(self):
        """create() works with YAML string spec names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            dat = create("fixtures.experiment_template", path=f"{tmpdir}/yaml_exp")
            assert isinstance(dat, Dat)
            assert dat.get_spec()["name"] == "experiment_from_yaml"
            assert dat.get_spec()["parameters"]["epochs"] == 100


class TestCallableFunctions:
    """Tests for loading and calling Python functions via do-system."""

    def test_do_load_returns_function(self):
        """dvc_do.load() returns a function without calling it."""
        fn = dvc_do.load("fixtures.process_data")
        assert callable(fn)

    def test_do_calls_function_with_args(self):
        """do() calls a function when passed arguments."""
        result = do("fixtures.process_data", items=["a", "b", "c"])
        assert result["count"] == 3
        assert result["first"] == "a"
        assert result["last"] == "c"

    def test_do_calls_function_with_empty_list(self):
        """do() calls function with empty list."""
        result = do("fixtures.process_data", items=[])
        assert result["count"] == 0
        assert result["first"] is None

    def test_do_load_compute_metric_function(self):
        """dvc_do.load() can load compute_metric function."""
        fn = dvc_do.load("fixtures.compute_metric")
        assert callable(fn)
        # Call without dat parameter
        result = fn(multiplier=2)
        assert result == 84  # 42 * 2

    def test_do_calls_function_with_default_args(self):
        """do() calls a function that has default args."""
        # compute_metric with no args returns 42 (default multiplier=1)
        result = do("fixtures.compute_metric")
        assert result == 42


class TestDatWithProperSpec:
    """Tests for DATs with proper dat: section specs."""

    def test_create_from_spec_with_dat_section(self):
        """create() with spec that has dat: section works correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            dat = create("fixtures.simple_dat", path=f"{tmpdir}/simple_dat_test")
            assert isinstance(dat, Dat)
            assert dat.get_spec()["name"] == "simple_dat"
            assert dat.get_spec()["value"] == 100
            assert dat.get_spec()["dat"]["kind"] == "Dat"

    def test_create_runnable_experiment(self):
        """create() with runnable spec (dat.do defined) works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            dat = create("fixtures.runnable_experiment", path=f"{tmpdir}/run_exp")
            assert isinstance(dat, Dat)
            assert dat.get_spec()["dat"]["do"] == "fixtures.run_compute_metric"
            assert dat.get_spec()["value"] == 7

    def test_dat_run_executes_do_function(self):
        """dat.run() executes the function specified in dat.do."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            dat = create("fixtures.runnable_experiment", path=f"{tmpdir}/run_test")

            # Run the DAT - this should call fixtures.compute_metric with dat
            success, results = dat.run()

            assert success is True
            # compute_metric returns value * multiplier (7 * 1 = 7)
            assert results.get("return") == 7


class TestDataFolderOperations:
    """Tests for saving/loading DATs from the data folder."""

    def test_save_to_fixtures_subfolder(self):
        """save() can write to a fixtures/ subfolder in data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            dat = save({"name": "in_fixtures", "value": 999}, "fixtures/test_item")

            assert isinstance(dat, Dat)
            spec_path = Path(tmpdir) / "fixtures" / "test_item" / "_spec_.yaml"
            assert spec_path.exists()

    def test_load_from_fixtures_subfolder(self):
        """load() can read from a fixtures/ subfolder in data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            # Save first
            save({"name": "loadable", "value": 123}, "fixtures/loadable_item")

            # Load it back
            dat = load(Path(tmpdir) / "fixtures" / "loadable_item")

            assert isinstance(dat, Dat)
            assert dat.get_spec()["name"] == "loadable"
            assert dat.get_spec()["value"] == 123

    def test_roundtrip_nested_subfolder(self):
        """save/load roundtrip works with nested subfolders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = Context(data_path=Path(tmpdir))
            set_context(context)

            original = {
                "name": "deeply_nested",
                "data": {"level1": {"level2": {"value": 42}}}
            }
            save(original, "fixtures/nested/deep/item")

            loaded = load(Path(tmpdir) / "fixtures" / "nested" / "deep" / "item")

            assert loaded.get_spec()["name"] == "deeply_nested"
            assert loaded.get_spec()["data"]["level1"]["level2"]["value"] == 42
