"""T091 AL (trust) — verifier AL's re-attack of the Expr sandbox after round
AH: the symlink that borrowed catalog trust (AL1), an included helper's
imports reachable through its namespace (AL2), alienbio's own loaders and
non-data objects as ``!py`` gadgets (AL3), and leaked framework functions
callable untrusted (AL8). Attack fixtures write marker files only, and each
test asserts the marker is absent. The DoS half is ``test_t091_al.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.expr import Env, ExprError, X, evaluate
from alienbio.expr.env import Limits
from alienbio.expr.include import UnsafeSpecError, resolve_py
from alienbio.suite.spec import REPO_ROOT, load_spec

ECOSYSTEM = REPO_ROOT / "catalog" / "examples" / "ecosystem" / "ecosystem.yaml"


def _doc(text: str, *, trusted: bool = False, limits: Limits | None = None, path: str = "<t>"):
    return Env.standard(seed=1, trusted=trusted, limits=limits).load(path, text=text)


def _x(text: str, *, trusted: bool = False, limits: Limits | None = None, **bindings):
    return evaluate(X.parse(text), Env.standard(seed=1, trusted=trusted, limits=limits, bindings=bindings))


def _marker_helper(directory: Path, marker: Path, name: str = "helpers.py") -> None:
    (directory / name).write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('RAN')\n")


# ---- AL1: one resolution decides trust and the include base -----------------


def test_al1_a_symlink_to_a_catalog_spec_uses_catalog_helpers_not_its_own_folder(tmp_path):
    marker = tmp_path / "sym_marker.txt"
    _marker_helper(tmp_path, marker)
    link = tmp_path / "ecosystem.yaml"
    link.symlink_to(ECOSYSTEM)
    spec = load_spec(link)
    assert not marker.exists()
    assert spec.source["helper_modules"] == ["catalog/examples/ecosystem/helpers.py"]
    assert spec.source["spec_path"] == "catalog/examples/ecosystem/ecosystem.yaml"


def test_al1_env_load_takes_its_base_from_the_resolved_file(tmp_path):
    marker = tmp_path / "env_marker.txt"
    _marker_helper(tmp_path, marker)
    link = tmp_path / "ecosystem.yaml"
    link.symlink_to(ECOSYSTEM)
    Env.standard(seed=0, trusted=True).load(link)
    assert not marker.exists()


def test_al1_a_symlink_resolving_outside_the_catalog_loads_untrusted(tmp_path):
    marker = tmp_path / "out_marker.txt"
    outside = tmp_path / "outside"
    outside.mkdir()
    _marker_helper(outside, marker)
    (outside / "spec.yaml").write_text("_includes_: [helpers.py]\nx: 1\n")
    link = tmp_path / "spec.yaml"
    link.symlink_to(outside / "spec.yaml")
    with pytest.raises(UnsafeSpecError, match="requires a trusted load"):
        load_spec(link)
    assert not marker.exists()


# ---- AL2: an included helper exposes only what it defines -------------------


def test_al2_an_included_helpers_imports_refuse_and_its_definitions_resolve(tmp_path):
    marker = tmp_path / "ns_marker.txt"
    (tmp_path / "helper.py").write_text(
        "from subprocess import run\nimport os\nfrom pathlib import Path\n\n"
        "def double(x):\n    return 2 * x\n\nK = 3\nHERE = Path('.')\n"
    )
    spec = tmp_path / "t.yaml"
    spec.write_text(
        "h: !include helper.py\n"
        f"r: !x \"h.run(['sh', '-c', 'echo RAN > {marker}'])\"\n"
        "s: !x h.os\n"
        "p: !x h.HERE\n"
        "d: !x h.double(h.K)\n"
    )
    env = Env.standard(seed=1, trusted=True).load(spec)
    for key, owner in (("r", "subprocess"), ("s", "os")):
        with pytest.raises(UnsafeSpecError, match=f"belongs to '{owner}', not to the included helper"):
            env.lookup(key)
    with pytest.raises(UnsafeSpecError, match="is not plain data or a domain value"):
        env.lookup("p")
    assert env.lookup("d") == 6
    assert not marker.exists()


# ---- AL3: !py results pass access.py; framework loaders are denied by name ---


@pytest.mark.parametrize("path,match", [
    ("alienbio.expr.include.run_python_file", "entry point"),
    ("alienbio.expr.include.load_include", "entry point"),
    ("alienbio.expr.yaml_tags.load_text", "entry point"),
    ("alienbio.expr.env.Env", "entry point"),
    ("alienbio.expr.env.Env.standard", "entry point"),
    ("alienbio.expr.interp.evaluate", "entry point"),
    ("alienbio.suite.spec.load_spec", "entry point"),
    ("alienbio.suite.expr_experiment.load_experiment", "entry point"),
    ("alienbio.suite.experiment.run_experiment", "entry point"),
    ("alienbio.report.run_pytest", "entry point"),
    ("alienbio.capabilities.REPO_ROOT", "not plain data"),
    ("alienbio.expr.registry.registry", "not plain data"),
    ("alienbio.suite.dist", "is a module"),
])
def test_al3_gadgets_refuse_under_trust(path, match):
    with pytest.raises(UnsafeSpecError, match=match):
        resolve_py(path, trusted=True)


def test_al3_the_gadget_chain_refuses_with_no_side_effect(tmp_path):
    marker = tmp_path / "gadget_marker.txt"
    _marker_helper(tmp_path, marker, "gadget.py")
    with pytest.raises(UnsafeSpecError):
        _doc(
            "rp: !py alienbio.expr.include.run_python_file\nroot: !py alienbio.capabilities.REPO_ROOT\n"
            f"ns: !x \"rp(root / '{tmp_path / 'gadget.py'}')\"\n",
            trusted=True,
        ).force_all()
    assert not marker.exists()


def test_al3_a_denied_entry_point_bound_from_python_is_not_callable_under_trust():
    with pytest.raises(ExprError, match="entry point"):
        _x("g('x.yaml')", trusted=True, g=load_spec)


# ---- AL8: untrusted calls registered heads only ------------------------------


@pytest.mark.parametrize("doc", [
    "c: !x diagnose().task.skeleton.motif.roles[0].constraints[0]\nr: !x c(1)\n",
    "h:\n  g: !x diagnose().task.skeleton.motif.roles[0].constraints[0]\nr: !x h.g(1)\n",
    "f: !x idle()\nr: !x 'f(1, {})'\n",
])
def test_al8_a_leaked_framework_function_is_not_callable_untrusted(doc):
    with pytest.raises(ExprError, match="not allowed in an untrusted spec"):
        _doc(doc).force_all()


def test_al8_the_llm_factory_is_not_callable_untrusted(monkeypatch):
    import alienbio.suite.llm_agent as llm_agent

    calls: list[object] = []
    monkeypatch.setattr(llm_agent, "default_anthropic_llm_fn", lambda *a, **k: calls.append(a))
    with pytest.raises(ExprError, match="not allowed in an untrusted spec"):
        _doc("f: !x \"llm(model='claude-sonnet-4-5-20250929')\"\nr: !x 'f(1, {})'\n").force_all()
    assert calls == []


