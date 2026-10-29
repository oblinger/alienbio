"""T091 I1–I3 — a rate law's constant factor is non-negative by construction.

Refused at LOAD and seed-independent: a distribution whose support reaches
below zero in a rate-constant position, and constant arithmetic folding
negative, in both the ``!q`` and ``!x`` spellings. A law whose value goes
negative because of state is not a constant and loads; the asymmetry
``-0.2 * (A - 5)`` refuses / ``0.2 * (5 - A)`` loads is the rule's stated
consequence (``suite/rate_law.py`` module docstring)."""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError
from alienbio.suite.dist import Constant, LogNormal, Normal, Uniform, support_of
from alienbio.suite.rate_law import compile_rate
from alienbio.suite.verify import SimConfig, simulate


def _doc(rate: str, pre: str = "") -> str:
    return f"""
{pre}
sk: !skeleton
  root: !block
    children:
      r: !reaction
        reactants: [A, B]
        products: [C]
        rate: {rate}
w: !world {{skeleton: !x sk, initial: {{A: 2.0, B: 3.0}}}}
"""


def _load(rate: str, pre: str = "", seed: int = 1):
    return Env.standard(seed=seed).load("<rate>", text=_doc(rate, pre)).force_all()["w"]


def _rate(rate: str, pre: str = "") -> float:
    dt = 1e-4
    state = simulate(_load(rate, pre), SimConfig(dt=dt, steps=1, sample_every=1)).states[-1]
    mols = list(state.molecule_ids or ())
    return state.get(0, mols.index(next(m for m in mols if m.endswith("C")))) / dt


NEG = r"sk\.root\.children\.r(\.rate)?: .*negative rate constant"


@pytest.mark.parametrize(
    "rate, pre",
    [
        ("!q k - 1", "k: 0.5"),
        ("!x 'k - 1'", "k: 0.5"),
        ("!q (k - 1) * A", "k: 0.5"),
        ("!q 0.5 - 1", ""),
        ("!x '0.5 - 1'", ""),
        ("!q 0.2 / -1", ""),
        ("!x '0.2 / -1'", ""),
        ("!q A / -5", ""),
        ("!q k3", "k3: !q normal(-5, 0.1)"),
        ("!q k3 * A", "k3: !q normal(-5, 0.1)"),
        ("!q k * A", "k: !x normal(-5, 0.1)"),
        ("!q -0.2 * (A - 5)", ""),
        ("!q 0.2 * -(A - 5)", ""),
    ],
)
def test_a_negative_constant_factor_refuses_at_load(rate, pre):
    with pytest.raises(ExprError, match=NEG):
        _load(rate, pre)


@pytest.mark.parametrize(
    "rate",
    [
        "!q normal(0.3, 0.3) * A",
        "!q normal(5, 0.01)",
        "!q uniform(-0.1, 1.0) * A",
        "!q 0.2 * uniform(-1, 1)",
        "!q A / normal(1, 0.1)",
    ],
)
def test_a_distribution_reaching_below_zero_refuses_naming_its_support(rate):
    with pytest.raises(ExprError, match=NEG + r" possible — .*support \["):
        _load(rate)


def test_a_bound_distribution_is_named_with_its_support():
    with pytest.raises(ExprError, match=r"k \(bound to normal\(0\.3, 0\.3\)\) has support \[-inf, inf\]"):
        _load("!q k * A", "k: !q normal(0.3, 0.3)")


def test_the_verdict_does_not_depend_on_the_seed():
    """Round E refused only the seeds that drew negative (7 of 40), so
    preflight passed and the run wrote error records after spend."""
    messages = set()
    for seed in range(40):
        with pytest.raises(ExprError) as exc:
            _load("!q normal(0.3, 0.3) * A", seed=seed)
        messages.add(str(exc.value))
    assert len(messages) == 1


def test_non_negative_supports_and_state_dependent_signs_load():
    assert _rate("!q uniform(0.1, 1.0) * A") > 0.0
    assert _rate("!q lognormal(0, 1) * A") > 0.0
    assert _rate("!q exp(-1) * A") == pytest.approx(0.7357588823, rel=1e-6)
    assert _rate("!q -1 * -0.2 * A") == pytest.approx(0.4)
    assert _rate("!q -k * A", "k: -0.2") == pytest.approx(0.4)
    assert _rate("!q 0.2 * (5 - A)") == pytest.approx(0.6)
    assert _rate("!q 5 - A") == pytest.approx(3.0)


def test_a_negative_value_from_state_reads_as_zero():
    # 0.2 * (1 - A) at A = 2 is -0.2: it loads (no constant is negative) and runs as 0
    assert _rate("!q 0.2 * (1 - A)") == 0.0


def test_a_dist_object_rate_is_checked_by_its_support():
    env = Env.standard(seed=0)
    with pytest.raises(ExprError, match="negative rate constant possible"):
        compile_rate(Normal(0.3, 0.3), env)
    with pytest.raises(ExprError, match="negative rate constant possible"):
        compile_rate(Uniform(-1.0, 1.0), env)
    assert compile_rate(LogNormal(0.0, 1.0), env).k == LogNormal(0.0, 1.0)
    assert support_of(Constant(-2.0)) == (-2.0, -2.0)
    assert support_of(Constant("x")) is None
