"""Tests for YAML/Python coexistence in fetch().

Tests TODO 2026-01-14 #10: YAML/Python Fetch Implementation
- !py tag resolution (local to source file)
- Python module global loading (dict and "yaml: " string)
- source_roots config with path + module pairs
- YAML takes precedence over Python
"""

import pytest
import tempfile
from pathlib import Path

from alienbio.spec_lang.bio import Bio, SourceRoot
from alienbio.spec_lang.tags import PyRef


# =============================================================================
# PyRef Tag Tests
# =============================================================================

class TestPyRefTag:
    """Test the !py tag resolution."""

    def test_pyref_requires_module_attr_format(self, tmp_path):
        """PyRef requires module.attr format, not bare name."""
        ref = PyRef("bare_name")
        with pytest.raises(ValueError, match="requires module.attr format"):
            ref.resolve(str(tmp_path))

    def test_pyref_resolves_local_function(self, tmp_path):
        """PyRef resolves function from local Python file."""
        # Create a Python file with a function
        py_file = tmp_path / "helpers.py"
        py_file.write_text("""
def compute_rate(x):
    return x * 2

CONSTANT = 42
""")

        ref = PyRef("helpers.compute_rate")
        result = ref.resolve(str(tmp_path))

        assert callable(result)
        assert result(5) == 10

    def test_pyref_resolves_local_constant(self, tmp_path):
        """PyRef resolves constant from local Python file."""
        py_file = tmp_path / "config.py"
        py_file.write_text("VALUE = 123")

        ref = PyRef("config.VALUE")
        result = ref.resolve(str(tmp_path))

        assert result == 123

    def test_pyref_resolves_nested_attr(self, tmp_path):
        """PyRef resolves nested attribute path."""
        py_file = tmp_path / "nested.py"
        py_file.write_text("""
class Config:
    rate = 0.5
    class Inner:
        value = 99
""")

        ref = PyRef("nested.Config.rate")
        assert ref.resolve(str(tmp_path)) == 0.5

        ref2 = PyRef("nested.Config.Inner.value")
        assert ref2.resolve(str(tmp_path)) == 99

    def test_pyref_file_not_found(self, tmp_path):
        """PyRef raises ImportError for missing file."""
        ref = PyRef("nonexistent.func")
        with pytest.raises(ImportError, match="not found"):
            ref.resolve(str(tmp_path))

    def test_pyref_attr_not_found(self, tmp_path):
        """PyRef raises AttributeError for missing attribute."""
        py_file = tmp_path / "module.py"
        py_file.write_text("VALUE = 1")

        ref = PyRef("module.NONEXISTENT")
        with pytest.raises(AttributeError):
            ref.resolve(str(tmp_path))


# =============================================================================
# Source Root Configuration Tests
# =============================================================================

class TestSourceRootConfig:
    """Test source root configuration."""

    def test_add_source_root(self):
        """Can add source roots to Bio instance."""
        bio = Bio()
        # Bio auto-configures catalog as source root, so start with 1
        initial_count = len(bio._source_roots)

        bio.add_source_root("/tmp/catalog", module="myproject.catalog")
        assert len(bio._source_roots) == initial_count + 1
        assert bio._source_roots[-1].module == "myproject.catalog"

    def test_source_root_path_expansion(self):
        """Source root paths are expanded."""
        bio = Bio()
        bio.add_source_root("~/catalog")

        # Path should be expanded
        assert "~" not in str(bio._source_roots[0].path)

    def test_multiple_source_roots(self):
        """Multiple source roots are searched in order."""
        bio = Bio()
        initial_count = len(bio._source_roots)
        bio.add_source_root("/first")
        bio.add_source_root("/second")

        assert len(bio._source_roots) == initial_count + 2
        # New roots are added after auto-configured ones
        assert str(bio._source_roots[-2].path) == "/first"
        assert str(bio._source_roots[-1].path) == "/second"


# =============================================================================
# YAML File Resolution Tests
# =============================================================================

class TestYamlResolution:
    """Test YAML file resolution from source roots."""

    def test_fetch_yaml_file(self, tmp_path):
        """Fetch resolves dotted path to YAML file."""
        # Create source root structure
        catalog = tmp_path / "catalog"
        catalog.mkdir()
        (catalog / "mute").mkdir()
        (catalog / "mute" / "mol").mkdir()

        yaml_file = catalog / "mute" / "mol" / "energy.yaml"
        yaml_file.write_text("""
molecule:
  name: Energy Molecule
  initial_count: 100
""")

        bio = Bio()
        bio.add_source_root(catalog)

        result = bio.fetch("mute.mol.energy", raw=True)
        assert result["molecule"]["name"] == "Energy Molecule"

    def test_fetch_yaml_with_dig(self, tmp_path):
        """Fetch digs into YAML structure."""
        catalog = tmp_path / "catalog"
        catalog.mkdir()

        yaml_file = catalog / "config.yaml"
        yaml_file.write_text("""
database:
  host: localhost
  port: 5432
cache:
  ttl: 300
""")

        bio = Bio()
        bio.add_source_root(catalog)

        result = bio.fetch("config.database", raw=True)
        assert result["host"] == "localhost"

        result = bio.fetch("config.database.port", raw=True)
        assert result == 5432

    def test_fetch_index_yaml_fallback(self, tmp_path):
        """Fetch falls back to index.yaml in directory."""
        catalog = tmp_path / "catalog"
        (catalog / "mute" / "org").mkdir(parents=True)

        index_file = catalog / "mute" / "org" / "index.yaml"
        index_file.write_text("""
organism:
  type: autotroph
  metabolism: photosynthesis
""")

        bio = Bio()
        bio.add_source_root(catalog)

        result = bio.fetch("mute.org", raw=True)
        assert result["organism"]["type"] == "autotroph"

    def test_yaml_file_preferred_over_index(self, tmp_path):
        """YAML file is preferred over directory with index.yaml."""
        catalog = tmp_path / "catalog"
        catalog.mkdir()

        # Create both file and directory
        (catalog / "item.yaml").write_text("source: file")
        (catalog / "item").mkdir()
        (catalog / "item" / "index.yaml").write_text("source: index")

        bio = Bio()
        bio.add_source_root(catalog)

        result = bio.fetch("item", raw=True)
        assert result["source"] == "file"


# =============================================================================
# Python Global Resolution Tests
# =============================================================================

class TestPythonGlobalResolution:
    """Test Python module global resolution from source roots."""

    def test_fetch_python_dict_global(self, tmp_path):
        """Fetch resolves Python dict global when no YAML exists."""
        import sys

        # Create a temporary module structure
        # catalog/templates.py with ENERGY global
        catalog = tmp_path / "catalog"
        catalog.mkdir()

        py_file = catalog / "templates.py"
        py_file.write_text("""
ENERGY = {
    "molecule": {
        "name": "Energy from Python",
        "count": 50
    }
}
""")

        # Add catalog to path so templates can be imported
        sys.path.insert(0, str(catalog))
        try:
            bio = Bio()
            # module="" means use path parts directly as module path
            bio.add_source_root(catalog, module="")

            # "templates.ENERGY" → import templates, get ENERGY
            result = bio.fetch("templates.ENERGY", raw=True)
            assert result["molecule"]["name"] == "Energy from Python"
        finally:
            sys.path.remove(str(catalog))

    def test_fetch_python_yaml_string_global(self, tmp_path):
        """Fetch parses 'yaml: ' prefixed string globals."""
        import sys

        catalog = tmp_path / "catalog"
        catalog.mkdir()

        py_file = catalog / "specs.py"
        py_file.write_text('''
SCENARIO = """yaml:
scenario:
  name: Test Scenario
  duration: 1000
"""
''')

        sys.path.insert(0, str(catalog))
        try:
            bio = Bio()
            bio.add_source_root(catalog, module="")

            result = bio.fetch("specs.SCENARIO", raw=True)
            assert result["scenario"]["name"] == "Test Scenario"
        finally:
            sys.path.remove(str(catalog))


# =============================================================================
# YAML/Python Precedence Tests
# =============================================================================

class TestYamlPythonPrecedence:
    """Test that YAML takes precedence over Python."""

    def test_yaml_preferred_over_python(self, tmp_path):
        """When both YAML and Python exist, YAML wins."""
        import sys

        catalog = tmp_path / "catalog"
        catalog.mkdir()

        # Create YAML file
        (catalog / "config.yaml").write_text("""
source: yaml
value: 100
""")

        # Create Python module with same name pattern
        (catalog / "config_py.py").write_text("""
CONFIG = {
    "source": "python",
    "value": 200
}
""")

        bio = Bio()
        bio.add_source_root(catalog, module="catalog")

        # Should get YAML content
        result = bio.fetch("config", raw=True)
        assert result["source"] == "yaml"
        assert result["value"] == 100


# =============================================================================
# !py Tag Integration Tests
# =============================================================================

class TestPyTagIntegration:
    """Test !py tag integration in YAML processing."""

    def test_py_tag_in_yaml(self, tmp_path):
        """!py tag in YAML resolves local Python."""
        catalog = tmp_path / "catalog"
        catalog.mkdir()

        # Create Python helper
        (catalog / "helpers.py").write_text("""
def rate_function(x):
    return x * 0.5

CONSTANT = 42
""")

        # Create YAML that references Python
        (catalog / "spec.yaml").write_text("""
reaction:
  name: Test Reaction
  rate: !py helpers.rate_function
  threshold: !py helpers.CONSTANT
""")

        bio = Bio()
        bio.add_source_root(catalog)

        result = bio.fetch("spec")
        assert result["reaction"]["name"] == "Test Reaction"
        assert callable(result["reaction"]["rate"])
        assert result["reaction"]["rate"](10) == 5.0
        assert result["reaction"]["threshold"] == 42


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling for fetch resolution."""

    def test_not_found_lists_searched_roots(self, tmp_path):
        """FileNotFoundError lists all searched source roots."""
        bio = Bio()
        bio.add_source_root(tmp_path / "root1")
        bio.add_source_root(tmp_path / "root2")

        with pytest.raises(FileNotFoundError) as exc_info:
            bio.fetch("nonexistent.path")

        assert "root1" in str(exc_info.value)
        assert "root2" in str(exc_info.value)

    def test_empty_source_roots_falls_through(self, tmp_path):
        """With source roots, non-existent dotted path raises error."""
        bio = Bio()
        # Bio auto-configures catalog source root

        # Should raise error for non-existent path
        with pytest.raises(FileNotFoundError, match="not found in source roots"):
            bio.fetch("some.dotted.path")
