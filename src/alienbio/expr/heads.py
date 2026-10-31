"""The builtin heads (M47.1): distributions, math/conversion, and the ``op:*``
heads the inline parser emits. Importing this module registers them.

Distribution heads **draw** when evaluated (``!x lognormal(1, 0.3)`` is a
number); quote one to pass it unsampled (``!q lognormal(1, 0.3)`` is a
``Dist``). One builtin set serves the inline sandbox and the rate view.

**Allocation charges.** Everything that can build a value proportional to an
argument is charged against ``Limits.charge`` (the per-session cumulative
meter, default cap 1M) BEFORE it is built, at the size it would produce:

=====================================  =========================================
call                                   charge
=====================================  =========================================
``range`` / ``list`` / ``sorted`` /    the iterable's length
``reversed`` / ``zip`` / ``max`` /
``min`` / ``sum``
``sum`` of lists                       total length of the rows
``a + b`` (sequences)                  ``len(a) + len(b)``
``seq * n`` (str/bytes/list/tuple)     ``len(seq) * n``
``a ** b`` / ``pow``                   refused past 10 000 exponent or 2^20 bits
``a * b`` (ints)                       refused past 2^20 result bits
``pow(a, b, m)``                       refused past bits(b) * bits(m) > 2^24
                                       or bits(m) > 2^20
``str(x)``                             the rendered size of ``x``
``fmt % args``                         ``len(fmt)`` + every width digit run +
                                       ``*`` widths + arg rendered size
                                       (x10 for %r/%a)
f-string / ``op:fmt``                  part rendered sizes; spec width digit
                                       runs
``op:flatten``                          total row length
text ``ljust/rjust/center/zfill``      ``max(len, width)``
text ``expandtabs(t)``                 ``len * max(8, t)``
text ``join(xs)``                      ``sum(len(x)) + len(sep) * len(xs)``
text ``replace(a, b)``                 ``len + (len+1) * max(len(a), len(b))``
text ``translate(table)``              ``len * longest table value``
text case mappings                     ``3 * len``
``str.encode``                         ``10 * len`` (``100 *`` with namereplace)
``bytes.decode``                       ``4 * len``
``bytes.hex(sep)``                     ``len * (2 + len(sep))``
``bytes.fromhex(s)`` / other text      ``len + len(text args)``
``int.to_bytes(n)``                    ``n``
other int / float / complex methods    0 (bounded scalar results)
container methods                      ``len(receiver) + len(sized args)``
=====================================  =========================================

Denied by name rather than charged: ``str.format`` / ``format_map`` (the
:mod:`spec_lang.safe_eval` name filter — a format field walks attributes
outside :mod:`.access`; use an f-string), the mutating methods, and the
``bytes`` / ``bytearray`` constructors (not heads).
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, Mapping

from ..spec_lang import builtins as _b
from ..spec_lang.safe_eval import UnsafeExpressionError
from . import access
from .env import Env, ExprError
from .registry import Head, fn, guard

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


# ---- rendered size: what ``str`` / an f-string / ``%`` will build -----------


def render_bound(value: Any, limit: int) -> int:
    """An upper estimate of ``len(str(value))``, computed WITHOUT building the
    text (T091 AL5: ``[[[0] * 1000] * 1000] * 100`` was charged 2 100 elements
    and rendered to 300 M characters). Every occurrence of a shared list is
    counted — that is what rendering repeats — and the walk stops as soon as
    the running total passes ``limit``, so it costs at most ``limit`` steps.
    A container on the current path is a cycle (Python prints ``[...]``).
    Per element: separators and brackets, a string's length + quotes, a
    bytes' escaped length, an int's digits, 32 for any other scalar; a
    dataclass is walked through its fields; any other object is measured by
    rendering it (its size was bounded where it was built)."""
    import dataclasses

    total = 0
    active: set[int] = set()
    stack: list[tuple[Any, bool]] = [(value, False)]
    while stack:
        x, leaving = stack.pop()
        if leaving:
            active.discard(id(x))
            continue
        t = type(x)
        if t in (list, tuple, set, frozenset, dict) or _is_dataclass_value(x):
            if id(x) in active:
                total += 5
                continue
            active.add(id(x))
            stack.append((x, True))
            if t is dict:
                items: Iterable[Any] = [v for kv in x.items() for v in kv]
            elif t in (list, tuple, set, frozenset):
                items = x
            else:
                items = [getattr(x, f.name, None) for f in dataclasses.fields(x)]
                total += len(t.__name__) + 2
            for item in items:
                total += 4  # separator, key colon / field name share
                if total > limit:
                    return total
                stack.append((item, False))
            total += 2
        elif t is str:
            total += len(x) + 2
        elif t in (bytes, bytearray):
            total += 4 * len(x) + 3
        elif t is int:
            total += x.bit_length() // 3 + 2
        elif t in (float, complex, bool, type(None)):
            total += 32
        else:
            total += len(str(x))
        if total > limit:
            return total
    return total


def _is_dataclass_value(x: Any) -> bool:
    import dataclasses

    return dataclasses.is_dataclass(x) and not isinstance(x, type)


def charge_render(value: Any, ctx: Any, what: str) -> None:
    """Charge what rendering ``value`` will build, before it is built (a
    ``str`` is its own length)."""
    if isinstance(value, (str, bytes, bytearray)):
        n = len(value)
    else:
        n = render_bound(value, ctx.limits.entities - ctx.limits.meter.allocated + 1)
    ctx.limits.charge(n, ctx.path, what)


@fn(kind="math", name="str", summary="str")
def _str(value: Any = "", *args: Any, ctx: Any) -> str:
    """``str(x)`` charged by its rendered size; ``str(b, encoding)`` decodes."""
    if args:
        ctx.limits.charge(4 * _sized_len(value), ctx.path, "str")
        return str(value, *args)
    charge_render(value, ctx, "str")
    return str(value)


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
#: T091 F6 / K: a ``%r`` / ``%a`` conversion in any spelling — the
#: ``%(key)a`` mapping form, flags/width/precision, and the ignored length
#: modifiers ``h`` / ``l`` / ``L`` (``%(k)la``, ``%ha``, ``%lr``), each of which
#: Python accepts and which escaped the charge before.
_REPR_CONVERSION = re.compile(r"%(?:\([^)]*\))?[^a-zA-Z%]*[hlL]?[ra]")


def _width_bound(spec: Any) -> int:
    """An upper bound on the padding a format string or spec can ask for:
    every digit run in it read as a width or precision (``'%050000000d'``,
    ``'.50000000f'``). Loose for literal digits, never short."""
    return sum(int(d) for d in _DIGITS.findall(spec)) if isinstance(spec, str) else 0


def _text_len(x: Any, ctx: Any = None) -> int:
    """The text ``x`` interpolates as, by :func:`render_bound` (never built)."""
    if isinstance(x, (str, bytes, bytearray)):
        return len(x)
    limit = ctx.limits.entities - ctx.limits.meter.allocated + 1 if ctx is not None else 10**7
    return render_bound(x, limit)


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
        # %r / %a write a repr: up to 10 characters per character of the
        # text ('\U0010ffff' under ascii) — charged at that bound (T091 C4).
        growth = 10 if _REPR_CONVERSION.search(fmt) else 1
        ctx.limits.charge(len(fmt) + _width_bound(fmt) + star + growth * sum(_text_len(x, ctx) for x in items), ctx.path, "mod")
    return a % b


#: The largest integer exponent an inline expression may raise to (M48.5:
#: ``10 ** 10 ** 10`` would otherwise hang the interpreter).
MAX_INT_EXPONENT = 10_000

#: The largest integer result (in bits) ``op:pow`` may build (T051 box 4: the
#: exponent cap alone did not bound the work — ``(10 ** 10000) ** 10000`` is
#: within it and is ~15 minutes of one core for a 332 M-bit integer).
#: T091 AL6: lowered from 2^24 — ``(10**1000)**4000`` (13 M bits) passed it
#: and took 15 s, and squaring THAT took 38 s. One 2^20-bit product is about
#: half a second; ``limits.seconds`` bounds a chain of them.
MAX_POW_RESULT_BITS = 1 << 20

#: ``pow(a, b, m)`` does ~bits(b) multiplications modulo ``m``:
#: bits(b) * bits(m) is capped here (T091 AL6 — a 13 M-bit exponent with a
#: 10 K-bit modulus ran past a minute).
MAX_MODPOW_WORK = 1 << 24


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


@fn(kind="op", name="op:mul", summary="operator mul")
def _mul(a: Any, b: Any, *, ctx: Any) -> Any:
    for seq, n in ((a, b), (b, a)):
        if isinstance(seq, (str, bytes, list, tuple)) and _is_int(n):
            ctx.limits.charge(len(seq) * max(n, 0), ctx.path, "mul")
    if _is_int(a) and _is_int(b):
        # T091 AL6: a big-int product is superlinear in its size — bounded by
        # result bits like `**`.
        bits = a.bit_length() + b.bit_length()
        if bits > MAX_POW_RESULT_BITS:
            raise ExprError(f"mul: result of ~{bits} bits exceeds {MAX_POW_RESULT_BITS}", ctx.path)
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
        if _is_int(b) and _is_int(mod):
            mod_bits = mod.bit_length()
            if mod_bits > MAX_POW_RESULT_BITS:
                raise ExprError(f"pow: modulus of {mod_bits} bits exceeds {MAX_POW_RESULT_BITS}", ctx.path)
            work = abs(b).bit_length() * mod_bits
            if work > MAX_MODPOW_WORK:
                raise ExprError(f"pow: exponent bits x modulus bits = {work} exceeds {MAX_MODPOW_WORK}", ctx.path)
        return pow(a, b, mod)
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
    """``obj.name``: a mapping key, else an attribute on a receiver type
    :mod:`.access` allows (T091 AG1 — the name filter alone let a spec walk
    ``quote(1).env.standard``)."""
    try:
        access.check_name(name)
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        return access.read_attr(obj, name)
    except UnsafeExpressionError as exc:
        raise env.error(str(exc)) from None
    except AttributeError:
        raise env.error(f"no attribute {name!r} on {type(obj).__name__}") from None


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
            return sum(_text_len(x) if isinstance(x, (str, bytes, bytearray)) else 0 for x in items) + n * len(items)
        if name == "replace":
            return n + (n + 1) * max([0] + texts)
        if name == "translate":
            return n * _translate_growth(args[0] if args else kwargs.get("table"))
        if name in _CASE_METHODS:
            # A case mapping can expand one character to three ('ﬃ'.upper()
            # is 'FFI'); charged at that bound (T091 C4).
            return 3 * n
        if name == "encode":
            # 'unicode_escape' writes up to 10 bytes per character
            # ('\U0010ffff'); the 'namereplace' handler writes a character's
            # whole Unicode name ('\N{...}', under 100 characters).
            return n * (100 if "namereplace" in values else 10)
        if name == "decode":
            return 4 * n  # 'backslashreplace' writes '\xff' for one byte
        if name == "hex":
            return n * (2 + sum(texts))  # each byte's two digits and a separator
        return n + sum(texts)
    if isinstance(obj, int) and not isinstance(obj, bool):
        if name == "to_bytes":
            # T091 AH: `(1).to_bytes(10**9, 'big')` built a gigabyte, charged 0.
            length = args[0] if args else kwargs.get("length", 1)
            return max(length, 0) if isinstance(length, int) else 0
        return 0  # every other int method returns a bounded scalar or the int itself
    if isinstance(obj, (float, complex, bool, type(None))):
        return 0
    # A container method returns at most the receiver plus its sized
    # arguments (`{1}.union(xs, ys)`, `{}.fromkeys(xs)`).
    sized = sum(len(v) for v in values if isinstance(v, (str, bytes, list, tuple, dict, set, frozenset)))
    return (len(obj) if hasattr(obj, "__len__") else 0) + sized


#: str methods whose result can be longer than the receiver by a case mapping.
_CASE_METHODS: frozenset[str] = frozenset({"upper", "lower", "casefold", "title", "swapcase", "capitalize"})


def _translate_growth(table: Any) -> int:
    """The most characters ``str.translate`` can write for one: the longest
    string (or bytes) value in the table, at least 1 (T091 C4: a mapping to
    a 300-character string multiplied the text by 300 per call and was
    charged only the receiver). A ``bytes`` table maps byte to byte."""
    if table is None or isinstance(table, (bytes, bytearray)):
        return 1
    if isinstance(table, Mapping):
        values: Iterable[Any] = table.values()
    elif isinstance(table, (list, tuple)):
        values = table  # indexed by ordinal
    else:
        raise ValueError(f"translate: the table must be a mapping or a list (got {type(table).__name__})")
    return max([1] + [len(v) for v in values if isinstance(v, (str, bytes, bytearray))])


def _method(obj: Any, name: str, *args: Any, env: Env, **kwargs: Any) -> Any:
    if name in _MUTATING_METHODS and isinstance(obj, (list, dict, set, bytearray)):
        raise env.error(
            f"{name!r} would change the {type(obj).__name__} in place, and Expr values are "
            "immutable (a binding is shared by every node naming it) — build a new value instead"
        )
    try:
        access.check_name(name)
        if isinstance(obj, Mapping) and name in obj:
            # a function held in a mapping (an included module's namespace)
            target = obj[name]
            if callable(target) and not isinstance(target, Head):
                access.check_callable(target, trusted=env.ctx.trusted)
        else:
            target = access.method(obj, name)
    except UnsafeExpressionError as exc:
        raise env.error(str(exc)) from None
    except AttributeError:
        raise env.error(f"no attribute {name!r} on {type(obj).__name__}") from None
    if not callable(target):
        raise env.error(f"{name!r} on {type(obj).__name__} is not callable")
    try:
        bound = _method_bound(obj, name, args, kwargs)
    except ValueError as exc:
        raise env.error(str(exc)) from None
    env.ctx.limits.charge(bound, env.path, f"method {name}")
    return target(*args, **kwargs)


def _fstr(*parts: Any, ctx: Any) -> str:
    # Charged before any part is rendered or joined (T088 heads 4; T091 AL5:
    # a non-text part is sized by `render_bound`, not by building it).
    ctx.limits.charge(sum(_text_len(p, ctx) for p in parts), ctx.path, "fstr")
    return "".join(p if isinstance(p, str) else str(p) for p in parts)


def _fmt(value: Any, spec: str = "", conv: str = "", *, ctx: Any) -> str:
    # T088 heads 2: a width in the spec (`f"{1:050000000d}"`) is charged
    # before the value is padded out to it (the text itself is charged by
    # `op:fstr` when the parts join).
    if spec:
        ctx.limits.charge(_width_bound(spec), ctx.path, "fmt")
    if not isinstance(value, (str, int, float, complex, bool, type(None))):
        # T091 AL5: a container renders here, before `op:fstr` sees text —
        # charged by its rendered size first (x10 under !r / !a).
        charge_render(value, ctx, "fmt")
        if conv in ("r", "a"):
            ctx.limits.charge(9 * _text_len(value, ctx), ctx.path, "fmt")
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
