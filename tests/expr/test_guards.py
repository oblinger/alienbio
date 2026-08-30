"""M47.5 — guards on any call: ``guards:`` + ``on_fail: retry | prune | reject``."""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError, GuardViolation, X, evaluate, fn, guard, registry
from alienbio.expr.env import Limits
from alienbio.expr.yaml_tags import load_text


@guard(summary="test: every reaction has at least one product")
def has_products(value, ctx):
    del ctx
    bad = [k for k, r in value.get("reactions", {}).items() if not r.get("products")]
    if bad:
        raise GuardViolation(f"reactions without products: {bad}", offenders=[f"reactions.{k}" for k in bad])
    return True


@guard(summary="test: the drawn number is above a floor")
def above(value, ctx, floor: float = 0.5):
    del ctx
    return value > floor


@fn(summary="test: a world with one bad reaction")
def lopsided():
    return {"molecules": {"A": {}, "B": {}}, "reactions": {"ok": {"reactants": ["A"], "products": ["B"]}, "dud": {"reactants": ["B"], "products": []}}}


def test_reject_is_the_default_and_names_the_guard():
    env = Env.standard(seed=1)
    with pytest.raises(ExprError, match="rejected by guard has_products.*dud"):
        evaluate(X.lopsided(guards=["has_products"]), env)
    with pytest.raises(ExprError, match="rejected by guard has_products"):
        evaluate(X.lopsided(guards=["has_products"], on_fail="reject"), env)


def test_prune_drops_the_offenders_a_guard_names():
    env = Env.standard(seed=1)
    world = evaluate(X.lopsided(guards=["has_products"], on_fail="prune"), env)
    assert set(world["reactions"]) == {"ok"}
    # a guard that returns False names nothing, so it cannot prune; a scalar cannot be pruned at all
    with pytest.raises(ExprError, match="names nothing to prune"):
        evaluate(X.lopsided(guards=[X.max_size(n=1)], on_fail="prune"), env)
    with pytest.raises(ExprError, match="needs a produced mapping"):
        evaluate(X.uniform(0.0, 0.1, guards=[X.above(floor=0.5)], on_fail="prune"), env)


def test_retry_redraws_under_the_next_child_seed_until_the_guard_passes():
    env = Env.standard(seed=3, limits=Limits(attempts=50))
    value = evaluate(X.uniform(0.0, 1.0, guards=[X.above(floor=0.9)], on_fail="retry"), env)
    assert value > 0.9
    # deterministic: the same seed retries the same way
    again = evaluate(X.uniform(0.0, 1.0, guards=[X.above(floor=0.9)], on_fail="retry"), Env.standard(seed=3, limits=Limits(attempts=50)))
    assert again == value
    with pytest.raises(ExprError, match="still failing after 2 attempts"):
        evaluate(X.uniform(0.0, 0.1, guards=[X.above(floor=0.5)], on_fail="retry"), Env.standard(seed=3, limits=Limits(attempts=2)))


def test_guards_in_yaml_by_name_and_as_calls():
    doc = load_text(
        "k: !uniform {args: [0.0, 1.0], guards: [!x above(floor=0.8)], on_fail: retry}\n"
        "w: !lopsided {guards: [has_products], on_fail: prune}\n"
    )
    env = Env.standard(seed=7, limits=Limits(attempts=100))
    values = env.scope({}).load("<guards>", text="k: !uniform {args: [0.0, 1.0], guards: [!x above(floor=0.8)], on_fail: retry}\nw: !lopsided {guards: [has_products], on_fail: prune}\n").force_all()
    assert values["k"] > 0.8 and set(values["w"]["reactions"]) == {"ok"}
    assert doc["k"].kwargs["on_fail"] == "retry"


def test_bad_guard_references_are_load_errors():
    env = Env.standard(seed=1)
    with pytest.raises(ExprError, match="not a guard"):
        evaluate(X.lopsided(guards=["uniform"]), env)
    with pytest.raises(ExprError, match="unknown head 'no_such_guard'"):
        evaluate(X.lopsided(guards=["no_such_guard"]), env)
    with pytest.raises(ExprError, match="on_fail must be one of"):
        evaluate(X.lopsided(guards=["has_products"], on_fail="ignore"), env)


def test_builtin_guards_nonempty_and_max_size():
    env = Env.standard(seed=1)
    assert registry.get("nonempty").kind == "guard" and registry.get("max_size").kind == "guard"
    assert evaluate(X.lopsided(guards=["nonempty", X.max_size(n=3)]), env)["molecules"] == {"A": {}, "B": {}}
    with pytest.raises(ExprError, match="rejected by guard max_size"):
        evaluate(X.lopsided(guards=[X.max_size(n=1)]), env)
