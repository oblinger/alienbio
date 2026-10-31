"""T091 AG1 — the Expr sandbox confines attribute and method access by the
RECEIVER'S TYPE (``alienbio.expr.access``), not only by attribute name.

The attack this pins: ``q: !q 1`` is a ``QuotedForm`` whose public ``.env``
was the ``Env``; ``q.env.standard(trusted=True).load(..., text='g: !py
os.system')`` minted a trusted environment from an untrusted spec and ran a
shell command before ``load_spec`` refused the file.
"""

from __future__ import annotations

import math
import types

import pytest

from alienbio.expr import Env, ExprError, X, evaluate, registry
from alienbio.expr.access import DOMAIN_CLASS_NAMES, PLAIN_TYPES, domain_types
from alienbio.expr.interp import QuotedForm, closure_env
from alienbio.suite.dist import Seed


def _x(text: str, *, trusted: bool = False, **bindings):
    env = Env.standard(seed=1, trusted=trusted, bindings=bindings)
    return evaluate(X.parse(text), env)


def _doc(text: str, *, trusted: bool = False):
    return Env.standard(seed=1, trusted=trusted).load("<t>", text=text).force_all()


def test_ag_attack_through_load_spec_refuses_with_no_side_effect(tmp_path):
    """AG's exact three-binding spec, loaded by the CLI's entry point from a
    path outside ``catalog/`` (so untrusted): refused, and the marker file the
    escaped shell command would write does not exist."""
    from alienbio.suite.spec import load_spec

    marker = tmp_path / "pwned.txt"
    spec = tmp_path / "rce.yaml"
    spec.write_text(
        "q: !q 1\n"
        "sys: !x \"q.env.standard(trusted=True).load('x', text='g: !py os.system').lookup('g')\"\n"
        f"pwn: !x \"sys('echo RCE > {marker}')\"\n"
    )
    with pytest.raises(ExprError, match="QuotedForm is not allowed"):
        load_spec(spec)
    assert not marker.exists()


@pytest.mark.parametrize("text", [
    "q.env", "q._env", "q.form", "q.sample", "q.run()", "q.env.standard(trusted=True)",
])
def test_a_quoted_form_exposes_nothing(text):
    with pytest.raises(ExprError, match="QuotedForm|private"):
        _doc(f"q: !q 1\nv: !x {text!r}\n")


def test_quoted_form_env_is_private_and_read_through_closure_env():
    env = Env.standard(seed=1)
    q = evaluate(X.quote(X.constant(3)), env)
    assert isinstance(q, QuotedForm) and not hasattr(q, "env")
    assert closure_env(q) is env and q.sample(Seed(1)) == 3


def _denied_values():
    env = Env.standard(seed=1)
    return {
        "Env": env,
        "Ctx": env.ctx,
        "Registry": registry,
        "Head": registry.get("max"),
        "Seed": Seed(1),
        "module": math,
        "class": Env,
        "function": _x,
        "bound method": "a".upper,
        "builtin": len,
    }


@pytest.mark.parametrize("kind", list(_denied_values()))
def test_every_denied_type_refuses_attribute_and_method_access(kind):
    value = _denied_values()[kind]
    for text in ("v.x", "v.get(1)"):
        with pytest.raises(ExprError, match="not allowed in a spec expression"):
            _x(text, v=value)
    # a dotted name walks the same check (Env._step)
    with pytest.raises(ExprError, match="not allowed in a spec expression"):
        _doc_with("w: !ref v.x\n", v=value)


def _doc_with(text: str, **bindings):
    return Env.standard(seed=1, bindings=bindings).load("<t>", text=text).force_all()


def test_denied_under_trust_too():
    env = Env.standard(seed=1, trusted=True)
    with pytest.raises(ExprError, match="Env is not allowed"):
        _x("e.standard", trusted=True, e=env)
    with pytest.raises(ExprError, match="QuotedForm is not allowed"):
        _doc("q: !q 1\nv: !x q.run()\n", trusted=True)


def test_the_seed_head_returns_an_opaque_seed():
    with pytest.raises(ExprError, match="Seed is not allowed"):
        _x("seed('a').rng()")


def test_plain_data_keeps_its_attributes_and_methods():
    assert _x("'ab'.upper()") == "AB"
    assert _x("d.get('k', 0)", d={"k": 2}) == 2
    assert _x("xs.index(3)", xs=[1, 3]) == 1
    assert _x("(3).real") == 3
    with pytest.raises(ExprError, match="is a method; call it"):
        _x("'ab'.upper")  # a method is called, never read as a value
    with pytest.raises(ExprError, match="private"):
        _x("d._x", d=[1])


def test_a_domain_value_offers_data_attributes_not_methods():
    env = Env.standard(seed=5)
    draft = evaluate(X.identify_pathway(pathway_length=3), env)
    world = _x("d.world", d=draft)
    assert world is draft.world
    assert _x("d.world.chemistry", d=draft) is draft.world.chemistry  # a property
    with pytest.raises(ExprError, match="methods are not callable"):
        _x("w.chemistry.save()", w=world)  # Entity.save writes to disk
    with pytest.raises(ExprError, match="is a method"):
        _x("w.chemistry.save", w=world)
    with pytest.raises(ExprError, match="methods are not callable|not allowed"):
        _x("w.chemistry.dat.save", w=world)  # never reaches the Dat


def test_untrusted_calls_only_plain_functions():
    def f(x):
        return x + 1

    assert _x("f(1)", f=f) == 2
    for value in ("a".upper, len, Env, Env.standard, types.SimpleNamespace):
        with pytest.raises(ExprError, match="not allowed in an untrusted spec"):
            _x("g(1)", g=value)
        with pytest.raises(ExprError, match="not allowed in an untrusted spec"):
            _x("m.g(1)", m={"g": value})
    assert _x("g(4)", trusted=True, g=math.sqrt) == 2.0  # a trusted author's binding


def test_the_allowlist_resolves_and_covers_plain_data():
    classes = domain_types()
    assert len(classes) == len(DOMAIN_CLASS_NAMES)
    names = {c.__name__ for c in classes}
    for denied in ("Env", "Ctx", "Registry", "Head", "QuotedForm", "Seed", "Scope"):
        assert denied not in names
    assert {str, int, float, bool, type(None), list, tuple, dict, set, frozenset} <= PLAIN_TYPES


def test_two_literal_experiments_refuse_before_any_helper_runs(tmp_path):
    """The structural check runs on the unevaluated tree, before ``env.load``
    executes an ``_includes_`` helper (trusted load)."""
    from alienbio.suite.expr_experiment import load_experiment

    marker = tmp_path / "ran.txt"
    (tmp_path / "helper.py").write_text(f"open({str(marker)!r}, 'w').write('ran')\n")
    spec = tmp_path / "two.yaml"
    spec.write_text("_includes_: [helper.py]\na: !experiment {name: a}\nb: !experiment {name: b}\n")
    with pytest.raises(ExprError, match="exactly one !experiment.*found 2"):
        load_experiment(spec, trusted=True)
    assert not marker.exists()
