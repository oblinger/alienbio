"""M47.5 — ``!include`` (yaml / md / py), ``_includes_:``, ``!py``, and trust."""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError, UnsafeSpecError, X, evaluate, registry
from alienbio.expr.form import Include, PyRef
from alienbio.expr.yaml_tags import load_text

HELPERS = '''
from alienbio.expr import fn

@fn(summary="test include: doubles")
def twice_from_include(x):
    return 2 * x

SITE_K = 0.25
'''


def _tree(tmp_path):
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "defaults.yaml").write_text("k: 0.5\nlabel: !x f'k={k}'\n")
    (tmp_path / "shared" / "plain.yaml").write_text("k: 0.5\ntwo: !x 1 + 1\n")
    (tmp_path / "shared" / "deep.yaml").write_text("inner: !include plain.yaml\n")
    (tmp_path / "notes.md").write_text("# notes\n")
    (tmp_path / "helpers.py").write_text(HELPERS)
    (tmp_path / "loop_a.yaml").write_text("b: !include loop_b.yaml\n")
    (tmp_path / "loop_b.yaml").write_text("a: !include loop_a.yaml\n")
    return tmp_path


def test_tags_load_as_include_and_pyref_forms():
    doc = load_text("d: !include shared/defaults.yaml\nf: !py math.sqrt\n")
    assert doc == {"d": Include("shared/defaults.yaml"), "f": PyRef("math.sqrt")}
    with pytest.raises(ExprError, match="was not resolved at load"):
        evaluate(doc["d"], Env.standard())


def test_yaml_include_splices_forms_relative_to_the_included_file(tmp_path):
    root = _tree(tmp_path)
    (root / "spec.yaml").write_text("plain: !include shared/plain.yaml\nnested: !include shared/deep.yaml\nnotes: !include notes.md\n")
    values = Env.standard(seed=1).load(root / "spec.yaml").force_all()
    assert values["plain"] == {"k": 0.5, "two": 2}  # the !x inside the include evaluated, in the including file's scope
    assert values["nested"] == {"inner": {"k": 0.5, "two": 2}}  # deep.yaml's own include, relative to shared/
    assert values["notes"] == "# notes\n"
    # a spliced include's names are data, not bindings: defaults.yaml's label reads `k` from the FILE scope
    (root / "spec2.yaml").write_text("k: 0.9\ndefaults: !include shared/defaults.yaml\n")
    assert Env.standard(seed=1).load(root / "spec2.yaml").force_all()["defaults"] == {"k": 0.5, "label": "k=0.9"}


def test_includes_list_executes_py_and_merges_yaml_with_the_file_winning(tmp_path):
    root = _tree(tmp_path)
    (root / "spec.yaml").write_text("_includes_: [helpers.py, shared/defaults.yaml]\nk: 0.9\nd: !x twice_from_include(k)\n")
    env = Env.standard(seed=1, trusted=True).load(root / "spec.yaml")
    values = env.force_all()
    assert "twice_from_include" in registry
    assert values["k"] == 0.9 and values["d"] == 1.8  # the file's own k wins over the include's
    assert values["label"] == "k=0.9"  # the merged binding evaluates in the file's scope
    assert "_includes_" not in values


def test_py_include_yields_its_namespace_and_pyref_yields_the_object(tmp_path):
    root = _tree(tmp_path)
    (root / "spec.yaml").write_text("h: !include helpers.py\nsq: !py math.sqrt\nroot2: !x sq(4)\nk: !x h.SITE_K\n")
    values = Env.standard(seed=1, trusted=True).load(root / "spec.yaml").force_all()
    assert values["k"] == 0.25 and values["root2"] == 2.0 and callable(values["sq"])


def test_untrusted_loads_refuse_python_and_escaping_paths(tmp_path):
    root = _tree(tmp_path)
    (root / "py.yaml").write_text("h: !include helpers.py\n")
    (root / "ref.yaml").write_text("f: !py math.sqrt\n")
    (root / "shared" / "up.yaml").write_text("x: !include ../notes.md\n")
    (root / "abs.yaml").write_text(f"x: !include {root / 'notes.md'}\n")
    (root / "lst.yaml").write_text("_includes_: [helpers.py]\n")
    for name, message in (
        ("py.yaml", "requires a trusted load"),
        ("ref.yaml", "requires a trusted load"),
        ("shared/up.yaml", "escapes|parent-directory"),
        ("abs.yaml", "absolute"),
        ("lst.yaml", "requires a trusted load"),
    ):
        with pytest.raises(UnsafeSpecError, match=message):
            Env.standard(seed=1).load(root / name)
    # trusted: the same escaping include is fine
    assert Env.standard(seed=1, trusted=True).load(root / "shared" / "up.yaml").force_all()["x"] == "# notes\n"


def test_include_cycles_and_missing_files_are_named(tmp_path):
    root = _tree(tmp_path)
    with pytest.raises(ExprError, match="cycle"):
        Env.standard(seed=1).load(root / "loop_a.yaml").force_all()
    (root / "gone.yaml").write_text("x: !include nowhere.yaml\n")
    with pytest.raises(ExprError, match="no such file 'nowhere.yaml'"):
        Env.standard(seed=1).load(root / "gone.yaml")
    (root / "kind.yaml").write_text("x: !include helpers.json\n")
    (root / "helpers.json").write_text("{}")
    with pytest.raises(ExprError, match="unknown file kind"):
        Env.standard(seed=1).load(root / "kind.yaml")


def test_hydrate_reaches_into_calls_and_quoted_forms(tmp_path):
    root = _tree(tmp_path)
    forms = load_text("w: !world {initial: !include shared/defaults.yaml}\nq: !q [!include notes.md]\n")
    env = Env.standard(seed=1)
    hydrated = env.hydrate(forms, base=root)
    assert hydrated["w"].kwargs["initial"] == {"k": 0.5, "label": X.parse("f'k={k}'")}
    assert hydrated["q"].form == ["# notes\n"]
