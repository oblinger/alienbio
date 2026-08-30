"""M47.1 — the Expr core: forms, the interpreter, the registry, the three
spellings, the special forms, seeds, errors and limits (ABIO Expr Spec)."""

from __future__ import annotations

import pytest

from alienbio.expr import (
    Call,
    Env,
    ExprError,
    Limits,
    Name,
    Quoted,
    QuotedForm,
    Registry,
    TemplateHead,
    X,
    evaluate,
    expander,
    fn,
    registry,
)
from alienbio.suite.dist import Dist, Seed


def _env(seed: int = 1, **bindings):
    return Env.standard(seed=seed, bindings=bindings)


# ---------------------------------------------------------------------------
# forms + spellings
# ---------------------------------------------------------------------------


def test_the_three_spellings_denote_one_tree():
    py = X.chain("A", "B", length=3, rate=X.quote(X.lognormal(0.1, 0.3)))
    inline = X.parse('chain("A", "B", length=3, rate=quote(lognormal(0.1, 0.3)))')
    # in a YAML flow mapping an inline expression holding a comma must be quoted
    structural = X.load('r: !chain {args: [A, B], length: 3, rate: !q "lognormal(0.1, 0.3)"}')["r"]
    assert py == inline == structural
    assert X.load(X.dump(py, style="structural")) == py
    assert X.parse(X.dump(py)) == py


def test_structural_forms_mapping_sequence_scalar():
    doc = X.load(
        """
a: !source {pool: A, rate: 2.0}
b: !chain [A, B]
c: !upper krel
d: !seed_word 3
e: !nothing
f: !ref K
g: !q {rate: !x k * 2}
"""
    )
    assert doc["a"] == Call("source", (), {"pool": "A", "rate": 2.0})
    assert doc["b"] == Call("chain", ("A", "B"))
    assert doc["c"] == Call("upper", ("krel",))
    assert doc["d"] == Call("seed_word", (3,))  # implicit typing on a tagged scalar
    assert doc["e"] == Call("nothing")
    assert doc["f"] == Name("K")
    assert doc["g"] == Quoted({"rate": Call("op:mul", (Name("k"), 2))})


def test_bad_tags_are_refused():
    with pytest.raises(ExprError, match="takes a string"):
        X.load("a: !x {not: text}")
    with pytest.raises(ExprError, match="identifier"):
        X.load("a: !bad-name {}")
    with pytest.raises(ExprError, match="keyword names"):
        X.load("a: !head {bad key: 1}")


def test_inline_operators_conditionals_fstrings_comprehensions():
    env = _env(n=4, rate=5.0, state={"A": 1.5})
    assert evaluate(X.parse("0.5 * n ** 2"), env) == 8.0
    assert evaluate(X.parse('"fast" if rate > 4 else "slow"'), env) == "fast"
    assert evaluate(X.parse('f"world-{n:02d}-{rate!r}"'), env) == "world-04-5.0"
    assert evaluate(X.parse("[f'M{i}' for i in range(n) if i != 2]"), env) == ["M0", "M1", "M3"]
    assert evaluate(X.parse("{f'k{i}': i * 2 for i in range(2)}"), env) == {"k0": 0, "k1": 2}
    assert evaluate(X.parse("[(i, j) for i in range(2) for j in range(2) if j]"), env) == [[0, 1], [1, 1]]
    assert evaluate(X.parse("state.get('A', 0.0) + state['A']"), env) == 3.0
    assert evaluate(X.parse("1 < n <= 4 and not (n == 3)"), env) is True
    assert evaluate(X.parse("max(rate, 1.0)"), env) == 5.0
    assert evaluate(X.parse("[1, 2, 3][1:]"), env) == [2, 3]


def test_inline_sandbox_refuses_what_the_language_forbids():
    for bad in ("__import__('os')", "().__class__", "lambda x: x", "getattr(a, 'b')", "f(*args)", "x = 1"):
        with pytest.raises(ExprError):
            X.parse(bad)


# ---------------------------------------------------------------------------
# evaluation: names, data, errors
# ---------------------------------------------------------------------------


def test_names_dotted_paths_and_unbound_errors():
    env = _env(site={"cell": {"volume": 2.0}}, K=0.5)
    assert evaluate(Name("site.cell.volume"), env) == 2.0
    assert evaluate(X.parse("K / 2"), env) == 0.25
    with pytest.raises(ExprError, match="unbound name 'nope'"):
        evaluate(Name("nope"), env)
    with pytest.raises(ExprError, match="dunder|not allowed"):
        evaluate(Name("site.__class__"), env)


def test_untagged_data_is_data_and_forms_nest_inside_it():
    env = _env(n=3)
    out = evaluate({"pools": ["A", "B"], "site": {"name": "cell", "volume": X.parse("n")}}, env)
    assert out == {"pools": ["A", "B"], "site": {"name": "cell", "volume": 3}}


def test_errors_carry_the_node_path():
    env = _env()
    with pytest.raises(ExprError) as exc:
        evaluate({"world": {"skeleton": {"route": X.chian("A")}}}, env)
    assert exc.value.path == "world.skeleton.route"
    assert "unknown head 'chian'" in str(exc.value)


# ---------------------------------------------------------------------------
# heads: functions, injection, expanders, registry views
# ---------------------------------------------------------------------------


def test_function_head_arguments_arrive_evaluated_and_ctx_is_injected():
    local = Registry()

    @fn(into=local, summary="hill")
    def hill(s: float, k: float, n: float = 1.0) -> float:
        return s**n / (k**n + s**n)

    @fn(into=local, kind="dist")
    def coin(*, ctx) -> int:
        return int(ctx.rng.integers(0, 2))

    env = Env.standard(seed=3, registry=local, bindings={"s": 0.5})
    assert evaluate(X.hill(X.name("s"), 0.5, n=2), env) == pytest.approx(0.5)
    assert evaluate(X.coin(), env) in (0, 1)
    with pytest.raises(ExprError, match="hill"):
        evaluate(X.hill(1.0, 2.0, bogus=1), env)  # an argument the function does not accept


def test_expander_receives_forms_and_returns_a_form_evaluated_per_key_seed():
    local = Registry()

    @expander(into=local)
    def chain(args, kwargs, env):
        src, dst = (env.evaluate(a) if False else evaluate(a, env) for a in args)
        n = evaluate(kwargs.get("length", 3), env)
        rate = kwargs.get("rate", X.parse("lognormal(0.1, 0.3)"))  # left as a form: drawn per hop
        nodes = [src, *[f"{env.ns}.x{i}" for i in range(1, n)], dst]
        return {
            "molecules": {m: {} for m in nodes[1:-1]},
            "reactions": {f"{env.ns}.hop{i}": {"reactants": [a], "products": [b], "rate": rate}
                          for i, (a, b) in enumerate(zip(nodes, nodes[1:]), 1)},
        }

    env = Env.standard(seed=1, registry=local)
    for name in ("lognormal", "range"):
        local.register(registry.get(name))
    frag = evaluate({"route": X.chain("A", "B", length=3)}, env)["route"]
    assert set(frag["molecules"]) == {"route.x1", "route.x2"}
    rates = [r["rate"] for r in frag["reactions"].values()]
    assert len(rates) == 3 and len(set(rates)) == 3  # one independent draw per hop
    again = evaluate({"route": X.chain("A", "B", length=3)}, Env.standard(seed=1, registry=local))["route"]
    assert again == frag  # same seed, same world


def test_registry_views_narrow_the_visible_heads():
    view = registry.view(kinds={"math"})
    assert "sqrt" in view and "lognormal" not in view and "each" in view  # special forms always show
    env = Env.standard(seed=1, registry=view)
    with pytest.raises(ExprError, match="unknown head 'lognormal'"):
        evaluate(X.lognormal(0, 1), env)


# ---------------------------------------------------------------------------
# quoted forms
# ---------------------------------------------------------------------------


def test_quoted_form_is_a_dist_and_run_evaluates_it_now():
    env = _env(seed=5, k=2.0)
    q = evaluate(Quoted(X.parse("lognormal(0.1, 0.3) * k")), env)
    assert isinstance(q, QuotedForm) and isinstance(q, Dist)
    a, b = q.sample(Seed(1)), q.sample(Seed(2))
    assert a != b and q.sample(Seed(1)) == a
    assert q.run({"k": 0.0}) == 0.0
    assert evaluate(X.parse("run(quote(k + 1))"), env) == 3.0
    assert evaluate(X.run(Quoted(X.parse("turns * 2")), {"turns": 4}), env) == 8


# ---------------------------------------------------------------------------
# special forms
# ---------------------------------------------------------------------------


def test_let_each_if_seed():
    env = _env()
    assert evaluate(X.let({"n": 3, "k": X.parse("n * 0.5")}, {"count": X.name("n"), "rate": X.name("k")}), env) == {"count": 3, "rate": 1.5}
    assert evaluate(X.each(over=[1, 2, 3], **{"as": "i"}, body=X.parse("i * 10")), env) == [10, 20, 30]
    mapping = evaluate(X.each(over=["a", "b"], **{"as": "x"}, key=X.parse("f'pool_{x}'"), body={"role": "energy"}), env)
    assert mapping == {"pool_a": {"role": "energy"}, "pool_b": {"role": "energy"}}
    assert evaluate(X.each(over=X.parse("range(5)"), **{"as": "i"}, where=X.parse("i % 2 == 0"), body=X.name("i")), env) == [0, 2, 4]
    assert evaluate(X.call("if", cond=False, then=1), env) is None
    assert evaluate(X.call("if", cond=True, then=1, **{"else": X.parse("nope")}), env) == 1  # untaken branch never evaluated
    s = evaluate(X.seed("kinetics"), env)
    assert isinstance(s, Seed) and s == env.ctx.seed.child("kinetics")
    with pytest.raises(ExprError, match="unknown keyword"):
        evaluate(X.each(over=[1], **{"as": "i"}, body=1, bogus=2), env)


def test_template_is_a_function_with_positional_names_and_param_defaults():
    doc = """
K: 0.5
cyc: !template
  positional: [waste]
  params: {count: 2, rate: !x K}
  body:
    rx: !each {over: !x range(count), as: i, body: {r: !x rate, w: !x waste}}
a: !cyc [shared]
b: !cyc {args: [null], count: 3, rate: 9}
"""
    env = _env().load("doc.yaml", text=doc)
    vals = env.force_all()
    assert isinstance(vals["cyc"], TemplateHead)
    assert vals["a"] == {"rx": [{"r": 0.5, "w": "shared"}] * 2}
    assert vals["b"] == {"rx": [{"r": 9, "w": None}] * 3}
    with pytest.raises(ExprError, match="no parameter 'bogus'"):
        evaluate(X.cyc("x", bogus=1), env)
    with pytest.raises(ExprError, match="missing positional argument 'waste'"):
        evaluate(X.cyc(), env)


def test_a_file_is_a_scope_with_order_independent_lazy_bindings_and_cycle_errors():
    env = _env().load("doc.yaml", text="later: !x earlier + 1\nearlier: 41\n")
    assert evaluate(Name("later"), env) == 42
    cyc = _env().load("doc.yaml", text="a: !x b\nb: !x a\n")
    with pytest.raises(ExprError, match="cyclic definition"):
        evaluate(Name("a"), cyc)


# ---------------------------------------------------------------------------
# seeds
# ---------------------------------------------------------------------------


def test_every_named_node_draws_under_its_own_child_seed():
    doc_a = "a: !x lognormal(0, 1)\nb: !x lognormal(0, 1)\n"
    doc_b = "a: !x lognormal(0, 1)\nz: !x lognormal(0, 1)\nb: !x lognormal(0, 1)\n"
    va = _env(seed=9).load("d", text=doc_a).force_all()
    vb = _env(seed=9).load("d", text=doc_b).force_all()
    assert va["a"] != va["b"]
    assert va["a"] == vb["a"] and va["b"] == vb["b"]  # inserting z re-rolls nothing
    assert _env(seed=10).load("d", text=doc_a).force_all()["a"] != va["a"]


# ---------------------------------------------------------------------------
# limits
# ---------------------------------------------------------------------------


def test_limits_fail_loudly_never_truncate():
    env = Env.standard(seed=1, limits=Limits(entities=10, depth=5))
    with pytest.raises(ExprError, match="exceeds limits.entities"):
        evaluate(X.each(over=X.parse("range(11)"), **{"as": "i"}, body=1), env)
    with pytest.raises(ExprError, match="limits.depth"):
        evaluate({"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}}, env)
