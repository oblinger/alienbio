"""T091 E4 / E9 — the rate grammar's whole-rate rule and its two refusals.

A law that names a reactant is the whole rate, whether or not it also has
the product-form shape (``0.2 * A`` read as ``0.2·A·B`` over ``A + B`` while
``0.2 * A + 0.0`` read as ``0.2·A``); a product of two distributions and a
negative rate constant refuse at load, naming the reaction's node."""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError
from alienbio.suite.verify import SimConfig, simulate

A0, B0 = 2.0, 3.0


def _world(law: str, reactants: str = "[A, B]", products: str = "[C]"):
    doc = f"""
sk: !skeleton
  root: !block
    children:
      r: !reaction
        reactants: {reactants}
        products: {products}
        rate: !q {law}
w: !world {{skeleton: !x sk, initial: {{A: {A0}, B: {B0}}}}}
"""
    return Env.standard(seed=1).load("<rate>", text=doc).force_all()["w"]


def _rate(law: str, **kw: str) -> float:
    """d[C]/dt at t = 0, read off one tiny step."""
    dt = 1e-4
    state = simulate(_world(law, **kw), SimConfig(dt=dt, steps=1, sample_every=1)).states[-1]
    mols = list(state.molecule_ids or ())
    return state.get(0, mols.index(next(m for m in mols if m.endswith("C")))) / dt


def test_a_law_naming_a_reactant_is_the_whole_rate_in_either_shape():
    assert _rate("0.2 * A") == pytest.approx(_rate("0.2 * A + 0.0")) == pytest.approx(0.2 * A0)
    assert _rate("A * 0.2") == pytest.approx(0.2 * A0)
    assert _rate("0.2 * B") == pytest.approx(0.2 * B0)
    assert _rate("0.2 * A * B") == pytest.approx(0.2 * A0 * B0)
    assert _rate("-(-0.2) * A") == pytest.approx(0.2 * A0)


def test_a_reactant_that_is_also_a_product_still_makes_the_law_the_whole_rate():
    # A + B -> A + C (A catalytic): the law names a reactant, so it is the rate
    assert _rate("0.2 * A", products="[A, C]") == pytest.approx(0.2 * A0)
    assert _rate("0.2 * A + 0.0", products="[A, C]") == pytest.approx(0.2 * A0)


def test_a_constant_law_is_still_mass_action():
    assert _rate("0.2") == pytest.approx(0.2 * A0 * B0)


@pytest.mark.parametrize("law", ["lognormal(0, 1) * lognormal(0, 1) * A", "lognormal(0, 1) * lognormal(0, 1)", "lognormal(0, 1) * A * -lognormal(0, 1)"])
def test_a_product_of_two_distributions_refuses(law):
    with pytest.raises(ExprError, match=r"sk\.root\.children\.r\.rate: .*product of two distributions"):
        _world(law)


def test_one_distribution_times_a_pool_still_loads():
    assert _rate("lognormal(0, 1) * A") > 0.0


@pytest.mark.parametrize("law", ["-0.2 * A", "-0.2", "-(0.2) * hill(B, 0.5)", "0.2 * -A"])
def test_a_negative_rate_constant_refuses_naming_the_reaction(law):
    with pytest.raises(ExprError, match=r"sk\.root\.children\.r\.rate: .*negative rate constant"):
        _world(law)
