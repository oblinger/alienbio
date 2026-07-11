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
from alienbio.spec_lang.tags import PyRef, UnsafeSpecError


# =============================================================================
# PyRef Tag Tests
# =============================================================================

class TestPyRefTag:
    """Test the !py tag resolution."""

    def test_pyref_requires_module_attr_format(self, tmp_path):
        """PyRef requires module.attr format, not bare name."""
        ref = PyRef("bare_name")
        with pytest.raises(ValueError, match="requires module.attr format"):
            ref.resolve(str(tmp_path), trusted=True)

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
        result = ref.resolve(str(tmp_path), trusted=True)

        assert callable(result)
        assert result(5) == 10

    def test_pyref_resolves_local_constant(self, tmp_path):
        """PyRef resolves constant from local Python file."""
        py_file = tmp_path / "config.py"
        py_file.write_text("VALUE = 123")

        ref = PyRef("config.VALUE")
        result = ref.resolve(str(tmp_path), trusted=True)

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
        assert ref.resolve(str(tmp_path), trusted=True) == 0.5

        ref2 = PyRef("nested.Config.Inner.value")
        assert ref2.resolve(str(tmp_path), trusted=True) == 99

    def test_pyref_file_not_found(self, tmp_path):
        """PyRef raises ImportError for missing file."""
        ref = PyRef("nonexistent.func")
        with pytest.raises(ImportError, match="not found"):
            ref.resolve(str(tmp_path), trusted=True)

    def test_pyref_attr_not_found(self, tmp_path):
        """PyRef raises AttributeError for missing attribute."""
        py_file = tmp_path / "module.py"
        py_file.write_text("VALUE = 1")

        ref = PyRef("module.NONEXISTENT")
        with pytest.raises(AttributeError):
            ref.resolve(str(tmp_path), trusted=True)


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
        """Fetch resolves Python dict global under an allowlisted module prefix."""
        import sys

        # Create a temporary package structure so the module is reachable
        # under a trusted, registered module prefix (not a bare top-level
        # name — see the security-audit tests below for why that matters).
        pkg_root = tmp_path / "pkgroot"
        catalog = pkg_root / "mycatalog"
        catalog.mkdir(parents=True)
        (pkg_root / "mycatalog" / "__init__.py").write_text("")

        py_file = catalog / "templates.py"
        py_file.write_text("""
ENERGY = {
    "molecule": {
        "name": "Energy from Python",
        "count": 50
    }
}
""")

        sys.path.insert(0, str(pkg_root))
        try:
            bio = Bio()
            bio.add_source_root(catalog, module="mycatalog")

            # "templates.ENERGY" → import mycatalog.templates, get ENERGY
            result = bio.fetch("templates.ENERGY", raw=True)
            assert result["molecule"]["name"] == "Energy from Python"
        finally:
            sys.path.remove(str(pkg_root))
            sys.modules.pop("mycatalog.templates", None)
            sys.modules.pop("mycatalog", None)

    def test_fetch_python_yaml_string_global(self, tmp_path):
        """Fetch parses 'yaml: ' prefixed string globals under an allowlisted prefix."""
        import sys

        pkg_root = tmp_path / "pkgroot"
        catalog = pkg_root / "mycatalog"
        catalog.mkdir(parents=True)
        (pkg_root / "mycatalog" / "__init__.py").write_text("")

        py_file = catalog / "specs.py"
        py_file.write_text('''
SCENARIO = """yaml:
scenario:
  name: Test Scenario
  duration: 1000
"""
''')

        sys.path.insert(0, str(pkg_root))
        try:
            bio = Bio()
            bio.add_source_root(catalog, module="mycatalog")

            result = bio.fetch("specs.SCENARIO", raw=True)
            assert result["scenario"]["name"] == "Test Scenario"
        finally:
            sys.path.remove(str(pkg_root))
            sys.modules.pop("mycatalog.specs", None)
            sys.modules.pop("mycatalog", None)

    def test_empty_module_prefix_no_longer_grants_unrestricted_import(self, tmp_path):
        """module="" ("use path parts directly as module path") is a footgun:
        it decouples the imported module name entirely from any trusted
        prefix, letting an untrusted dotted specifier name an arbitrary
        top-level module. The import allowlist now rejects it — an empty
        module prefix contributes nothing to the allowlist, so the fetch
        must raise UnsafeSpecError and must NOT import (execute) the module.
        """
        import sys

        catalog = tmp_path / "catalog"
        catalog.mkdir()

        marker = tmp_path / "executed.marker"
        py_file = catalog / "templates.py"
        py_file.write_text(f"""
open(r"{marker}", "w").close()
ENERGY = {{"molecule": {{"name": "Energy from Python", "count": 50}}}}
""")

        sys.path.insert(0, str(catalog))
        try:
            bio = Bio()
            bio.add_source_root(catalog, module="")

            with pytest.raises(UnsafeSpecError, match="not in the import allowlist"):
                bio.fetch("templates.ENERGY", raw=True)

            assert not marker.exists(), "module must not have been imported/executed"
            assert "templates" not in sys.modules
        finally:
            sys.path.remove(str(catalog))
            sys.modules.pop("templates", None)


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
        # Note: source root lookup uses {name}.yaml, not index.yaml
        # index.yaml is for DAT folders; {name}.yaml is for source roots
        (catalog / "spec.yaml").write_text("""
reaction:
  name: Test Reaction
  rate: !py helpers.rate_function
  threshold: !py helpers.CONSTANT
""")

        bio = Bio()
        bio.add_source_root(catalog)

        # !py executes Python; the standard (untrusted) fetch path must refuse
        # it rather than run arbitrary agent-authored code.
        from alienbio.spec_lang.tags import UnsafeSpecError
        with pytest.raises(UnsafeSpecError):
            bio.fetch("spec")


class TestPyTagTrust:
    """!py / .py-include are gated behind an explicit trust flag."""

    def test_pyref_untrusted_by_default_raises(self, tmp_path):
        """PyRef.resolve refuses to execute Python unless trusted=True."""
        from alienbio.spec_lang.tags import UnsafeSpecError
        py_file = tmp_path / "helpers.py"
        py_file.write_text("def f(x):\n    return x\n")

        ref = PyRef("helpers.f")
        with pytest.raises(UnsafeSpecError):
            ref.resolve(str(tmp_path))

    def test_pyref_trusted_executes(self, tmp_path):
        """PyRef.resolve executes when explicitly trusted."""
        py_file = tmp_path / "helpers.py"
        py_file.write_text("VALUE = 7\n")

        ref = PyRef("helpers.VALUE")
        assert ref.resolve(str(tmp_path), trusted=True) == 7

    def test_py_include_untrusted_raises(self, tmp_path):
        """A .py !include refuses to execute unless trusted=True."""
        from alienbio.spec_lang.tags import Include, UnsafeSpecError
        py_file = tmp_path / "mod.py"
        py_file.write_text("x = 1\n")

        inc = Include("mod.py")
        with pytest.raises(UnsafeSpecError):
            inc.load(str(tmp_path))

    def test_py_include_trusted_executes(self, tmp_path):
        """A .py !include executes when explicitly trusted."""
        from alienbio.spec_lang.tags import Include
        py_file = tmp_path / "mod.py"
        py_file.write_text("x = 1\n")

        inc = Include("mod.py")
        assert inc.load(str(tmp_path), trusted=True) is None


class TestTopLevelIncludeTrust:
    """Top-level ``include:`` .py execution is gated behind trusted=True.

    Regression for the audit-sec2 hole: ``process._process_python_includes``
    exec_module'd arbitrary .py listed in ``include:`` unconditionally.
    """

    def test_include_py_untrusted_raises_before_exec(self, tmp_path):
        from alienbio.spec_lang.tags import UnsafeSpecError

        marker = tmp_path / "PWNED"
        (tmp_path / "evil.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n")
        (tmp_path / "index.yaml").write_text(
            "include:\n  - evil.py\nchemistry.t:\n  molecules:\n    A: {}\n"
        )

        with pytest.raises(UnsafeSpecError):
            Bio().fetch(str(tmp_path))
        assert not marker.exists()  # exec must NOT have run

    def test_include_py_trusted_executes(self, tmp_path):
        marker = tmp_path / "OK"
        (tmp_path / "reg.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n")
        (tmp_path / "index.yaml").write_text(
            "include:\n  - reg.py\nchemistry.t:\n  molecules:\n    A: {}\n"
        )

        result = Bio().fetch(str(tmp_path), trusted=True)
        assert marker.exists()
        assert "include" not in result


class TestIncludePathContainment:
    """.md/.yaml !include paths are contained for untrusted specs.

    Regression for the audit-sec2 hole: ``tags.Include.load`` accepted absolute
    and ``..`` paths, allowing arbitrary file read from an untrusted spec.
    """

    def test_absolute_include_untrusted_raises(self, tmp_path):
        from alienbio.spec_lang.tags import Include, UnsafeSpecError

        secret = tmp_path / "secret.md"
        secret.write_text("TOP-SECRET")
        with pytest.raises(UnsafeSpecError):
            Include(str(secret)).load()

    def test_parent_escape_untrusted_raises(self, tmp_path):
        from alienbio.spec_lang.tags import Include, UnsafeSpecError

        (tmp_path / "outside.md").write_text("secret")
        sub = tmp_path / "sub"
        sub.mkdir()
        with pytest.raises(UnsafeSpecError):
            Include("../outside.md").load(str(sub))

    def test_parent_escape_no_base_untrusted_raises(self, tmp_path):
        from alienbio.spec_lang.tags import Include, UnsafeSpecError

        with pytest.raises(UnsafeSpecError):
            Include("../../etc/passwd").load()

    def test_contained_relative_include_ok(self, tmp_path):
        from alienbio.spec_lang.tags import Include

        (tmp_path / "inner.md").write_text("inner content")
        assert Include("inner.md").load(str(tmp_path)) == "inner content"

    def test_absolute_include_trusted_ok(self, tmp_path):
        from alienbio.spec_lang.tags import Include

        secret = tmp_path / "secret.md"
        secret.write_text("TOP-SECRET")
        assert Include(str(secret)).load(trusted=True) == "TOP-SECRET"


class TestSafeEvalEscapeGadgets:
    """The AST allowlist must reject known sandbox-escape gadgets."""

    @pytest.mark.parametrize("payload", [
        "().__class__.__base__.__subclasses__()",
        "().__class__",
        "type(1)",
        "getattr((), '__class__')",
        "'{0.__class__}'.format(())",
        "'{}'.format_map({})",
        "(lambda: ().__class__)()",
        "[x for x in ().__class__.__subclasses__()]",
        "(x for x in [1]).gi_frame",
        "(lambda: x).__globals__",
        "[].append.__self__",
        "__import__('os')",
        "eval('1')",
        "open('/etc/passwd')",
        "().__class__.mro()",
        "object.__subclasses__",
    ])
    def test_gadget_rejected(self, payload):
        from alienbio.spec_lang.safe_eval import safe_eval, UnsafeExpressionError
        from alienbio.spec_lang.eval import SAFE_BUILTINS

        with pytest.raises((UnsafeExpressionError, NameError, AttributeError,
                            TypeError, SyntaxError)):
            safe_eval(payload, dict(SAFE_BUILTINS))

    def test_legit_expressions_still_work(self):
        from alienbio.spec_lang.safe_eval import safe_eval
        from alienbio.spec_lang.eval import SAFE_BUILTINS

        ns = dict(SAFE_BUILTINS)
        ns["state"] = {"A": 5}
        assert safe_eval("abs(-3)", ns) == 3
        assert safe_eval("max([1, 2, 3])", ns) == 3
        assert safe_eval("state.get('A', 0)", ns) == 5


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling for fetch resolution."""

    def test_not_found_lists_searched_roots(self, tmp_path):
        """FileNotFoundError lists all searched source roots.

        Uses an "alienbio."-prefixed specifier so the import allowlist
        check passes and the (nonexistent) module falls through to the
        normal "not found in source roots" path, rather than being
        rejected outright as an unregistered/untrusted module.
        """
        bio = Bio()
        bio.add_source_root(tmp_path / "root1")
        bio.add_source_root(tmp_path / "root2")

        with pytest.raises(FileNotFoundError) as exc_info:
            bio.fetch("alienbio.nonexistent_module_xyz.path")

        assert "root1" in str(exc_info.value)
        assert "root2" in str(exc_info.value)

    def test_empty_source_roots_falls_through(self, tmp_path):
        """With source roots, non-existent dotted path raises error.

        Uses an "alienbio."-prefixed specifier so the import allowlist
        check passes and the (nonexistent) module falls through to the
        normal "not found in source roots" path.
        """
        bio = Bio()
        # Bio auto-configures catalog source root

        # Should raise error for non-existent path
        with pytest.raises(FileNotFoundError, match="not found in source roots"):
            bio.fetch("alienbio.some.dotted.path")
