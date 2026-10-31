"""Verifier AE follow-ups on the sign fold (T091 AE1, AE6).

AE1: an ``if`` whose condition is a bool, a string comparison or a name bound
to either folded to ``None`` ("reads a pool"), so a ``!x``-bound draw fell back
to the seed's drawn number — refused on 2 of 20 seeds, loaded on 18. The
condition is now ignored unless it reads a pool, and a drawn binding whose fold
gives up refuses at load by name. AE6: unary ``+``, ``%`` and ``//`` fold."""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError

SEEDS = range(20)


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
        "flag: true\nk: !x 'normal(0.3, 0.3) if flag else 0.3'",
        "mode: fast\nk: !x \"normal(0.3, 0.3) if mode == 'fast' else 0.3\"",
        "k: !x 'normal(0.3, 0.3) if True else 0.3'",
        "k: !x 'normal(0.3, 0.3) if 1 > 0 else 0.3'",
    ],
)
def test_constant_condition_is_ignored_one_verdict_on_every_seed(pre: str) -> None:
    verdicts = _verdicts(pre)
    assert len(verdicts) == 1, verdicts
    (verdict,) = verdicts
    assert "negative rate constant possible" in verdict and "on every seed" in verdict


@pytest.mark.parametrize(
    "pre",
    [
        "flag: true\nk: !x 'abs(normal(0.3, 0.3)) if flag else 0.3'",
        "mode: fast\nk: !x \"uniform(0.1, 0.5) if mode == 'fast' else 0.3\"",
        "k: !x 'lognormal(0, 1) if True else 0.3'",
    ],
)
def test_constant_condition_non_negative_branches_load(pre: str) -> None:
    assert _verdicts(pre) == {"loads"}


def test_drawn_binding_whose_fold_gives_up_refuses_by_name() -> None:
    verdicts = _verdicts("k: !x \"abs(normal(0.3, 0.1)) * len('ab')\"")
    assert len(verdicts) == 1, verdicts
    (verdict,) = verdicts
    assert "the sign fold cannot read k" in verdict and "on every seed" in verdict


@pytest.mark.parametrize(
    "pre",
    [
        "k: !x '+uniform(0.1, 0.5)'",
        "k: !x 'uniform(0.1, 0.5) % 1'",
        "k: !x 'uniform(1.1, 5.5) % 1'",
        "k: !x 'uniform(1, 5) // 1'",
    ],
)
def test_pos_mod_floordiv_fold(pre: str) -> None:
    assert _verdicts(pre) == {"loads"}


@pytest.mark.parametrize(
    ("pre", "support"),
    [
        ("k: !x '+uniform(-0.5, 0.5)'", "[-0.5, 0.5]"),
        ("k: !x 'uniform(-0.5, 0.5) // 1'", "[-1, 0]"),
    ],
)
def test_pos_floordiv_straddle_refuses_with_support(pre: str, support: str) -> None:
    (verdict,) = _verdicts(pre)
    assert "negative rate constant possible" in verdict and support in verdict


def test_fold_note_prints_source_shaped_operator_names() -> None:
    from alienbio.suite import rate_law

    assert rate_law._CMP_SHOW["op:pos"] == "+x"
    assert rate_law._CMP_SHOW["op:floordiv"] == "a // b"
    assert rate_law._CMP_SHOW["op:mod"] == "a % b"
    assert "// %" in rate_law.FOLDED_FORMS and "unary + -" in rate_law.FOLDED_FORMS
