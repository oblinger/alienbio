"""T091 AG2 — ``!py`` restores the D1 import-root allowlist (Audit Findings
2026-07-10 § D1): only ``alienbio`` / ``alienbio.*`` and the spec's own
included ``.py`` helpers, under trust too, and the walk never leaves them."""

from __future__ import annotations

import sys

import pytest

from alienbio.expr import Env, UnsafeSpecError
from alienbio.expr.include import resolve_py


@pytest.mark.parametrize("path", [
    "subprocess.run", "os.system", "sys.exit", "importlib.import_module", "builtins.open",
    "math.sqrt", "posixpath.basename",
])
def test_a_foreign_root_refuses_by_name_under_trust(path):
    root = path.split(".")[0]
    with pytest.raises(UnsafeSpecError, match=f"module {root!r} is outside the allowed import roots"):
        resolve_py(path, trusted=True)


def test_a_foreign_root_is_never_imported():
    sys.modules.pop("antigravity", None)
    with pytest.raises(UnsafeSpecError):
        resolve_py("antigravity.fly", trusted=True)
    assert "antigravity" not in sys.modules


def test_an_alienbio_reference_resolves():
    from alienbio.expr.heads import constant

    assert resolve_py("alienbio.expr.heads.constant", trusted=True) is constant


@pytest.mark.parametrize("path", ["alienbio.expr.heads.re.compile", "alienbio.expr.heads.math.sqrt"])
def test_the_walk_cannot_leave_the_roots_through_an_imported_module(path):
    with pytest.raises(UnsafeSpecError, match="belongs to 're'|belongs to 'math'"):
        resolve_py(path, trusted=True)


@pytest.mark.parametrize("path", ["alienbio.config.os.system", "alienbio.suite.store.os"])
def test_a_denied_module_refuses_before_its_imports_are_walked(path):
    # T091 AP2: config and the store are denied modules — every name in them.
    with pytest.raises(UnsafeSpecError, match="entry point"):
        resolve_py(path, trusted=True)


def test_private_and_dunder_steps_refuse():
    for path in ("alienbio.expr.env._callable_head", "alienbio.__builtins__"):
        with pytest.raises(UnsafeSpecError, match="private or dunder"):
            resolve_py(path, trusted=True)


def test_an_included_helper_resolves_but_not_what_it_imported(tmp_path):
    (tmp_path / "helpers.py").write_text(
        "import os\nfrom subprocess import run\n\ndef score(x):\n    return x\n\nK = 3\n"
    )
    ok = tmp_path / "ok.yaml"
    ok.write_text("_includes_: [helpers.py]\nf: !py helpers.score\nk: !py helpers.K\nv: !x f(k)\n")
    assert Env.standard(seed=1, trusted=True).load(ok).force_all()["v"] == 3
    for ref in ("helpers.run", "helpers.os.system", "helpers.os"):
        bad = tmp_path / "bad.yaml"
        bad.write_text(f"_includes_: [helpers.py]\nf: !py {ref}\n")
        with pytest.raises(UnsafeSpecError, match="outside the allowed import roots"):
            Env.standard(seed=1, trusted=True).load(bad)
