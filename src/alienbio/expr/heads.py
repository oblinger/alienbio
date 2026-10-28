"""The builtin heads (M47.1): distributions, math/conversion, and the ``op:*``
heads the inline parser emits. Importing this module registers them.

Distribution heads **draw** when evaluated (``!x lognormal(1, 0.3)`` is a
number); quote one to pass it unsampled (``!q lognormal(1, 0.3)`` is a
``Dist``). One builtin set serves the inline sandbox and the rate view.
"""

from __future__ import annotations

import math
import re
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

# `min` / `max` / `sum` are NOT here: their metered versions below are the
# only registration (a second registration of a name refuses since T054 #6).
for _name, _f in {
    "abs": abs,
    "round": round,
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


def _sized_len(x: Any) -> int:
    return len(x) if isinstance(x, (str, bytes, list, tuple)) else 0


@fn(kind="math", name="sum", summary="sum")
def _sum(x: Any, start: Any = 0, *, ctx: Any) -> Any:
    # T051 box 4 — a sum of LISTS (``sum([[0] * 10**5] * 10**4, [])``) is
    # sized by its output, and Python builds it quadratically, so the charge
    # must land BEFORE the work: ten thousand 100k-element rows is 10^9
    # elements and minutes of one core under a cap that saw only 10^4.
    if isinstance(x, (list, tuple)):
        total = sum(_sized_len(item) for item in x)
        if total:
            ctx.limits.charge(total, ctx.path, "sum")
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


@fn(kind="op", name="op:add", summary="operator add")
def _add(a: Any, b: Any, *, ctx: Any) -> Any:
    # T051 box 4 — ``add`` was the one sized operator that charged nothing:
    # fifteen lazy bindings doubling a 1000-element list produced 16.4M
    # elements (250 MB) under a 10k cap; thirty would have been the machine.
    n = _sized_len(a) + _sized_len(b)
    if n:
        ctx.limits.charge(n, ctx.path, "add")
    return a + b


_op("sub", lambda a, b: a - b)
_op("div", lambda a, b: a / b)
_op("floordiv", lambda a, b: a // b)


_DIGITS = re.compile(r"\d+")


def _width_bound(spec: Any) -> int:
    """An upper bound on the padding a format string or spec can ask for:
    every digit run in it read as a width or precision (``'%050000000d'``,
    ``'.50000000f'``). Loose for literal digits, never short."""
    return sum(int(d) for d in _DIGITS.findall(spec)) if isinstance(spec, str) else 0


def _text_len(x: Any) -> int:
    return len(x) if isinstance(x, (str, bytes, bytearray)) else len(str(x))


@fn(kind="op", name="op:mod", summary="operator mod")
def _mod(a: Any, b: Any, *, ctx: Any) -> Any:
    # T088 heads 2: `'%050000000d' % 1` built 50M characters under a 1M cap.
    # A %-format is charged its bound BEFORE it is built: the format's own
    # length, every width/precision in it, a `*` width's argument, and the
    # text of every argument it interpolates.
    if isinstance(a, (str, bytes)):
        fmt = a if isinstance(a, str) else a.decode("latin-1")
        items = list(b.values()) if isinstance(b, Mapping) else list(b) if isinstance(b, tuple) else [b]
        star = sum(max(x, 0) for x in items if isinstance(x, int) and not isinstance(x, bool)) if "*" in fmt else 0
        ctx.limits.charge(len(fmt) + _width_bound(fmt) + star + sum(_text_len(x) for x in items), ctx.path, "mod")
    return a % b


#: The largest integer exponent an inline expression may raise to (M48.5:
#: ``10 ** 10 ** 10`` would otherwise hang the interpreter).
MAX_INT_EXPONENT = 10_000

#: The largest integer result (in bits) ``op:pow`` may build (T051 box 4: the
#: exponent cap alone did not bound the work — ``(10 ** 10000) ** 10000`` is
#: within it and is ~15 minutes of one core for a 332 M-bit integer).
MAX_POW_RESULT_BITS = 1 << 24


@fn(kind="op", name="op:mul", summary="operator mul")
def _mul(a: Any, b: Any, *, ctx: Any) -> Any:
    for seq, n in ((a, b), (b, a)):
        if isinstance(seq, (str, bytes, list, tuple)) and isinstance(n, int) and not isinstance(n, bool):
            ctx.limits.charge(len(seq) * max(n, 0), ctx.path, "mul")
    return a * b


@fn(kind="op", name="op:pow", summary="operator pow")
def _pow(a: Any, b: Any, *, ctx: Any) -> Any:
    """``a ** b`` with the exponent and result-size caps; ``pow`` by name is
    the same function (T088 heads 1: the builtin under ``pow`` skipped both)."""
    if isinstance(b, int) and not isinstance(b, bool) and abs(b) > MAX_INT_EXPONENT and not isinstance(a, bool) and a not in (0, 1, -1):
        raise ExprError(f"pow: exponent {b} exceeds {MAX_INT_EXPONENT}", ctx.path)
    if isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool) and not isinstance(b, bool) and b > 0:
        bits = a.bit_length() * b
        if bits > MAX_POW_RESULT_BITS:
            raise ExprError(f"pow: result of ~{bits} bits exceeds {MAX_POW_RESULT_BITS}", ctx.path)
    try:
        return a**b
    except OverflowError as exc:
        raise ExprError(f"pow: {exc}", ctx.path) from None


@fn(kind="math", name="pow", summary="pow")
def _pow_named(a: Any, b: Any, mod: Any = None, *, ctx: Any) -> Any:
    if mod is not None:
        return pow(a, b, mod)  # bounded by mod's size; Python refuses a negative int exponent without one
    return _pow(a, b, ctx=ctx)


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
@fn(kind="op", name="op:flatten", summary="operator flatten")
def _flatten(xss: Any, *, ctx: Any) -> list:
    rows = list(xss)
    # T088 heads 4: charged before the result is built (sized rows only;
    # an unsized row is charged by its count once materialized).
    ctx.limits.charge(sum(len(xs) for xs in rows if hasattr(xs, "__len__")), ctx.path, "flatten")
    out = [x for xs in rows for x in xs]
    unsized = sum(1 for xs in rows if not hasattr(xs, "__len__"))
    if unsized:
        ctx.limits.charge(len(out) - sum(len(xs) for xs in rows if hasattr(xs, "__len__")), ctx.path, "flatten")
    return out


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


#: Methods that change their receiver in place (T088 heads 3: ``b: !x
#: a.clear()`` emptied the mapping bound at ``a`` for every later reader, and
#: a lazily cached binding is shared by every node naming it). Expr values
#: are immutable; these refuse — build a new value (``xs + [x]``, ``{**d}``
#: is not inline, so a mapping update is a new literal or a registered fn).
_MUTATING_METHODS: frozenset[str] = frozenset({
    "append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse",
    "update", "setdefault", "popitem", "add", "discard",
    "difference_update", "intersection_update", "symmetric_difference_update",
})

#: str/bytes methods whose result is padded out to an integer argument.
_PADDING_METHODS: frozenset[str] = frozenset({"ljust", "rjust", "center", "zfill"})


def _method_bound(obj: Any, name: str, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> int:
    """An upper bound on what a method call can build, charged before it runs
    (T088 heads 2: ``'a'.ljust(50000000)`` built 50M characters under a 1M
    cap). Text receivers are bounded per method family; a container's
    methods return at most a copy of it."""
    values = list(args) + list(kwargs.values())
    if isinstance(obj, (str, bytes, bytearray)):
        n = len(obj)
        ints = [v for v in values if isinstance(v, int) and not isinstance(v, bool)]
        texts = [len(v) for v in values if isinstance(v, (str, bytes, bytearray))]
        if name in _PADDING_METHODS:
            return max([n] + ints)
        if name == "expandtabs":
            return n * max([8] + ints)
        if name == "join":
            items = args[0] if args and hasattr(args[0], "__len__") else ()
            return sum(_text_len(x) for x in items) + n * len(items)
        if name == "replace":
            return n + (n + 1) * max([0] + texts)
        return n + sum(texts)
    return len(obj) if hasattr(obj, "__len__") else 0


def _method(obj: Any, name: str, *args: Any, env: Env, **kwargs: Any) -> Any:
    if name in _MUTATING_METHODS and isinstance(obj, (list, dict, set, bytearray)):
        raise env.error(
            f"{name!r} would change the {type(obj).__name__} in place, and Expr values are "
            "immutable (a binding is shared by every node naming it) — build a new value instead"
        )
    target = _attr(obj, name, env=env)
    if not callable(target):
        raise env.error(f"{name!r} on {type(obj).__name__} is not callable")
    env.ctx.limits.charge(_method_bound(obj, name, args, kwargs), env.path, f"method {name}")
    return target(*args, **kwargs)


def _fstr(*parts: Any, ctx: Any) -> str:
    texts = [p if isinstance(p, str) else str(p) for p in parts]
    ctx.limits.charge(sum(len(t) for t in texts), ctx.path, "fstr")  # before the join (T088 heads 4)
    return "".join(texts)


def _fmt(value: Any, spec: str = "", conv: str = "", *, ctx: Any) -> str:
    # T088 heads 2: a width in the spec (`f"{1:050000000d}"`) is charged
    # before the value is padded out to it (the text itself is charged by
    # `op:fstr` when the parts join).
    if spec:
        ctx.limits.charge(_width_bound(spec), ctx.path, "fmt")
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
fn(_fstr, name="op:fstr", kind="op", summary="operator fstr")
fn(_fmt, name="op:fmt", kind="op", summary="operator fmt")


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
