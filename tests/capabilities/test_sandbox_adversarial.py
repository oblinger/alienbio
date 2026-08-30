"""M48.5 — the sandbox and the limits, adversarially.

A hostile corpus for ``!x`` / ``!q``: attribute walks, format-string
escapes, the denied builtins, comprehension and allocation bombs, deep
nesting, huge counts — every one refused with the node's path and none of
them doing the work first. The entity / depth / attempt caps fire with the
path; an untrusted load cannot reach ``!py`` or a ``.py`` include.
"""

from __future__ import annotations

import time

import pytest

from alienbio.expr import Env, ExprError, UnsafeSpecError, X, evaluate
from alienbio.expr.env import Limits


def _x(text: str, **bindings):
    return evaluate(X.parse(text), Env.standard(seed=1, bindings=bindings))


def _doc(text: str, **limits):
    return Env.standard(seed=1, limits=Limits(**limits) if limits else None).load("<adv>", text=text).force_all()


ATTRIBUTE_WALKS = [
    "().__class__.__bases__[0].__subclasses__()",
    "x.__dict__",
    "x.__class__.__mro__",
    "f.__globals__",
    "f.__code__",
    "g.gi_frame.f_back",
    "x.__reduce__()",
    "type(x).__subclasses__()",
]

ESCAPES = [
    "'{0.__class__}'.format(x)",
    "f'{x.__class__}'",
    "f'{x.__init__.__globals__}'",
    "'%s' % x.__class__",
    "vars(x)",
    "getattr(x, '__class__')",
    "globals()",
    "locals()",
    "__import__('os').system('true')",
    "open('/etc/passwd')",
    "eval('1')",
    "exec('pass')",
    "compile('1', 'x', 'eval')",
    "breakpoint()",
    "input()",
    "x = 1",
    "(y := 1)",
    "lambda: 1",
    "f(*args)",
    "f(**kw)",
    "import os",
    "[i for i in range(3)][0].__class__",
]


@pytest.mark.parametrize("text", ATTRIBUTE_WALKS + ESCAPES)
def test_hostile_expressions_are_refused_at_parse_or_evaluation(text):
    with pytest.raises(ExprError):
        _x(text, x=object(), f=len, g=iter([]), args=[], kw={})


BOMBS = [
    ("range(10**9)", "exceeds limits.entities"),
    ("list(range(10**8))", "exceeds limits.entities"),
    ("sum(range(10**9))", "exceeds limits.entities"),
    ("sorted(range(10**8))", "exceeds limits.entities"),
    ("max(range(10**9))", "exceeds limits.entities"),
    ("'a' * 10**9", "exceeds limits.entities"),
    ("[0] * 10**8", "exceeds limits.entities"),
    ("10 ** 10 ** 6", "exponent"),
    ("2 ** 100000", "exponent"),
    ("[i for i in range(10**9)]", "exceeds limits.entities"),
    ("[[0] * 10**5 for _ in range(10**5)]", "exceeds limits.entities"),
]


@pytest.mark.parametrize("text,message", BOMBS)
def test_allocation_and_cpu_bombs_are_refused_before_the_work_is_done(text, message):
    t0 = time.perf_counter()
    with pytest.raises(ExprError, match=message):
        _x(text)
    assert time.perf_counter() - t0 < 2.0, "the bomb ran before it was refused"


def test_deep_nesting_is_an_error_not_a_crash():
    with pytest.raises(ExprError):
        X.parse("(" * 500 + "1" + ")" * 500)
    with pytest.raises(ExprError):
        X.parse("[" * 500 + "1" + "]" * 500)
    deep: object = 1
    for _ in range(400):
        deep = [deep]
    with pytest.raises(ExprError, match="deeper than limits.depth"):
        evaluate({"d": deep}, Env.standard(seed=1))


def test_every_cap_fires_with_the_node_path():
    with pytest.raises(ExprError, match=r"^big.*exceeds limits.entities=5"):
        _doc("big: !each {over: !x range(10), as: i, body: !x i}\n", entities=5)
    with pytest.raises(ExprError, match=r"^deep.*deeper than limits.depth=10"):
        _doc("t: !template {positional: [n], body: !x t(n - 1) if n > 0 else 0}\ndeep: !x t(100)\n", depth=10)
    with pytest.raises(ExprError, match=r"^draw.*still failing after 2 attempts"):
        _doc("draw: !range {args: [3], guards: [!x max_size(n=1)], on_fail: retry}\n", attempts=2)


def test_untrusted_loads_cannot_reach_python(tmp_path):
    (tmp_path / "evil.py").write_text("import os\nos.environ['ABIO_PWNED'] = '1'\n")
    for text in ("h: !include evil.py\n", "_includes_: [evil.py]\n", "f: !py os.system\n", "f: !py evil.pwn\n"):
        (tmp_path / "spec.yaml").write_text(text)
        with pytest.raises(UnsafeSpecError):
            Env.standard(seed=1).load(tmp_path / "spec.yaml")
    import os

    assert "ABIO_PWNED" not in os.environ


def test_the_sandbox_lets_ordinary_work_through():
    assert _x("sum(range(1000))") == 499500
    assert _x("'ab' * 3") == "ababab"
    assert _x("2 ** 10") == 1024
    assert _x("max([3, 1, 2])") == 3 and _x("sorted([3, 1, 2], reverse=True)") == [3, 2, 1]
    assert _x("len(list(zip([1, 2], [3, 4])))") == 2
    assert _x("f'{n:03d}'", n=7) == "007"
