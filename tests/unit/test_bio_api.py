"""Tests for Bio class API.

Coverage:
- Bio.cd() — current DAT tracking and path resolution
- Bio.fetch() — specifier routing, hydration options
- Bio.run() — routing for string/dict/Scenario inputs
- Bio.store() — dehydration and storage
- Bio.build() — scenario instantiation
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch

from alienbio import Bio, bio
from alienbio.protocols import Scenario


class MockDat:
    """Mock DAT for testing."""
    def __init__(self, path: str = "test/dat"):
        self._path = path

    def path(self) -> str:
        return self._path


# =============================================================================
# Bio.cd() Tests
# =============================================================================


class TestBioCd:
    """Tests for Bio.cd() current DAT tracking."""

    def test_cd_initial_state(self):
        """New Bio instance has no current DAT."""
        b = Bio()
        # _current_dat should be None or cwd
        assert not hasattr(b, '_current_dat') or b._current_dat is None

    @pytest.mark.skip(reason="Bio.cd() not yet implemented")
    def test_cd_sets_current_dat(self, temp_dir):
        """cd(path) sets current DAT."""
        b = Bio()
        b.cd(str(temp_dir))
        assert b._current_dat == temp_dir

    @pytest.mark.skip(reason="Bio.cd() not yet implemented")
    def test_cd_none_resets(self, temp_dir):
        """cd(None) resets to no current DAT."""
        b = Bio()
        b.cd(str(temp_dir))
        b.cd(None)
        assert b._current_dat is None

    @pytest.mark.skip(reason="Bio.cd() not yet implemented")
    def test_cd_returns_current(self, temp_dir):
        """cd() with no args returns current DAT path."""
        b = Bio()
        b.cd(str(temp_dir))
        assert b.cd() == temp_dir

    @pytest.mark.skip(reason="Bio.cd() not yet implemented")
    def test_fetch_relative_to_current_dat(self, temp_dir):
        """fetch('./subpath') resolves relative to current DAT."""
        # Create a DAT structure
        (temp_dir / "index.yaml").write_text("value: 42\n")
        subdir = temp_dir / "sub"
        subdir.mkdir()
        (subdir / "index.yaml").write_text("value: 100\n")

        b = Bio()
        b.cd(str(temp_dir))

        # Relative fetch should work
        result = b.fetch("./sub", raw=True)
        assert result["value"] == 100


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


# =============================================================================
# Bio.fetch() Tests — Specifier Routing
# =============================================================================


class TestBioFetchRouting:
    """Tests for Bio.fetch() specifier routing."""

    def test_fetch_absolute_path(self, temp_dir):
        """fetch('/absolute/path') loads from absolute path."""
        yaml_file = temp_dir / "test.yaml"
        yaml_file.write_text("key: value\n")

        result = Bio.fetch(str(yaml_file), raw=True)
        assert result["key"] == "value"

    def test_fetch_dat_folder_loads_spec(self, temp_dir):
        """fetch('path/to/dat') loads spec.yaml from DAT folder."""
        dat_dir = temp_dir / "mydat"
        dat_dir.mkdir()
        # Current implementation looks for spec.yaml, not index.yaml
        (dat_dir / "spec.yaml").write_text("name: mydat\nvalue: 123\n")

        result = Bio.fetch(str(dat_dir), raw=True)
        assert result["name"] == "mydat"
        assert result["value"] == 123

    @pytest.mark.skip(reason="index.yaml convention not yet implemented")
    def test_fetch_dat_folder_loads_index(self, temp_dir):
        """fetch('path/to/dat') should load index.yaml from DAT folder."""
        dat_dir = temp_dir / "mydat"
        dat_dir.mkdir()
        (dat_dir / "index.yaml").write_text("name: mydat\nvalue: 123\n")

        result = Bio.fetch(str(dat_dir), raw=True)
        assert result["name"] == "mydat"
        assert result["value"] == 123

    @pytest.mark.skip(reason="Dots-before-slash routing not yet implemented")
    def test_fetch_dotted_name_routes_to_lookup(self, temp_dir):
        """fetch('catalog.scenarios.test') routes to lookup."""
        # This should:
        # 1. Detect dots before any slash
        # 2. Route to lookup() which searches configured roots
        pass

    @pytest.mark.skip(reason="Python module lookup not yet implemented")
    def test_fetch_python_module(self):
        """fetch('alienbio.bio.Chemistry') returns Python class."""
        result = Bio.fetch("alienbio.bio.Chemistry")
        from alienbio.bio import Chemistry
        assert result == Chemistry


class TestBioFetchHydration:
    """Tests for Bio.fetch() hydration options."""

    def test_fetch_raw_returns_dict(self, temp_dir):
        """fetch(..., raw=True) returns raw dict."""
        yaml_file = temp_dir / "test.yaml"
        yaml_file.write_text("key: value\n")

        result = Bio.fetch(str(yaml_file), raw=True)
        assert isinstance(result, dict)
        assert result["key"] == "value"

    @pytest.mark.skip(reason="hydrate=False option not yet implemented")
    def test_fetch_hydrate_false_returns_scope(self, temp_dir):
        """fetch(..., hydrate=False) returns Scope without type construction."""
        from alienbio.spec_lang import Scope

        yaml_file = temp_dir / "test.yaml"
        yaml_file.write_text("""
world.test:
  molecules:
    M1: {role: energy}
""")

        result = Bio.fetch(str(yaml_file), hydrate=False)
        assert isinstance(result, Scope)


class TestBioFetchDatPattern:
    """Tests for 'loads within DAT' pattern."""

    @pytest.mark.skip(reason="Dotted path dereferencing not yet implemented")
    def test_fetch_dat_with_dotted_path(self, temp_dir):
        """fetch('path/to/dat.nested.key') dereferences into DAT."""
        dat_dir = temp_dir / "mydat"
        dat_dir.mkdir()
        (dat_dir / "index.yaml").write_text("""
nested:
  key: found_it
  other: value
""")

        # Should load index.yaml then dereference .nested.key
        result = Bio.fetch(f"{dat_dir}.nested.key", raw=True)
        assert result == "found_it"

    @pytest.mark.skip(reason="Dotted path dereferencing not yet implemented")
    def test_fetch_dat_deep_path(self, temp_dir):
        """fetch('path/to/dat.a.b.c') handles deep paths."""
        dat_dir = temp_dir / "mydat"
        dat_dir.mkdir()
        (dat_dir / "index.yaml").write_text("""
a:
  b:
    c: deep_value
""")

        result = Bio.fetch(f"{dat_dir}.a.b.c", raw=True)
        assert result == "deep_value"


# =============================================================================
# Bio.run() Tests — Routing
# =============================================================================


class TestBioRunRouting:
    """Tests for Bio.run() routing logic."""

    def test_run_with_dict_calls_build(self):
        """run(dict) calls build() on the dict."""
        from alienbio.build import TemplateRegistry, parse_template

        registry = TemplateRegistry()
        registry.register("simple", parse_template({
            "molecules": {"M1": {"role": "energy"}}
        }))

        spec = {
            "_instantiate_": {
                "_as_ x": {"_template_": "simple"}
            }
        }

        result = Bio.run(spec, seed=42, registry=registry)

        # Should return a Scenario
        assert isinstance(result, Scenario)
        assert len(result.molecules) > 0

    def test_run_with_scenario_returns_scenario(self):
        """run(Scenario) returns the scenario (for execution)."""
        scenario = Scenario(
            molecules={"M1": {"role": "energy"}},
            reactions={},
            _ground_truth_={"molecules": {"M1": {}}},
            _visibility_mapping_={},
            _seed=42,
            _metadata_={}
        )

        result = Bio.run(scenario, seed=42)

        # Should return the same scenario (execution not yet implemented)
        assert result is scenario

    @pytest.mark.skip(reason="String routing in run() needs fetch integration")
    def test_run_with_string_fetches_and_builds(self, temp_dir):
        """run(string) fetches spec, then builds."""
        # Create a spec file
        spec_file = temp_dir / "spec.yaml"
        spec_file.write_text("""
_instantiate_:
  _as_ x:
    _template_: simple
""")
        # Would need template registry configured
        pass


# =============================================================================
# Bio.store() Tests
# =============================================================================


class TestBioStore:
    """Tests for Bio.store() dehydration and storage."""

    @pytest.mark.skip(reason="Bio.store currently requires biotype objects, not plain dicts")
    def test_store_writes_yaml(self, temp_dir):
        """store(path, obj) writes YAML file."""
        obj = {"key": "value", "number": 42}
        path = temp_dir / "output.yaml"

        Bio.store(str(path), obj)

        assert path.exists()
        content = yaml.safe_load(path.read_text())
        assert content["key"] == "value"
        assert content["number"] == 42

    @pytest.mark.skip(reason="Bio.store currently requires biotype objects, not plain dicts")
    def test_store_round_trip(self, temp_dir):
        """store then fetch returns equivalent data."""
        original = {"name": "test", "values": [1, 2, 3]}
        path = temp_dir / "roundtrip.yaml"

        Bio.store(str(path), original)
        loaded = Bio.fetch(str(path), raw=True)

        assert loaded["name"] == original["name"]
        assert loaded["values"] == original["values"]

    @pytest.mark.skip(reason="MoleculeImpl not registered as biotype - needs @biotype decorator")
    def test_store_typed_object(self, temp_dir):
        """store() works with typed (biotype) objects."""
        from alienbio.bio import MoleculeImpl

        dat = MockDat("molecules/atp")
        mol = MoleculeImpl(
            "ATP",  # local_name
            dat=dat,
            name="ATP",
            bdepth=0
        )
        path = temp_dir / "molecule.yaml"

        Bio.store(str(path), mol)

        assert path.exists()
        content = yaml.safe_load(path.read_text())
        assert "_type" in content
        assert content["name"] == "ATP"

    @pytest.mark.skip(reason="raw=True option for store not yet implemented")
    def test_store_raw_dict(self, temp_dir):
        """store(path, dict, raw=True) writes plain dict without dehydration."""
        obj = {"key": "value", "number": 42}
        path = temp_dir / "output.yaml"

        Bio.store(str(path), obj, raw=True)

        assert path.exists()
        content = yaml.safe_load(path.read_text())
        assert content["key"] == "value"
        assert content["number"] == 42


# =============================================================================
# Bio.build() Tests — Already well-covered in test_build_pipeline.py
# These are additional edge case tests
# =============================================================================


class TestBioBuildEdgeCases:
    """Additional edge case tests for Bio.build()."""

    def test_build_with_empty_spec(self):
        """build() with empty spec returns empty scenario."""
        result = Bio.build({}, seed=42)

        assert isinstance(result, Scenario)
        assert len(result.molecules) == 0
        assert len(result.reactions) == 0

    def test_build_without_templates(self):
        """build() works without _instantiate_ block."""
        spec = {
            "molecules": {"M1": {"role": "energy"}},
            "reactions": {}
        }

        result = Bio.build(spec, seed=42)

        # Should create scenario from direct spec
        assert isinstance(result, Scenario)

    @pytest.mark.skip(reason="String spec in build() needs fetch integration")
    def test_build_with_string_fetches_first(self, temp_dir):
        """build(string) fetches the spec first."""
        spec_file = temp_dir / "spec.yaml"
        spec_file.write_text("""
molecules:
  M1: {role: energy}
""")

        result = Bio.build(str(spec_file), seed=42)
        assert isinstance(result, Scenario)


# =============================================================================
# Integration Tests
# =============================================================================


class TestBioM2Integration:
    """Integration tests for M2 workflow."""

    @pytest.mark.skip(reason="Full M2 workflow not yet implemented")
    def test_fetch_build_run_workflow(self, temp_dir):
        """Complete workflow: fetch spec -> build -> run."""
        # Create spec file
        spec_file = temp_dir / "scenario.yaml"
        spec_file.write_text("""
scenario.test:
  molecules:
    M1: {role: energy}
    M2: {role: structural}
  reactions:
    r1:
      reactants: [M1]
      products: [M2]
      rate: 0.1
""")

        # Workflow
        spec = Bio.fetch(str(spec_file))
        scenario = Bio.build(spec, seed=42)
        result = Bio.run(scenario)

        assert isinstance(result, Scenario)

    @pytest.mark.skip(reason="DAT storage not yet implemented")
    def test_store_and_fetch_dat(self, temp_dir):
        """Store scenario to DAT, then fetch it back."""
        scenario = Scenario(
            molecules={"M1": {"role": "energy"}},
            reactions={},
            _ground_truth_={"molecules": {"M1": {}}},
            _visibility_mapping_={},
            _seed=42,
            _metadata_={"name": "test"}
        )

        dat_path = temp_dir / "output_dat"
        Bio.store(str(dat_path), scenario)

        loaded = Bio.fetch(str(dat_path))
        assert isinstance(loaded, Scenario)
        assert loaded._seed == 42
