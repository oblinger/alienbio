"""T091 AL — verifier AL's re-attack of the Expr sandbox after round AH:
unmetered allocation and CPU (AL4–AL6), raw exceptions out of the evaluator
(AL7), a nested ``!experiment`` silently dropped (AL9), and a callable
binding usable as a head only after something forced it (AL10). The trust
half (AL1–AL3, AL8) is ``test_t091_al_trust.py``.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from alienbio.expr import Env, ExprError, X, evaluate
from alienbio.expr.env import Limits
from alienbio.suite.spec import REPO_ROOT, load_spec

ECOSYSTEM = REPO_ROOT / "catalog" / "examples" / "ecosystem" / "ecosystem.yaml"


def _doc(text: str, *, trusted: bool = False, limits: Limits | None = None, path: str = "<t>"):
    return Env.standard(seed=1, trusted=trusted, limits=limits).load(path, text=text)


def _x(text: str, *, trusted: bool = False, limits: Limits | None = None, **bindings):
    return evaluate(X.parse(text), Env.standard(seed=1, trusted=trusted, limits=limits, bindings=bindings))


def _marker_helper(directory: Path, marker: Path, name: str = "helpers.py") -> None:
    (directory / name).write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('RAN')\n")


# ---- AL4-AL6: allocation and CPU ---------------------------------------------


def test_al4_to_bytes_is_charged_by_its_length():
    t = time.monotonic()
    with pytest.raises(ExprError, match="limits.entities"):
        _x("len((1).to_bytes(300000000, 'big'))")
    assert time.monotonic() - t < 2


@pytest.mark.parametrize("text", ["len(str(c))", 'len(f"{c}")', "len('%s' % (c,))", "len(f'{c!r}')"])
def test_al5_rendering_a_shared_nested_list_is_charged_before_it_is_built(text):
    t = time.monotonic()
    with pytest.raises(ExprError, match="limits.entities"):
        _doc(f"a: !x '[0] * 1000'\nb: !x '[a] * 1000'\nc: !x '[b] * 100'\ns: !x {text!r}\n").lookup("s")
    assert time.monotonic() - t < 2


def test_al5_small_renderings_are_unchanged():
    assert _x("str([1, 'a', {'k': [2.5, None]}])") == "[1, 'a', {'k': [2.5, None]}]"
    assert _x("f'{[1, 2]}-{3}'") == "[1, 2]-3"
    assert _x("'%(k)s' % {'k': [1, 2]}") == "[1, 2]"


@pytest.mark.parametrize("text,match", [
    ("(10**1000)**4000 > 0", "pow: result"),
    ("pow(3, (10**100)**100, 10**3000) > 0", "exponent bits x modulus bits"),
])
def test_al6_big_int_work_refuses_quickly(text, match):
    t = time.monotonic()
    with pytest.raises(ExprError, match=match):
        _x(text)
    assert time.monotonic() - t < 2


def test_al6_a_squaring_chain_refuses_at_the_result_bit_cap():
    t = time.monotonic()
    env = _doc("x: !x '(10**1000)**150'\ny: !x 'x * x'\nz: !x 'y * y'\n")
    assert env.lookup("y") > 0
    with pytest.raises(ExprError, match="mul: result of"):
        env.lookup("z")
    assert time.monotonic() - t < 5


def test_al6_modest_int_arithmetic_still_works():
    assert _x("pow(3, 1000, 10**9 + 7)") == pow(3, 1000, 10**9 + 7)
    assert _x("(10**100) * (10**100)") == 10**200


def test_al6_the_wall_clock_budget_stops_a_long_evaluation():
    t = time.monotonic()
    with pytest.raises(ExprError, match=r"limits.seconds=0.001"):
        _x("[[j for j in range(50)] for i in range(5000)]", limits=Limits(seconds=0.001))
    assert time.monotonic() - t < 2


def test_al6_each_top_level_evaluation_gets_its_own_clock():
    env = Env.standard(seed=1, limits=Limits(seconds=0.5))
    for _ in range(3):
        evaluate(X.parse("[i for i in range(1000)]"), env)
        time.sleep(0.2)  # time between evaluations is not charged
    assert env.ctx.limits.meter.clock.active == 0


# ---- AL7: raw exceptions become ExprError ------------------------------------


@pytest.mark.parametrize("text,kind", [("'a'.encode('bogus')", "LookupError"), ("'a'.encode('rot13')", "LookupError")])
def test_al7_a_raw_exception_is_wrapped(text, kind):
    with pytest.raises(ExprError, match=kind):
        _x(text)


# ---- AL9: an !experiment must be a top-level key ------------------------------

_EXPERIMENT = (
    "!experiment {name: N, task: !q 'identify_pathway(pathway_length=3)', "
    "episode: !q 'episode(max_turns=6, sim_steps=10)', agent: measure_commit, "
    "trials_per_condition: 1, base_seed: 7, out_dir: runs/N}"
)


@pytest.mark.parametrize("nested", [
    "e2:\n  - " + _EXPERIMENT.replace("N", "b"),
    "e2:\n  inner: " + _EXPERIMENT.replace("N", "b"),
])
def test_al9_a_nested_experiment_refuses(tmp_path, nested):
    spec = tmp_path / "nested.yaml"
    spec.write_text("e1: " + _EXPERIMENT.replace("N", "a") + "\n" + nested + "\n")
    with pytest.raises(ExprError, match="an experiment must be a top-level document key"):
        load_spec(spec)


# ---- AL10: a callable binding is a head regardless of document order ----------


def test_al10_a_callable_binding_works_as_a_head_before_it_is_forced():
    text = "r: !x c(1)\nc: !x diagnose().task.skeleton.motif.roles[0].constraints[0]\n"
    assert _doc(text, trusted=True).lookup("r") is True


def test_al10_a_non_callable_binding_used_as_a_head_says_so():
    with pytest.raises(ExprError, match="not a head or a callable"):
        _doc("r: !x k(1)\nk: 3\n").lookup("r")
