"""The builtin heads (M47.1): distributions, math/conversion, and the ``op:*``
heads the inline parser emits. Importing this module registers them.

Distribution heads **draw** when evaluated (``!x lognormal(1, 0.3)`` is a
number); quote one to pass it unsampled (``!q lognormal(1, 0.3)`` is a
``Dist``). One builtin set serves the inline sandbox and the rate view.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from ..spec_lang import builtins as _b
from ..spec_lang.safe_eval import UnsafeExpressionError, _check_attr_name
from .env import Env, ExprError
from .registry import fn, guard

# ---- distributions ----------------------------------------------------------

for _name in ("normal", "uniform", "lognormal", "poisson", "exponential", "choice", "discrete"):
    fn(getattr(_b, _name), name=_name, kind="dist", summary=f"{_name} draw")


@fn(kind="dist", summary="always this value")
def constant(value: Any) -> Any:
    return value


# ---- math / conversion ------------------------------------------------------

for _name, _f in {
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "pow": pow,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "dict": dict,
    "all": all,
    "any": any,
}.items():
    fn(_f, name=_name, kind="math", summary=_name)


# ---- sized builtins: an untrusted expression must not allocate or iterate
# past ``ctx.limits.entities`` (M48.5 — range(10**9), list(range(...)),
# sum(range(10**9)) are refused before any work is done).


def _sized(x: Any, ctx: Any, what: str) -> Any:
    """Charge a sized iterable against the session's allocation meter."""
    if hasattr(x, "__len__") and not isinstance(x, (str, bytes)):
        try:
            n = len(x)
        except TypeError:
            return x
        ctx.limits.charge(n, ctx.path, what)
    return x


@fn(kind="math", name="range", summary="range")
def _range(*a: Any, ctx: Any) -> list[Any]:
    r = range(*a)
    return list(_sized(r, ctx, "range"))


@fn(kind="math", name="list", summary="list")
def _list(x: Any = (), *, ctx: Any) -> list[Any]:
    return list(_sized(x, ctx, "list"))


@fn(kind="math", name="sorted", summary="sorted")
def _sorted(x: Any, *, ctx: Any, key: Any = None, reverse: bool = False) -> list[Any]:
    return sorted(_sized(x, ctx, "sorted"), key=key, reverse=reverse)


@fn(kind="math", name="reversed", summary="reversed")
def _reversed(x: Any, *, ctx: Any) -> list[Any]:
    return list(reversed(_sized(x, ctx, "reversed")))


@fn(kind="math", name="zip", summary="zip")
def _zip(*a: Any, ctx: Any) -> list[list[Any]]:
    return [list(t) for t in zip(*(_sized(x, ctx, "zip") for x in a))]


@fn(kind="math", name="sum", summary="sum")
def _sum(x: Any, start: Any = 0, *, ctx: Any) -> Any:
    return sum(_sized(x, ctx, "sum"), start)


@fn(kind="math", name="max", summary="max")
def _max(*a: Any, ctx: Any, **kw: Any) -> Any:
    return max(*(_sized(x, ctx, "max") for x in a), **kw)


@fn(kind="math", name="min", summary="min")
def _min(*a: Any, ctx: Any, **kw: Any) -> Any:
    return min(*(_sized(x, ctx, "min") for x in a), **kw)


# ---- op:* heads (what the inline parser emits for operators) --------------


def _op(name: str, f: Any) -> None:
    fn(f, name=f"op:{name}", kind="op", summary=f"operator {name}")


_op("add", lambda a, b: a + b)
_op("sub", lambda a, b: a - b)
_op("div", lambda a, b: a / b)
_op("floordiv", lambda a, b: a // b)
_op("mod", lambda a, b: a % b)


#: The largest integer exponent an inline expression may raise to (M48.5:
#: ``10 ** 10 ** 10`` would otherwise hang the interpreter).
MAX_INT_EXPONENT = 10_000


@fn(kind="op", name="op:mul", summary="operator mul")
def _mul(a: Any, b: Any, *, ctx: Any) -> Any:
    for seq, n in ((a, b), (b, a)):
        if isinstance(seq, (str, bytes, list, tuple)) and isinstance(n, int) and not isinstance(n, bool):
            ctx.limits.charge(len(seq) * max(n, 0), ctx.path, "mul")
    return a * b


@fn(kind="op", name="op:pow", summary="operator pow")
def _pow(a: Any, b: Any, *, ctx: Any) -> Any:
    if isinstance(b, int) and not isinstance(b, bool) and abs(b) > MAX_INT_EXPONENT and not isinstance(a, bool) and a not in (0, 1, -1):
        raise ExprError(f"pow: exponent {b} exceeds {MAX_INT_EXPONENT}", ctx.path)
    try:
        return a**b
    except OverflowError as exc:
        raise ExprError(f"pow: {exc}", ctx.path) from None
_op("neg", lambda a: -a)
_op("pos", lambda a: +a)
_op("not", lambda a: not a)
_op("eq", lambda a, b: a == b)
_op("ne", lambda a, b: a != b)
_op("lt", lambda a, b: a < b)
_op("le", lambda a, b: a <= b)
_op("gt", lambda a, b: a > b)
_op("ge", lambda a, b: a >= b)
_op("in", lambda a, b: a in b)
_op("notin", lambda a, b: a not in b)
_op("is", lambda a, b: a is b)
_op("isnot", lambda a, b: a is not b)
_op("set", lambda xs: set(xs))
_op("flatten", lambda xss: [x for xs in xss for x in xs])
_op("slice", lambda lo=None, hi=None, step=None: slice(lo, hi, step))


def _item(obj: Any, index: Any, *, env: Env) -> Any:
    try:
        return obj[index]
    except (KeyError, IndexError, TypeError) as exc:
        raise env.error(f"subscript {index!r} on {type(obj).__name__}: {exc}") from None


def _attr(obj: Any, name: str, *, env: Env) -> Any:
    try:
        _check_attr_name(name)
    except UnsafeExpressionError as exc:
        raise env.error(str(exc)) from None
    if isinstance(obj, Mapping) and name in obj:
        return obj[name]
    if not hasattr(obj, name):
        raise env.error(f"no attribute {name!r} on {type(obj).__name__}")
    return getattr(obj, name)


def _method(obj: Any, name: str, *args: Any, env: Env, **kwargs: Any) -> Any:
    target = _attr(obj, name, env=env)
    if not callable(target):
        raise env.error(f"{name!r} on {type(obj).__name__} is not callable")
    return target(*args, **kwargs)


def _fstr(*parts: Any) -> str:
    return "".join(str(p) for p in parts)


def _fmt(value: Any, spec: str = "", conv: str = "") -> str:
    if conv == "r":
        value = repr(value)
    elif conv == "s":
        value = str(value)
    elif conv == "a":
        value = ascii(value)
    return format(value, spec) if spec else str(value)


_op("item", _item)
_op("attr", _attr)
_op("method", _method)
_op("fstr", _fstr)
_op("fmt", _fmt)


def flatten_iter(xs: Iterable[Iterable[Any]]) -> list[Any]:
    return [x for ys in xs for x in ys]


__all__ = ["constant", "flatten_iter", "ExprError"]


# ---------------------------------------------------------------------------
# guards (M47.5) — the two generic ones; domain guards register from Python
# ---------------------------------------------------------------------------


@guard(summary="the produced value is not empty")
def nonempty(value: Any, ctx: Any) -> bool:
    del ctx
    try:
        return len(value) > 0
    except TypeError:
        return value is not None


@guard(summary="the produced value has at most n elements")
def max_size(value: Any, ctx: Any, n: int = 1) -> bool:
    del ctx
    try:
        return len(value) <= int(n)
    except TypeError:
        return True
