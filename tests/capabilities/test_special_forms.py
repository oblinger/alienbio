"""M48.3 — edge cases of the seven special forms and every ``ctx.limits`` cap."""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError, X, evaluate, guard
from alienbio.expr.env import Limits


def _doc(text: str, seed: int = 1, **limits):
    return Env.standard(seed=seed, limits=Limits(**limits) if limits else None).load("<sf>", text=text).force_all()


def test_each_over_nothing_and_over_a_mapping():
    v = _doc("empty: !each {over: [], as: i, body: !x i}\nkeyed: !each {over: [], as: i, key: !x i, body: 1}\npairs: !each\n  over: {a: 1, b: 2}\n  as: kv\n  body: !x kv[1] * 10\n")
    assert v["empty"] == [] and v["keyed"] == {} and v["pairs"] == [10, 20]


def test_each_duplicate_key_and_non_iterable_are_errors():
    with pytest.raises(ExprError, match="duplicate key"):
        _doc("d: !each {over: [1, 1], as: i, key: !x i, body: !x i}\n")
    with pytest.raises(ExprError, match="not iterable"):
        _doc("d: !each {over: 3, as: i, body: !x i}\n")


def test_let_shadows_the_file_scope_and_later_bindings_see_earlier_ones():
    v = _doc("n: 1\nw: !let\n  bindings: {n: 5, m: !x n * 2}\n  body: !x m + n\nouter: !x n\n")
    assert v["w"] == 15 and v["outer"] == 1


def test_if_without_else_is_null_and_only_the_taken_branch_evaluates():
    v = _doc("a: !if {cond: False, then: !x unbound_name}\nb: !if {cond: True, then: 1, else: !x unbound_name}\n")
    assert v["a"] is None and v["b"] == 1


def test_quote_run_round_trip_and_bindings():
    v = _doc("q: !q n * 2\nr: !x \"run(q, {'n': 21})\"\n")
    assert v["r"] == 42
    env = Env.standard(seed=1)
    form = X.quote(X.parse("lognormal(0, 1)"))
    d = evaluate(form, env)
    assert d.sample(env.ctx.seed.child("a")) == d.sample(env.ctx.seed.child("a"))
    assert d.sample(env.ctx.seed.child("a")) != d.sample(env.ctx.seed.child("b"))


def test_inserting_a_node_never_re_rolls_a_sibling():
    before = _doc("a: !x lognormal(0, 1)\nc: !x lognormal(0, 1)\n")
    after = _doc("a: !x lognormal(0, 1)\nb: !x lognormal(0, 1)\nc: !x lognormal(0, 1)\n")
    assert before["a"] == after["a"] and before["c"] == after["c"] and after["b"] not in (after["a"], after["c"])


def test_template_arity_unknown_parameter_and_missing_positional_are_errors():
    doc = "t: !template {positional: [a], params: {b: 1}, body: !x a + b}\n"
    assert _doc(doc + "v: !t [1]\n")["v"] == 2
    with pytest.raises(ExprError, match="takes 1 positional"):
        _doc(doc + "v: !t [1, 2]\n")
    with pytest.raises(ExprError, match="no parameter 'z'"):
        _doc(doc + "v: !t {args: [1], z: 3}\n")
    with pytest.raises(ExprError, match="missing positional argument 'a'"):
        _doc(doc + "v: !t {b: 2}\n")


def test_seed_streams_are_independent_and_named():
    v = _doc("k1: !x seed('a')\nk2: !x seed('b')\n")
    assert v["k1"] != v["k2"] and v["k1"].value != v["k2"].value


@guard(summary="test: never passes")
def never(value, ctx):
    return False


def test_every_limit_cap_fires_with_the_node_path():
    with pytest.raises(ExprError, match="exceeds limits.entities"):
        _doc("big: !each {over: !x range(100), as: i, body: !x i}\n", entities=10)
    with pytest.raises(ExprError, match="deeper than limits.depth"):
        _doc("d: !template {positional: [n], body: !x d(n - 1) if n > 0 else 0}\nv: !x d(500)\n", depth=50)
    with pytest.raises(ExprError, match="still failing after 3 attempts"):
        _doc("v: !uniform {args: [0, 1], guards: [never], on_fail: retry}\n", attempts=3)


def test_cyclic_bindings_and_unbound_names_carry_the_path():
    with pytest.raises(ExprError, match="cyclic definition of 'a'"):
        _doc("a: !x b\nb: !x a\n")
    with pytest.raises(ExprError, match=r"^x: unbound name 'nope'"):
        _doc("x: !x nope\n")
