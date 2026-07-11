"""Security tests for the spec_lang import allowlist (RCE fix).

ABIO specs are agent-authored / untrusted. Two dotted-specifier code paths
end up calling ``importlib.import_module(module_path)``:

- ``resolve.load_from_python_global`` (reached via ``Bio._fetch_from_source_roots``
  -> ``resolve_dotted_in_source_root``), for a dotted path resolved under a
  registered source root's Python module prefix.
- ``Bio._fetch_python_import``, the direct "bare" dotted-specifier import path
  (e.g. ``bio.fetch("alienbio.bio.Chemistry")``).

Both must refuse to import a module unless it is trusted: the "alienbio"
framework package (or a submodule of it), or a dotted submodule of some
*registered* source root's module prefix. An arbitrary attacker-chosen
top-level module name (e.g. from ``bio.fetch("evilmod.GLOBAL")``) must be
rejected with ``UnsafeSpecError`` *before* any import is attempted.
"""

import sys

import pytest

from alienbio.spec_lang.bio import Bio
from alienbio.spec_lang.resolve import SourceRoot, _is_allowed_import, load_from_python_global
from alienbio.spec_lang.tags import UnsafeSpecError


# =============================================================================
# _is_allowed_import — unit tests for the allowlist predicate
# =============================================================================

class TestIsAllowedImport:
    def test_alienbio_top_level_allowed(self):
        assert _is_allowed_import("alienbio", []) is True

    def test_alienbio_submodule_allowed(self):
        assert _is_allowed_import("alienbio.bio.chemistry", []) is True

    def test_lookalike_top_level_not_allowed(self):
        """'alienbiological' shares a prefix string but is not a submodule."""
        assert _is_allowed_import("alienbiological", []) is False

    def test_registered_root_module_prefix_allowed(self):
        root = SourceRoot(path=".", module="myproject.catalog")
        assert _is_allowed_import("myproject.catalog", [root]) is True
        assert _is_allowed_import("myproject.catalog.mute.mol", [root]) is True

    def test_unrelated_module_not_allowed(self):
        root = SourceRoot(path=".", module="myproject.catalog")
        assert _is_allowed_import("evilmod", [root]) is False
        assert _is_allowed_import("evilmod.SOMEGLOBAL".rsplit(".", 1)[0], [root]) is False

    def test_empty_module_prefix_grants_nothing(self):
        """A source root registered with module="" contributes no prefix —
        it must not act as a wildcard allowing arbitrary imports."""
        root = SourceRoot(path=".", module="")
        assert _is_allowed_import("evilmod", [root]) is False
        assert _is_allowed_import("templates", [root]) is False

    def test_no_source_roots_only_alienbio_allowed(self):
        assert _is_allowed_import("evilmod", []) is False


# =============================================================================
# Exploit closed: arbitrary/unregistered module names are rejected
# =============================================================================

class TestExploitClosed:
    """Reproduces the confirmed exploit: bio.fetch("evilmod.GLOBAL") must not
    import an attacker-controlled module."""

    def test_direct_import_site_rejects_unregistered_module(self, tmp_path, monkeypatch):
        """Bio._fetch_python_import (the direct specifier->import path) must
        refuse and must never call importlib.import_module for a module
        that isn't in the allowlist."""
        import importlib

        called_with = []
        real_import_module = importlib.import_module

        def spy_import_module(name, *a, **kw):
            called_with.append(name)
            return real_import_module(name, *a, **kw)

        monkeypatch.setattr(importlib, "import_module", spy_import_module)

        bio = Bio()

        with pytest.raises(UnsafeSpecError, match="not in the import allowlist"):
            bio.fetch("notallowed_evilmod.SOMEGLOBAL")

        assert called_with == [], (
            "import_module must not be reached for a non-allowlisted module"
        )

    def test_exploit_module_side_effect_never_executes(self, tmp_path):
        """Point at a real module that, if imported, would have an
        observable side effect (writes a marker file at import time).
        Prove the fetch raises and the side effect never happens."""
        evil_dir = tmp_path / "evil_pkg_dir"
        evil_dir.mkdir()
        marker = tmp_path / "pwned.marker"

        evil_module = evil_dir / "notallowed_evilmod.py"
        evil_module.write_text(f"""
open(r"{marker}", "w").close()
SOMEGLOBAL = "pwned"
""")

        sys.path.insert(0, str(evil_dir))
        try:
            bio = Bio()

            with pytest.raises(UnsafeSpecError):
                bio.fetch("notallowed_evilmod.SOMEGLOBAL")

            assert not marker.exists(), "attacker module must never have executed"
            assert "notallowed_evilmod" not in sys.modules
        finally:
            sys.path.remove(str(evil_dir))
            sys.modules.pop("notallowed_evilmod", None)

    def test_source_root_python_global_site_rejects_unregistered_module(self):
        """resolve.load_from_python_global (the source-root python-global
        import site) must refuse a module that isn't covered by any
        registered source root's module prefix."""
        root = SourceRoot(path=".", module="trusted_pkg")

        with pytest.raises(UnsafeSpecError, match="not in the import allowlist"):
            load_from_python_global("evilmod", "SOMEGLOBAL", [root])

    def test_source_root_python_global_site_does_not_import(self, monkeypatch):
        """Confirm importlib.import_module is never reached for a
        disallowed module_path at the resolve.py import site."""
        import importlib

        calls = []
        monkeypatch.setattr(
            importlib, "import_module", lambda name, *a, **kw: calls.append(name)
        )

        root = SourceRoot(path=".", module="trusted_pkg")
        with pytest.raises(UnsafeSpecError):
            load_from_python_global("evilmod", "SOMEGLOBAL", [root])

        assert calls == []


# =============================================================================
# Allowed imports still work exactly as before
# =============================================================================

class TestAllowedImportsStillWork:
    def test_alienbio_framework_import_still_works(self):
        """bio.fetch('alienbio.bio.Chemistry')-style framework imports must
        be unaffected by the allowlist."""
        from alienbio.bio import Chemistry

        bio = Bio()
        result = bio.fetch("alienbio.bio.Chemistry")
        assert result is Chemistry

    def test_registered_source_root_module_prefix_still_works(self, tmp_path):
        """A fetch under a registered add_source_root(..., module=...)
        prefix must still resolve a Python module global exactly as
        before."""
        pkg_root = tmp_path / "pkgroot"
        catalog = pkg_root / "mycatalog"
        catalog.mkdir(parents=True)
        (catalog / "__init__.py").write_text("")
        (catalog / "templates.py").write_text(
            'ENERGY = {"molecule": {"name": "Energy from Python", "count": 50}}\n'
        )

        sys.path.insert(0, str(pkg_root))
        try:
            bio = Bio()
            bio.add_source_root(catalog, module="mycatalog")

            result = bio.fetch("templates.ENERGY", raw=True)
            assert result["molecule"]["name"] == "Energy from Python"
        finally:
            sys.path.remove(str(pkg_root))
            sys.modules.pop("mycatalog.templates", None)
            sys.modules.pop("mycatalog", None)
