"""T091 AR — verifier AR's attack on round AQ: the node cap blind to
mapping subclasses (AR1), merge-key expansion inside the constructor (AR2),
framework functions reached through plain containers (AR3), helper-class
instances wrapping imported code (AR4), base-60 int literals (AR5), long int
keys compared by text (AR6), non-regular spec files (AR7) and the dead
``bio.makers`` allowlist entry (AR8)."""

from __future__ import annotations

import os
import time

import pytest
import yaml

from alienbio.expr import Env, ExprError, heads, yaml_tags
from alienbio.expr.access import PY_ALLOWED_MODULES
from alienbio.expr.form import Call
from alienbio.suite.expr_experiment import load_experiment
from alienbio.suite.yaml_keys import refuse_duplicate_keys


def _bomb(n: int, call: bool) -> str:
    defs = ["a0: &a0 [1,1,1,1,1,1,1,1,1,1]"] + [f"a{i}: &a{i} [{', '.join([f'*a{i - 1}'] * 10)}]" for i in range(1, n + 1)]
    if not call:
        return "\n".join(defs) + "\n"
    return "!experiment\nname: bomb\nnotes:\n" + "\n".join("  " + d for d in defs) + "\n"


def _load_file(tmp_path, name: str, text: str, *, trusted: bool = True):
    path = tmp_path / name
    path.write_text(text)
    return Env.standard(seed=0, trusted=trusted).load(str(path)).force_all()


# ---- AR1: the node cap sees through every mapping / sequence subclass ----


def test_ar1_element_bound_counts_inside_a_calls_kwargs():
    call = Call("block", (), {"x": [[1] * 10] * 10})
    assert heads.element_bound(call, 10_000) > 100


def test_ar1_an_alias_bomb_inside_an_experiment_call_refuses_fast(tmp_path):
    path = tmp_path / "bomb.yaml"
    path.write_text(_bomb(9, call=True))
    assert len(path.read_bytes()) < 700
    t = time.monotonic()
    with pytest.raises(ExprError, match="MAX_DOCUMENT_NODES"):
        load_experiment(path, trusted=False)
    assert time.monotonic() - t < 5


def test_ar1_a_bomb_under_a_tagged_mapping_refuses_at_load():
    text = "x: !block\n" + "".join("  " + line + "\n" for line in _bomb(7, call=False).splitlines())
    with pytest.raises(ExprError, match="MAX_DOCUMENT_NODES"):
        yaml_tags.load_text(text)


# ---- AR2: merge keys are bounded on the node tree ----


def _merge(n: int) -> str:
    lines = ["L0: &L0 {a: 1, b: 2}"]
    lines += [f"L{i}: &L{i} {{<<: [*L{i - 1}, *L{i - 1}], k{i}: {i}}}" for i in range(1, n + 1)]
    return "\n".join(lines) + "\nx: 1\n"


def test_ar2_a_doubling_merge_chain_refuses_before_construction():
    t = time.monotonic()
    with pytest.raises(ExprError, match="merge keys"):
        yaml_tags.load_text(_merge(26))
    assert time.monotonic() - t < 5


def test_ar2_ordinary_merge_keys_still_load():
    data = yaml_tags.load_text("base: &b {a: 1, b: 2}\nmore: {<<: *b, b: 3}\nboth: {<<: [*b, {c: 4}]}\n")
    assert data["more"] == {"a": 1, "b": 3}
    assert data["both"] == {"a": 1, "b": 2, "c": 4}


# ---- AR3: a framework function reached through plain data refuses at the call ----


def test_ar3_a_plotter_read_out_of_plotters_refuses_when_called(tmp_path):
    text = "P: !py alienbio.suite.plots.PLOTTERS\nf: !x P[0][1]\nv: !x f(7)\n"
    with pytest.raises(ExprError, match="AR3"):
        _load_file(tmp_path, "c3.yaml", text)


def test_ar3_a_domain_class_from_a_container_stays_callable(tmp_path):
    from alienbio.expr.access import callable_code_allowed
    from alienbio.spec_lang import biotype_registry

    for cls in biotype_registry.values():
        assert callable_code_allowed(cls)


# ---- AR4: helper-class instances are judged by what they hold and run ----

_GAD = """
import os


class Box(dict):
    pass


class Caller:
    __call__ = staticmethod(os.getcwd)


class Own:
    def __call__(self, x):
        return x + 1


def box():
    return Box(cwd=os.getcwd)


def good_box():
    return Box(n=1)


def caller():
    return Caller()


def own():
    return Own()
"""


@pytest.mark.parametrize(
    "body",
    ["b: !x h.box()\nv: !x b.cwd()\n", "b: !x h.box()\nf: !x b['cwd']\nv: !x f()\n", "c: !x h.caller()\nv: !x c()\n", "c: !x h.Caller()\nv: !x c()\n"],
)
def test_ar4_a_helper_instance_wrapping_an_import_refuses(tmp_path, body):
    (tmp_path / "gad.py").write_text(_GAD)
    with pytest.raises(ExprError, match="outside the spec's helpers"):
        _load_file(tmp_path, "t.yaml", "h: !include gad.py\n" + body)


def test_ar4_a_helper_instance_of_its_own_code_passes(tmp_path):
    (tmp_path / "gad.py").write_text(_GAD)
    out = _load_file(tmp_path, "t.yaml", "h: !include gad.py\nb: !x h.good_box()\nc: !x h.own()\nv: !x c(1)\n")
    assert out["v"] == 2 and out["b"] == {"n": 1}


# ---- AR5: base-60 ints refuse outright ----


def test_ar5_a_sexagesimal_int_refuses_before_conversion():
    t = time.monotonic()
    with pytest.raises(ExprError, match="base-60"):
        yaml_tags.load_text("a: 1" + ":59" * 116_000 + "\n")
    assert time.monotonic() - t < 2


# ---- AR6: long int keys are compared by value ----


def test_ar6_two_spellings_of_one_long_int_key_refuse():
    text = "? 0x" + "f" * 4100 + "\n: a\n? 0x" + "f" * 4099 + "_f\n: b\n"
    with pytest.raises(ValueError, match="duplicate key"):
        refuse_duplicate_keys(text, yaml.SafeLoader)
    with pytest.raises(ExprError, match="duplicate key"):
        yaml_tags.load_text(text)


# ---- AR7: a spec is read from a regular file, with a hard byte limit ----


def test_ar7_a_fifo_spec_refuses(tmp_path):
    fifo = tmp_path / "p.yaml"
    os.mkfifo(fifo)
    with pytest.raises(ExprError, match="not a regular file"):
        yaml_tags.read_spec_text(fifo)


def test_ar7_a_symlink_to_a_device_refuses(tmp_path):
    link = tmp_path / "zero.yaml"
    link.symlink_to("/dev/zero")
    with pytest.raises(ExprError, match="not a regular file"):
        yaml_tags.read_spec_text(link)


def test_ar7_the_read_is_bounded_even_if_the_size_check_passed(tmp_path, monkeypatch):
    path = tmp_path / "big.yaml"
    path.write_text("a: 1\n" * 10)
    monkeypatch.setattr(yaml_tags, "MAX_SPEC_BYTES", 49)
    monkeypatch.setattr(yaml_tags, "check_spec_size", lambda p: None)  # the file "grew" after the check
    with pytest.raises(ExprError, match="grew past"):
        yaml_tags.read_spec_text(path)


# ---- AR8: the dead makers entry is gone ----


def test_ar8_makers_is_not_an_allowed_module():
    assert "alienbio.bio.makers" not in PY_ALLOWED_MODULES
