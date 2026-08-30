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
    "range": lambda *a: list(range(*a)),
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "sorted": sorted,
    "zip": lambda *a: [list(t) for t in zip(*a)],
    "all": all,
    "any": any,
    "reversed": lambda x: list(reversed(x)),
}.items():
    fn(_f, name=_name, kind="math", summary=_name)


# ---- op:* heads (what the inline parser emits for operators) --------------


def _op(name: str, f: Any) -> None:
    fn(f, name=f"op:{name}", kind="op", summary=f"operator {name}")


_op("add", lambda a, b: a + b)
_op("sub", lambda a, b: a - b)
_op("mul", lambda a, b: a * b)
_op("div", lambda a, b: a / b)
_op("floordiv", lambda a, b: a // b)
_op("mod", lambda a, b: a % b)
_op("pow", lambda a, b: a**b)
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
