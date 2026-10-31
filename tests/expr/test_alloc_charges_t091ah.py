"""T091 AH: allocations proportional to an argument are charged before they
are built (``(1).to_bytes(10**9, 'big')`` was a gigabyte charged 0)."""

from __future__ import annotations

import pytest

from alienbio.expr import Env, ExprError, X, evaluate


def _env() -> Env:
    return Env.standard(seed=1).load("doc.yaml", text="x: 1\n")


@pytest.mark.parametrize("text", [
    "(1).to_bytes(10**9, 'big')",
    "(1).to_bytes(length=2000000)",
    "{1}.union(xs, ys)",
])
def test_a_huge_allocation_refuses_before_it_is_built(text):
    # xs / ys cost 800k of the 1M cap to build; the union's 400k is what crosses it.
    env = Env.standard(seed=1).load("doc.yaml", text="xs: !x list(range(200000))\nys: !x list(range(1, 200001))\n") \
        if "xs" in text else _env()
    with pytest.raises(ExprError, match=r"method (to_bytes|union).*exceeds limits.entities"):
        evaluate(X.parse(text), env)


def test_small_allocations_still_load():
    env = _env()
    assert evaluate(X.parse("(5).to_bytes(2, 'little')"), env) == b"\x05\x00"
    assert evaluate(X.parse("(1).to_bytes()"), env) == b"\x01"
    assert evaluate(X.parse("{1}.union([2, 3])"), env) == {1, 2, 3}
    assert evaluate(X.parse("{}.fromkeys(['a'])"), env) == {"a": None}
    assert evaluate(X.parse("(7).bit_length()"), env) == 3


@pytest.mark.parametrize("text", [
    "'a'.encode().fromhex('00' * 300000 + '00' * 300000)",
    "'ab' * 600000",
    "'a'.zfill(2000000)",
    "'a\\tb'.expandtabs(2000000)",
    "'-'.join(['ab'] * 400000)",
    "sorted(range(2000000))",
    "list('a' * 2000000)",
    "pow(3, 2000000)",
])
def test_the_previously_charged_allocations_still_refuse(text):
    with pytest.raises(ExprError, match="exceeds"):
        evaluate(X.parse(text), _env())


@pytest.mark.parametrize("text", ["'{:>2000000}'.format(1)", "'{a}'.format_map({'a': 1})"])
def test_str_format_is_denied_by_name(text):
    with pytest.raises(ExprError, match="not allowed"):
        evaluate(X.parse(text), _env())
