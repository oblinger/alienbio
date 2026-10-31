"""T091 AP (trust, robustness) — what a helper function returns is judged
(AP1), framework code is denied by module and allow-listed for ``!py``
(AP2), every YAML failure is an ``ExprError`` naming the file (AP9), and the
whole-document ``!experiment`` form gets the nested-experiment check (AP10).
Attack fixtures write marker files only, and each test asserts the marker is
absent. The DoS half is ``test_t091_ap.py``.
"""

from __future__ import annotations

import functools

import pytest

from alienbio.expr import Env, ExprError
from alienbio.expr import access
from alienbio.expr.include import UnsafeSpecError, resolve_py
from alienbio.suite.expr_experiment import load_experiment
from alienbio.suite.spec import load_spec


def _helper(tmp_path, marker) -> None:
    (tmp_path / "helper.py").write_text(
        "import functools, os, subprocess\n"
        "from alienbio.suite.spec import load_spec as ls\n"
        "from alienbio.suite.dist import Normal\n"
        "def get_mod():\n    return subprocess\n"
        "def get_run():\n    return subprocess.run\n"
        "def get_ls():\n    return ls\n"
        "def get_partial():\n    return functools.partial(ls, 'nowhere.yaml')\n"
        "def get_nested():\n    return {'f': [subprocess.run]}\n"
        "def get_normal():\n    return Normal\n"
        "class K:\n    def m(self):\n        return os\n"
        "def mk():\n    return K()\n"
        "def value():\n    return {'a': [1, 2.5, 'x']}\n"
        f"def touch():\n    open({str(marker)!r}, 'w').write('RAN')\n"
    )


def _load(tmp_path, body: str):
    spec = tmp_path / "t.yaml"
    spec.write_text("h: !include helper.py\n" + body)
    return Env.standard(seed=0, trusted=True).load(spec)


# ---- AP1: a helper's return value is judged ---------------------------------


@pytest.mark.parametrize("call,match", [
    ("h.get_mod()", "is a module"),
    ("h.get_run()", "outside the spec's helpers"),
    ("h.get_ls()", "entry point"),
    ("h.get_partial()", "entry point"),
    ("h.get_nested()", "outside the spec's helpers"),
])
def test_ap1_a_helper_cannot_return_what_a_reference_could_not_reach(tmp_path, call, match):
    marker = tmp_path / "marker.txt"
    _helper(tmp_path, marker)
    doc = _load(tmp_path, f"r: !x {call}\nx: !x \"r(['sh', '-c', 'echo RAN > {marker}'])\"\n")
    with pytest.raises(ExprError, match=match):
        doc.lookup("x")
    assert not marker.exists()


def test_ap1_plain_values_allowed_code_and_helper_objects_return(tmp_path):
    _helper(tmp_path, tmp_path / "marker.txt")
    doc = _load(tmp_path, "v: !x h.value()\nn: !x h.get_normal()\nk: !x h.mk()\n")
    assert doc.lookup("v") == {"a": [1, 2.5, "x"]}
    assert doc.lookup("n").__name__ == "Normal"
    with pytest.raises(ExprError, match="not callable from a spec|not allowed"):
        _load(tmp_path, "k: !x h.mk()\nm: !x k.m()\n").lookup("m")


def test_ap1_partials_and_bound_methods_unwrap_to_their_function():
    from alienbio.suite.spec import load_spec as ls

    assert access.denied_entry_point(functools.partial(functools.partial(ls, "x"))) == "alienbio.suite.spec:*"

    class Holder:
        def method(self):
            return 1

    bound = Holder().method
    assert access.denied_entry_point(bound) is None
    assert access.denied_entry_point(ls.__get__(object())) == "alienbio.suite.spec:*"


# ---- AP2: framework code is denied by module, allow-listed for !py ----------


@pytest.mark.parametrize("path", [
    "alienbio.report.example_rows",
    "alienbio.suite.spec.resolve_source_path",
    "alienbio.suite.llm_agent.write_models_snapshot",
    "alienbio.suite.llm_agent.fetch_models_snapshot",
    "alienbio.suite.experiment.spec_from_manifest",
    "alienbio.suite.experiment.aggregate",
    "alienbio.suite.store.read_manifest",
    "alienbio.config.get_api_key",
    "alienbio.cli.main",
])
def test_ap2_a_denied_module_refuses_every_name(path):
    with pytest.raises(UnsafeSpecError, match="entry point"):
        resolve_py(path, trusted=True)


@pytest.mark.parametrize("path", ["alienbio.expr.heads.render_bound", "alienbio.suite.carve.carve", "alienbio.bio.world.WorldImpl"])
def test_ap2_framework_code_outside_the_allow_list_refuses(path):
    with pytest.raises(UnsafeSpecError, match="framework code"):
        resolve_py(path, trusted=True)


def test_ap2_allowed_framework_code_resolves():
    from alienbio.expr.heads import constant
    from alienbio.suite.dist import Normal

    assert resolve_py("alienbio.expr.heads.constant", trusted=True) is constant  # a registered head
    assert resolve_py("alienbio.suite.dist.Normal", trusted=True) is Normal


def test_ap2_the_gadget_write_refuses_with_no_file(tmp_path):
    target = tmp_path / "gadget_write.json"
    spec = tmp_path / "g.yaml"
    spec.write_text(
        "rsp: !py alienbio.suite.spec.resolve_source_path\n"
        f"p: !x \"rsp('{target}')\"\n"
        "w: !py alienbio.suite.llm_agent.write_models_snapshot\n"
        "wx: !x \"w({'pwned': 'yes'}, p)\"\n"
    )
    with pytest.raises(UnsafeSpecError):
        Env.standard(seed=0, trusted=True).load(spec).force_all()
    assert not target.exists()


# ---- AP9: YAML failures are ExprErrors naming the file ----------------------


def test_ap9_deep_nesting_is_an_expr_error_naming_the_file(tmp_path):
    spec = tmp_path / "deep.yaml"
    spec.write_text("x: " + "[" * 3000 + "]" * 3000 + "\n")
    with pytest.raises(ExprError, match="deep.yaml.*nesting deeper"):
        load_spec(spec)


def test_ap9_an_included_file_failure_names_the_included_file(tmp_path):
    (tmp_path / "bad.yaml").write_text("a: [1, 2\nb: :\n")
    (tmp_path / "deep.yaml").write_text("x: " + "{a: " * 3000 + "1" + "}" * 3000 + "\n")
    (tmp_path / "top_bad.yaml").write_text("x: !include bad.yaml\n")
    (tmp_path / "top_deep.yaml").write_text("x: !include deep.yaml\n")
    with pytest.raises(ExprError, match="bad.yaml.*YAML error"):
        load_spec(tmp_path / "top_bad.yaml")
    with pytest.raises(ExprError, match="deep.yaml.*nesting deeper"):
        load_spec(tmp_path / "top_deep.yaml")


def test_ap9_dry_run_prints_the_message_not_a_traceback(tmp_path):
    import subprocess
    import sys

    spec = tmp_path / "deep.yaml"
    spec.write_text("x: " + "[" * 3000 + "]" * 3000 + "\n")
    out = subprocess.run(
        [sys.executable, "-m", "alienbio.cli", "suite", "run", str(spec), "--dry"],
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode != 0
    assert "Traceback" not in out.stderr + out.stdout
    assert "nesting deeper" in out.stderr + out.stdout


# ---- AP10: the whole-document form refuses a nested !experiment -------------


_OUTER = (
    "!experiment\n"
    "name: outer\n"
    "task: !q identify_pathway(pathway_length=pathway_length)\n"
    "agent: measure_commit\n"
    "trials_per_condition: 2\n"
    "base_seed: 7\n"
)
_INNER = "!experiment {name: inner, task: !q identify_pathway(pathway_length=3), agent: measure_commit, trials_per_condition: 1, base_seed: 1}"


@pytest.mark.parametrize("tail,where", [
    (f"axes: {{pathway_length: [3, 4]}}\ndrafter_kwargs: {{extra: {_INNER}}}\n", "experiment.drafter_kwargs.extra"),
    (f"axes: {{pathway_length: [3, {_INNER}]}}\n", "experiment.axes.pathway_length.1"),
])
def test_ap10_a_nested_experiment_in_the_document_form_names_its_placement(tmp_path, tail, where):
    spec = tmp_path / "wn.yaml"
    spec.write_text(_OUTER + tail)
    with pytest.raises(ExprError, match=f"found an !experiment at '{where}'"):
        load_experiment(spec)


def test_ap10_the_plain_document_form_still_loads(tmp_path):
    spec = tmp_path / "ok.yaml"
    spec.write_text(_OUTER + "axes: {pathway_length: [3, 4]}\n")
    assert load_experiment(spec).name == "outer"
