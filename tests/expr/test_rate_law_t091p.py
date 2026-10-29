"""T092 follow-ups (verifier P): the sign fold over a bound draw's form.

T092 folds a ``!x``-bound draw by its FORM, so the verdict is the inline
draw's on every seed. P1: heads the fold did not model (``if`` / ``round`` /
``float`` / ``int`` / ``sum`` / a self-product) folded to the whole line, so a
draw that is non-negative on every seed refused on every seed. P4: a quoted
constant passed to a call was called "a distribution still to be drawn"."""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError

SEEDS = range(12)


def _doc(rate: str, pre: str) -> str:
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


def _verdicts(pre: str, rate: str = "!q k * A") -> set[str]:
    out = set()
    for seed in SEEDS:
        try:
            Env.standard(seed=seed).load("<rate>", text=_doc(rate, pre)).force_all()["w"]
            out.add("loads")
        except ExprError as exc:
            out.add(exc.message)
    return out


@pytest.mark.parametrize(
    "pre",
    [
        # the clip idiom: the then-branch is the compared name, bounded by the test
        "base: !x normal(0.3, 0.3)\nk: !x 'base if base > 0 else 0.01'",
        "base: !x normal(0.3, 0.3)\nk: !x '0 if base < 0 else base'",
        "base: !x normal(0.3, 0.3)\nk: !x '0.01 if 0 > base else base'",
        "base: !x normal(0.3, 0.3)\nk: !x 'base if base >= 0.05 else 0.05'",
        # the union of two non-negative branches, the condition ignored
        "k: !x 0.1 if normal(0, 1) > 0 else 0.2",
        # round / float / int map the bounds
        "k: !x round(uniform(0.1, 0.5), 2)",
        "k: !x float(uniform(0.1, 0.5))",
        "k: !x int(uniform(1, 5))",
        # a sum of intervals
        "k: !x sum([uniform(0.1, 0.2), 0.3])",
        "k: !x uniform(0.1, 0.2) + lognormal(0, 1)",
        # one name read twice is a square; x ** 2 and abs are non-negative
        "n: !x normal(0, 1)\nk: !x n * n",
        "k: !x normal(0, 1) ** 2",
        "k: !x abs(normal(0, 1))",
        "k: !x max(normal(0, 1), 0.01)",
    ],
)
def test_a_bound_draw_non_negative_on_every_seed_loads(pre):
    assert _verdicts(pre) == {"loads"}


@pytest.mark.parametrize(
    "pre",
    [
        # the branch the comparison does not bound still reaches below zero
        "base: !x normal(0.3, 0.3)\nk: !x 'base if base < 0 else 0.01'",
        "k: !x round(normal(0.3, 0.3), 2)",
        "k: !x sum([normal(0.3, 0.3), 0.3])",
        # two inline draws are two values, never a square
        "k: !x normal(0, 1) * normal(0, 1)",
        "k: !x 0.1 if normal(0, 1) > 0 else -0.2",
    ],
)
def test_a_bound_draw_that_can_go_negative_refuses_on_every_seed(pre):
    verdicts = _verdicts(pre)
    assert len(verdicts) == 1, verdicts
    (message,) = verdicts
    assert "negative rate constant possible" in message or "product of two distributions" in message, message


def test_a_head_outside_the_fold_refuses_naming_the_covered_forms():
    (message,) = _verdicts("k: !x 'sorted([uniform(0.1, 0.3), 0.2])[1]'")
    assert "the sign fold reads an index as the whole line" in message
    assert "round, float, int, sum([...]), `a if c else b`" in message
    (message,) = _verdicts(
        "k: !x 'sorted([uniform(0.1, 0.3), 0.2])[1]'", rate="!q 0.2 * A * inhibitor(B, k)"
    )
    assert message.startswith("rate law: inhibitor.Ki can be negative") and "it covers numbers" in message


def test_a_quoted_constant_in_a_call_is_named_as_one():
    (message,) = _verdicts("k: !q 0.3", rate="!q max(k, 0.05) * A")
    assert "a quoted constant" in message and "bind it with !x or write the number inline" in message
    assert "a distribution still to be drawn" not in message
    (message,) = _verdicts("k: !q normal(0.3, 0.1)", rate="!q max(k, 0.05) * A")
    assert "a distribution still to be drawn" in message
