"""T088 generators-and-Expr round: suite/expr_heads, rate_law,
expr_experiment, drafters and agents.

Each test pins one finding from the module-doc pass (numbered as in the T088
findings doc, e.g. ``rate_law 1``): it failed before its fix and passes
after.
"""

from __future__ import annotations

import dataclasses

import pytest

from alienbio.expr import Env, ExprError, X, evaluate, fn
from alienbio.suite.agents import _PursueTargetAgent
from alienbio.suite.dist import Seed
from alienbio.suite.expr_experiment import load_experiment, spec_to_text


@fn(name="t088s_same")
def _same(w):  # type: ignore[no-untyped-def]
    return w


@fn(name="t088s_ok")
def _ok(a, b):  # type: ignore[no-untyped-def]
    return True


_TEMPLATE_WORLD = """
mk: !template
  body: !world
    skeleton: !skeleton
      root: !block
        children:
          src: !source {pool: P, rate: 1.0}
          snk: !sink {pool: P, rate: 1.0}
"""


# suite/expr_heads 1–3 --------------------------------------------------------------


def test_a_verified_template_world_is_named_by_its_key():
    doc = _TEMPLATE_WORLD + """
one: !verify {world: !x mk(), perturb: t088s_same, valid: t088s_ok, sim: !sim {steps: 5}}
two: !verify {world: !x mk(), perturb: t088s_same, valid: t088s_ok, sim: !sim {steps: 5}}
"""
    vals = Env.standard(seed=1).load("doc.yaml", text=doc).force_all()
    # was root/attempt0.P, and the second verify refused the instance claim
    assert list(vals["one"].chemistry.molecules) == ["root/one.P"]
    assert list(vals["two"].chemistry.molecules) == ["root/two.P"]


def test_world_heads_carry_no_unread_guard_metadata():
    from alienbio.expr import registry
    from alienbio.suite.drafters import guarded_dials

    for name in ("pressure_world", "conflict_world", "diagnosis_world", "intervention_world"):
        assert registry.get(name).guarded_params == frozenset()
    assert {"pi", "rung", "hazard", "perturbation", "target_margin"} <= guarded_dials()


def test_a_block_refuses_one_pool_named_in_two_compartments():
    env = Env.standard(seed=1)
    with pytest.raises(ExprError, match="one compartment"):
        evaluate(X.block(children={"a": X.source(pool="x", container="a"), "b": X.sink(pool="x", container="b")}), env)
    evaluate(X.block(children={"a": X.source(pool="x", container="a"), "b": X.sink(pool="x", container="a")}), env)


# suite/rate_law 1, 3, 5 ------------------------------------------------------------


def test_a_product_law_naming_a_reactant_compiles_inside_a_template():
    doc = """
mk: !template
  body: !reaction {reactants: [S], products: [T], rate: !q "2 * S * hill('M', 0.5)"}
top: !reaction {reactants: [S], products: [T], rate: !q "2 * S * hill('M', 0.5)"}
inst: !x mk()
"""
    vals = Env.standard(seed=1).load("doc.yaml", text=doc).force_all()  # inst refused "unbound name 'S'"
    # A law naming its reactant is the whole rate (T091 E4) — the expression
    # path, in the template as at top level, over the namespaced pool there.
    assert vals["inst"].law.expr is not None and vals["top"].law.expr is not None
    assert any(p.endswith("S") for p in vals["inst"].law.expr_pools) and "S" in vals["top"].law.expr_pools


def test_an_unbound_factor_falls_back_to_the_expression_grammar():
    doc = 'r: !reaction {reactants: [S], products: [T], rate: !q "2 * Q * hill(\'M\', 0.5)"}\n'
    vals = Env.standard(seed=1).load("doc.yaml", text=doc).force_all()  # refused "unbound name 'Q'"
    assert vals["r"].law.expr is not None and "Q" in vals["r"].law.expr_pools


def test_the_numeric_rate_heads_read_as_the_engine_does():
    from alienbio.suite.rate_law import hill, inhibitor

    assert inhibitor(1.0, 0.0) == 0.0  # 1 / (1 + inf); raised ZeroDivisionError
    assert hill(0.5, 0.5, n=2) == pytest.approx(0.5)


# suite/expr_experiment 1–3 ---------------------------------------------------------


def _exp02_without_pi():
    spec = load_experiment("catalog/experiments/exp02.yaml")
    return dataclasses.replace(spec, design=None, axes=tuple(a for a in spec.axes if a[0] != "pi"))


@pytest.mark.parametrize("name", ["no", "null", "a: b", "x #y"])
def test_spec_to_text_quotes_the_name(name):
    spec = dataclasses.replace(load_experiment("catalog/experiments/exp02.yaml"), name=name, out_dir="runs/a: b #c")
    back = load_experiment("x.yaml", text=spec_to_text(spec))
    assert back.name == name and back.out_dir == "runs/a: b #c"


@pytest.mark.parametrize("value", [-1.5, float("inf"), float("-inf")])
def test_a_negative_or_infinite_dial_round_trips(value):
    spec = dataclasses.replace(_exp02_without_pi(), fixed_dials={**_exp02_without_pi().fixed_dials, "pi": value})
    assert load_experiment("x.yaml", text=spec_to_text(spec)).fixed_dials["pi"] == value


def test_a_nan_dial_refuses_to_render():
    spec = dataclasses.replace(_exp02_without_pi(), fixed_dials={**_exp02_without_pi().fixed_dials, "pi": float("nan")})
    with pytest.raises(ValueError, match="NaN"):
        spec_to_text(spec)


def test_a_swept_dial_bound_to_another_name_already_refuses():
    """expr_experiment 3, withdrawn: the typo leaves the axis unread, and
    the experiment head already refuses an axis no call reads."""
    text = """
framng: 'Raise both targets.'
exp: !experiment
  name: typo
  task: !q conflict(rung=rung)
  brief: !q brief(framing=framng, levers=[])
  agent: survey_commit
  axes:
    rung: [compatible, latent]
    framing: ['a', 'b']
  trials_per_condition: 1
  base_seed: 1
"""
    with pytest.raises(ExprError, match="no call reads them"):
        load_experiment("x.yaml", text=text)


# suite/drafters 3 ------------------------------------------------------------------


def test_the_guarded_constants_see_a_late_registration():
    from alienbio.expr import registry
    from alienbio.suite import drafters, experiment

    @fn(kind="drafter", name="late_guarded_t088", guarded=True, summary="late")
    def late_guarded_t088(*, env):  # pragma: no cover — never called
        raise AssertionError

    try:
        assert "late_guarded_t088" in drafters.GUARDED_DRAFTERS  # the import-time snapshot missed it
        assert "late_guarded_t088" in experiment.GUARDED_DRAFTERS
    finally:
        registry._heads.pop("late_guarded_t088", None)
    assert "late_guarded_t088" not in drafters.GUARDED_DRAFTERS


# suite/agents 1 --------------------------------------------------------------------


def test_pursue_target_reads_the_target_summed_over_compartments():
    agent = _PursueTargetAgent(Seed(1))
    agent._target, agent._goal = "T", 10.0
    observation = ({"T": 6.0}, {"T": 6.0})
    assert agent._reading(observation) == 12.0  # was 6.0, the first compartment's
    action, _ = agent.act(observation)
    assert type(action).__name__ == "Commit"
