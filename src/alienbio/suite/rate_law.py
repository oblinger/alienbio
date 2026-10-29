"""Rate laws — the compiled tier of Expr (M47.3).

A ``rate:`` slot is **not** run by the interpreter. It is a number / ``Dist``
(the mass-action constant ``k``) or a quoted form in the **rate grammar**,
compiled once here into a :class:`RateLaw` the engine evaluates every step.

Two shapes compile (M47.10). The **product form** — mass action over the
reactants (implicit) times a product of **modulations** by non-consumed
modifier pools, the four ``Modulation`` kinds ``bio/reaction.py`` implements:

    k
    k * hill(M, K, n=2)
    k * michaelis(M, K) * inhibitor(I, Ki)

compiles to ``RateLaw(k, modulations)`` and realises as a ``ReactionImpl``
with ``Modulation`` modifiers (the M47.3 path; unchanged). Anything else the
**rate grammar** admits — a sum, a quotient, ``exp`` / ``log`` / ``sqrt``,
substrate-saturation kinetics written over a *reactant* (``Vmax * S / (Km +
S)``), several modulations mixed with algebra — compiles to a
:mod:`~alienbio.bio.rate_expr` tree (``RateLaw.expr``) that both simulators
evaluate: the whole rate when the law names a reactant, else the factor on
mass action. A law that names a reactant or product pool as a factor is
never the product form (T091 E4: ``0.2 * A`` over ``A + B`` read as
``0.2·A·B`` while ``0.2 * A + 0.0`` read as ``0.2·A``) — it takes the
expression path, so ``0.2 * A`` and ``0.2 * A + 0.0`` are one number. ``k``
and every parameter may be a number, a bound constant, a bound ``Dist`` or a
distribution call (drawn once, at world build). A bare name that is not
bound in scope is a **pool** (a quoted string always is). What is refused,
at load with the node path: a head outside the rate view (a world-building
head, a Python-only function), a bool, a product of two distributions, and
a constant factor that can be negative, and a math or distribution call over
a distribution still to be drawn (``max(k, 0.05)`` with ``k: !q normal(...)``;
draw inside the call or bind with ``!x``, T092).

**A rate law's constant factor is non-negative by construction** (T091 E9,
I1–I3). The rate-constant positions are the whole law when it reads no pool,
and each factor of its top-level product chain (multiplicands and divisors,
through unary minus) that reads no pool. Each such factor is folded at
compile — constant arithmetic (``k - 1`` with ``k = 0.5``, ``0.2 / -1``,
``exp(-1)``), bound numbers, bound and quoted distributions — to the interval
it can take *on any seed*: a number is a point, a distribution its support
(``normal`` the whole line, ``uniform(lo, hi)`` ``[lo, hi]``, ``lognormal`` /
``poisson`` / ``exponential`` ``[0, ∞)``, :func:`~alienbio.suite.dist.support_of`
for a ``Dist`` object; a name bound to a draw with ``!x`` — drawn at load,
outside the law — by its binding's form, so ``k: !x normal(0.3, 0.3)`` gets
the inline draw's verdict, T092). The fold reads numbers, ``+ - * /`` and
unary minus, ``**`` / ``pow``, ``exp`` / ``log`` / ``sqrt`` / ``abs``, ``min`` /
``max``, ``round`` / ``float`` / ``int`` (the bounds mapped), ``sum([...])``
(the bounds added), one name times itself (a square) and ``a if c else b``
(the union of the branches, the condition otherwise ignored — but a branch
that IS the compared name is bounded by the comparison, so the clip idiom
``base if base > 0 else 0.01`` loads); any other head over a draw folds to
the whole line, and its refusal names this list (:data:`FOLDED_FORMS`). A
factor whose interval straddles zero, or a product
whose signs (unary minus included) come out negative, refuses at LOAD,
naming the node and the support — so the verdict never depends on the seed
a world is drafted at, and ``--dry`` agrees with every trial. A sub-expression
that reads a pool is not a constant: a law whose *value* goes negative
because of state (``0.2 * (5 - A)`` at ``A > 5``) loads, and both simulators
read a negative rate as 0. The rule's consequence is an asymmetry between
two algebraically equal spellings: ``-0.2 * (A - 5)`` refuses (its constant
factor ``-0.2`` is negative) while ``0.2 * (5 - A)`` loads (its constant
factor ``0.2`` is not; the sign lives in a state-dependent term). Terms of
a sum are not rate-constant positions, so ``5 - A`` and ``0.2 * (5 - A)``
get the same verdict.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from ..bio import rate_expr as rx
from ..bio.reaction import Modulation
from ..expr.env import Env, ExprError, Lazy
from ..expr.form import Call, Name, Quoted
from ..expr.interp import QuotedForm, evaluate
from ..expr.registry import fn
from .dist import Constant, Dist, Seed, support_of

#: The modulation heads: kind -> (positional parameter names after the pool, keyword-only extras)
MODULATION_HEADS: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "hill": (("K",), ("n", "Vmax")),
    "michaelis": (("K",), ("Vmax",)),
    "activator": (("a",), ()),
    "inhibitor": (("Ki",), ()),
}

_MODULATION_DEFAULTS: Mapping[str, Mapping[str, float]] = {
    "hill": {"n": 2.0, "Vmax": 1.0},
    "michaelis": {"Vmax": 1.0},
    "activator": {},
    "inhibitor": {},
}


# ---- the rate heads, as real functions (so `!x hill(0.5, 0.5, n=2)` is a number too)


# Each numeric head IS ``rate_expr.modulation_factor`` — the arithmetic the
# compiled law runs on both simulators, zero-denominator conventions
# included — so `!x inhibitor(1, 0)` reads as the engine does (T088 rate_law
# 5: it raised a bare ZeroDivisionError where hill/michaelis returned 0).


@fn(kind="rate", summary="Hill response of a modifier: Vmax * m**n / (K**n + m**n)")
def hill(m: float, K: float, n: float = 2.0, Vmax: float = 1.0) -> float:
    return rx.modulation_factor("hill", m, {"K": K, "n": n, "Vmax": Vmax})


@fn(kind="rate", summary="Michaelis-Menten response of a modifier: Vmax * m / (K + m)")
def michaelis(m: float, K: float, Vmax: float = 1.0) -> float:
    return rx.modulation_factor("michaelis", m, {"K": K, "Vmax": Vmax})


@fn(kind="rate", summary="linear activation: 1 + a * m")
def activator(m: float, a: float) -> float:
    return rx.modulation_factor("activator", m, {"a": a})


@fn(kind="rate", summary="linear inhibition: 1 / (1 + m / Ki)")
def inhibitor(m: float, Ki: float) -> float:
    return rx.modulation_factor("inhibitor", m, {"Ki": Ki})


# ---- the compiled record ----------------------------------------------------


@dataclass(frozen=True)
class ModulationSpec:
    """One modulation term: the modifier pool, the kind, its parameter Dists."""

    pool: str
    kind: str
    params: Mapping[str, Dist[float]] = field(default_factory=dict)

    def sample(self, seed: Seed) -> Modulation:
        values = {name: float(dist.sample(seed.child(name))) for name, dist in self.params.items()}
        return Modulation(kind=self.kind, **values)


@dataclass(frozen=True)
class RateLaw:
    """A compiled rate law: ``k`` (a Dist) times zero or more modulations —
    or, when ``expr`` is set, a compiled rate expression (``bio.rate_expr``
    tree over pool names, with ``("dist", Dist)`` leaves still to draw)."""

    k: Dist[float]
    modulations: tuple[ModulationSpec, ...] = ()
    expr: Optional[Any] = None

    @property
    def modifier_pools(self) -> tuple[str, ...]:
        return tuple(m.pool for m in self.modulations)

    @property
    def expr_pools(self) -> tuple[str, ...]:
        """Every pool the expression reads (empty for the product form)."""
        return tuple(sorted(rx.species_of(self.expr))) if self.expr is not None else ()

    def realize_expr(self, seed: Seed) -> Any:
        """The expression with every ``Dist`` leaf and parameter drawn under
        ``seed`` — the tree a ``ReactionImpl`` carries. Draws are numbered in
        walk order (``law1``, ``law2`` …): the tree has no names to seed by,
        so inserting a term ahead of a draw re-seeds it (any positional
        scheme would shift too); a reaction's own seed is per path."""
        counter = [0]

        def draw(dist: Dist[float]) -> float:
            counter[0] += 1
            return float(dist.sample(seed.child(f"law{counter[0]}")))

        def walk(node: Any) -> Any:
            tag = node[0]
            if tag == "dist":
                return rx.const(draw(node[1]))
            if tag == "mod":
                params = {k: (draw(v) if isinstance(v, Dist) else float(v)) for k, v in node[3].items()}
                return rx.modulation(node[1], node[2], params)
            if tag in ("neg", "exp", "log", "sqrt"):
                return (tag, walk(node[1]))
            if tag in ("add", "sub", "mul", "div", "pow"):
                return (tag, walk(node[1]), walk(node[2]))
            return node

        return walk(self.expr)


RATE_VIEW_KINDS: frozenset[str] = frozenset({"rate", "math", "op", "dist"})


class _Scaled:
    """A Dist scaled by a constant factor (``2 * k`` where ``k`` is a Dist)."""

    def __init__(self, base: Dist[float], factor: float) -> None:
        self.base = base
        self.factor = factor

    def sample(self, seed: Seed) -> float:
        return float(self.base.sample(seed)) * self.factor

    def support(self) -> Optional[tuple[float, float]]:
        base = support_of(self.base)
        if base is None:
            return None
        return _interval_mul(base, (self.factor, self.factor))

    def __repr__(self) -> str:
        return f"_Scaled({self.base!r} * {self.factor})"


def _flatten_product(form: Any) -> list[Any]:
    if isinstance(form, Call) and form.head == "op:mul" and len(form.args) == 2 and not form.kwargs:
        return _flatten_product(form.args[0]) + _flatten_product(form.args[1])
    return [form]


class _NotProductForm(ExprError):
    """The law is not the product form; the expression grammar may still
    take it. Typed, so the fallback no longer matches the message text
    (T088 rate_law 3)."""


def _refuse(env: Env, what: str) -> ExprError:
    return _NotProductForm(
        f"rate law: {what} is outside the engine's compilable subset "
        "(mass action × modulations by non-consumed pools) — M47.10",
        env.ctx.path,
    )


def _constant(form: Any, env: Env, what: str) -> Dist[float]:
    """A constant factor: a literal, a bound number, or a bound Dist."""
    if isinstance(form, bool):
        raise _refuse(env, f"{what} (a bool)")
    if isinstance(form, (int, float)):
        return Constant(float(form))
    if isinstance(form, Name):
        try:
            value = env.lookup(form.path)
        except ExprError:
            # an unbound name in a rate law is a pool — a species factor is
            # not a constant, so the expression grammar takes the law
            raise _refuse(env, f"{what} ({form.path!r} names a pool, not a constant)") from None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return Constant(float(value))
        if isinstance(value, Dist):
            return value
        raise _refuse(env, f"{what} ({form.path!r} is bound to a {type(value).__name__})")
    if isinstance(form, Quoted):
        return QuotedForm(form.form, env)
    if isinstance(form, Call) and form.head in ("op:neg",):
        inner = _constant(form.args[0], env, what)
        # folded, so the sign check sees `-(-0.2)` as the 0.2 it is
        if isinstance(inner, Constant):
            return Constant(-float(inner.value))
        if isinstance(inner, _Scaled):
            return _Scaled(inner.base, -inner.factor)
        return _Scaled(inner, -1.0)
    if isinstance(form, Call) and form.head in ("op:mul",) and len(form.args) == 2:
        a, b = (_constant(x, env, what) for x in form.args)
        return _scale(a, b, env, what)
    if isinstance(form, Call):
        head = env.head(form.head)
        if head.kind in ("dist", "math"):
            if _quoted_draw(form, env) is not None:
                # not a product-form constant; the expression path carries a
                # draw through ``exp`` / ``log`` / ``sqrt`` and refuses the rest by name
                raise _refuse(env, f"{what} ({form.head}(...) over an unevaluated quoted form)")
            try:
                value = evaluate(form, env)
            except ExprError as exc:
                # a factor that reads a species (``exp(M)``) is not a constant —
                # the expression compiler's business
                raise _refuse(env, f"{what} ({exc.message})") from None
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return Constant(float(value))
            if isinstance(value, Dist):
                return value
    raise _refuse(env, what)


def _scale(a: Dist[float], b: Dist[float], env: Env, what: str) -> Dist[float]:
    if isinstance(a, Constant) and isinstance(b, Constant):
        return Constant(float(a.value) * float(b.value))
    if isinstance(a, Constant):
        return _Scaled(b, float(a.value))
    if isinstance(b, Constant):
        return _Scaled(a, float(b.value))
    # A hard refusal, not a product-form miss: the expression path would
    # otherwise take the law and multiply the two draws (T091 E9).
    raise env.error(f"rate law: {what} is a product of two distributions ({a!r} * {b!r}); draw one")


def _quoted_draw(form: Any, env: Env) -> Optional[Any]:
    """The first sub-form of ``form`` that evaluates to an UNDRAWN distribution
    — a quote, or a name bound to a quoted form or a ``Dist`` — else ``None``."""
    if isinstance(form, Quoted):
        return form
    if isinstance(form, Name):
        try:
            value = env.lookup(form.path)
        except ExprError:
            return None
        return form if isinstance(value, (QuotedForm, Dist)) and not isinstance(value, (int, float)) else None
    if isinstance(form, (list, tuple)):
        return next((hit for hit in (_quoted_draw(x, env) for x in form) if hit is not None), None)
    if isinstance(form, Call):
        parts = list(form.args) + list(form.kwargs.values())
        return next((hit for hit in (_quoted_draw(x, env) for x in parts) if hit is not None), None)
    return None


def _quoted_constant(hit: Any, env: Env) -> bool:
    """Whether a :func:`_quoted_draw` hit is a quoted form that draws nothing
    (``k: !q 0.3``): its fold is a single point."""
    if isinstance(hit, Name):
        try:
            value = env.lookup(hit.path)
        except ExprError:
            return False
        if not isinstance(value, QuotedForm):
            return False
        return _point(_interval(value.form, value.env)) is not None
    if isinstance(hit, Quoted):
        return _point(_interval(hit.form, env)) is not None
    return False


def _refuse_quoted_draw_argument(form: Call, env: Env) -> None:
    """Refuse a math or distribution call over an undrawn distribution (T092):
    ``max(k, 0.05)`` with ``k: !q normal(0.3, 0.3)`` reached ``max`` with a
    ``QuotedForm`` and died at world build as ``'>' not supported between
    instances of 'float' and 'QuotedForm'``. Only the four arithmetic
    operators, ``exp`` / ``log`` / ``sqrt`` and the modulations carry a draw
    through a rate law; a call takes numbers."""
    hit = _quoted_draw(form, env)
    if hit is None:
        return
    if _quoted_constant(hit, env):
        raise env.error(
            f"rate law: {form.head}(...) takes {_describe(hit, env)}, a quoted constant — a quoted form is not "
            f"evaluated before the call; bind it with !x or write the number inline (refused at load, on every seed)"
        )
    raise env.error(
        f"rate law: {form.head}(...) takes {_describe(hit, env)}, a distribution still to be drawn — "
        f"a {form.head}(...) call in a rate law takes numbers; draw inside the call "
        f"({form.head}(normal(...), ...)) or bind the name with !x (refused at load, on every seed)"
    )


def _negative_constant(env: Env, value: float) -> ExprError:
    return env.error(f"rate law: negative rate constant {value:g} — a rate is never negative (it ran as rate 0)")


# ---- the sign rule: a constant factor is non-negative on every seed (T091 I1–I3)

Interval = tuple[float, float]
_LINE: Interval = (-math.inf, math.inf)
_HALF: Interval = (0.0, math.inf)


def _interval_mul(a: Interval, b: Interval) -> Interval:
    products = [x * y for x in a for y in b if not ((x == 0.0 and math.isinf(y)) or (y == 0.0 and math.isinf(x)))]
    if not products:
        return (0.0, 0.0)
    return (min(products), max(products))


def _interval_div(a: Interval, b: Interval) -> Interval:
    lo, hi = b
    if lo <= 0.0 <= hi:
        return _LINE
    return _interval_mul(a, (1.0 / hi, 1.0 / lo))


def _point(iv: Optional[Interval]) -> Optional[float]:
    return iv[0] if iv is not None and iv[0] == iv[1] else None


#: The distribution heads :func:`_dist_head_support` knows the support of;
#: any other ``dist`` head in a rate-constant position refuses at load.
SUPPORTED_DIST_HEADS = ("normal", "uniform", "lognormal", "poisson", "exponential", "discrete", "choice", "constant")


def _dist_head_support(
    head: str, args: Sequence[Interval], kwargs: Mapping[str, Interval], env: Env
) -> Interval:
    """The support of a distribution head called with these argument intervals.

    Covered heads (:data:`SUPPORTED_DIST_HEADS`): ``normal`` the whole line;
    ``uniform(lo, hi)`` (positional or ``low=`` / ``high=``) the hull of its
    bounds' intervals; ``lognormal`` / ``poisson`` / ``exponential`` /
    ``discrete`` ``[0, ∞)``; ``choice([...])`` the min and max over its
    members (a mixed-sign list straddles zero, so the sign rule refuses it);
    ``constant(x)`` the interval of ``x``. Any other distribution head
    refuses as unsupported for a support check — never the whole line by
    default, which refused an all-positive law with a misleading support
    (T091 M3)."""
    if head == "normal":
        return _LINE
    if head == "uniform":
        bounds = list(args) + [kwargs[k] for k in ("low", "high") if k in kwargs]
        if len(bounds) == 2:
            return (min(bounds[0][0], bounds[1][0]), max(bounds[0][1], bounds[1][1]))
    if head in ("lognormal", "poisson", "exponential", "discrete"):
        return _HALF
    if head == "choice":
        members = list(args) + ([kwargs["options"]] if "options" in kwargs else [])
        if len(members) == 1:
            return members[0]  # a list's interval is already its members' min / max
    if head == "constant" and len(args) == 1:
        return args[0]
    raise env.error(
        f"rate law: the distribution {head}(...) is unsupported for a support check — a rate constant "
        f"drawn in a rate law must use one of {', '.join(SUPPORTED_DIST_HEADS)} (refused at load, on every seed)"
    )


def _interval_pow(base: Interval, exp: Interval) -> Interval:
    """``base ** exp`` over intervals, for a point exponent (else the half-line
    over a non-negative base, the whole line otherwise)."""
    e = _point(exp)
    lo, hi = base

    def p(x: float) -> float:
        try:
            return math.pow(x, e)  # type: ignore[arg-type]
        except OverflowError:
            return math.inf
        except (ValueError, ZeroDivisionError):
            return math.inf

    if e is None:
        return _HALF if lo >= 0.0 else _LINE
    if lo >= 0.0:
        if e >= 0.0:
            return (p(lo), p(hi))
        return (p(hi), math.inf if lo == 0.0 else p(lo))
    if e.is_integer() and e > 0.0:
        if int(e) % 2 == 0:
            mag = max(abs(lo), abs(hi))
            low = 0.0 if lo <= 0.0 <= hi else min(p(lo), p(hi))
            return (low, p(mag) if mag < math.inf else math.inf)
        return (p(lo), p(hi))  # an odd power is monotone
    return _LINE


def _interval(form: Any, env: Env) -> Optional[Interval]:
    """The interval a pool-free form can take on any seed; ``None`` when it
    reads a pool (not a constant). An unknown constant is the whole line."""
    if isinstance(form, bool):
        return None
    if isinstance(form, (int, float)):
        return (float(form), float(form))
    if isinstance(form, str):
        return None
    if isinstance(form, Name):
        try:
            value = env.lookup(form.path)
        except ExprError:
            return None
        drawn = _drawn_binding(form, env)
        if drawn is not None:
            folded = _interval(*drawn)
            if folded is not None:
                return folded
        return _value_interval(value)
    if isinstance(form, Quoted):
        return _interval(form.form, env)
    if isinstance(form, list):
        parts = [_interval(x, env) for x in form]
        if any(p is None for p in parts) or not parts:
            return None
        return (min(p[0] for p in parts if p), max(p[1] for p in parts if p))
    if not isinstance(form, Call):
        return None
    if form.head in MODULATION_HEADS:
        return None
    if form.head == "if" and not form.args:
        return _if_interval(form, env)
    call_args: list[Any] = list(form.args)
    if form.head == "sum" and call_args and isinstance(call_args[0], list) and len(call_args) <= 2 and not form.kwargs:
        terms = [_interval(x, env) for x in [*call_args[0], *call_args[1:]]]
        if any(t is None for t in terms):
            return None
        return (sum(t[0] for t in terms if t), sum(t[1] for t in terms if t))
    args = [_interval(a, env) for a in form.args]
    kwargs = {k: _interval(v, env) for k, v in form.kwargs.items()}
    if any(a is None for a in args) or any(v is None for v in kwargs.values()):
        return None
    ivs: list[Interval] = [a for a in args if a is not None]
    if form.head == "op:neg" and len(ivs) == 1:
        return (-ivs[0][1], -ivs[0][0])
    if form.head in ("op:add", "op:sub", "op:mul", "op:div") and len(ivs) == 2:
        a, b = ivs
        if form.head == "op:add":
            return (a[0] + b[0], a[1] + b[1])
        if form.head == "op:sub":
            return (a[0] - b[1], a[1] - b[0])
        if form.head == "op:mul":
            if isinstance(call_args[0], Name) and call_args[0] == call_args[1]:
                # one name read twice is one value: ``n * n`` is a square
                return _interval_pow(a, (2.0, 2.0))
            return _interval_mul(a, b)
        return _interval_div(a, b)
    if form.head in ("op:pow", "pow") and len(ivs) == 2 and not kwargs:
        if _point(ivs[0]) is not None and _point(ivs[1]) is not None:
            return _evaluated(form, env)
        return _interval_pow(ivs[0], ivs[1])
    if form.head == "log" and len(ivs) == 1 and not kwargs and ivs[0][0] >= 0.0:
        lo, hi = ivs[0]
        return (math.log(lo) if lo > 0.0 else -math.inf, math.log(hi) if hi < math.inf else math.inf)
    if form.head in ("min", "max") and ivs and not kwargs:
        members = ivs
        if len(form.args) == 1 and isinstance(form.args[0], list):
            members = [iv for iv in (_interval(x, env) for x in form.args[0]) if iv is not None]
        pick = min if form.head == "min" else max
        return (pick(m[0] for m in members), pick(m[1] for m in members))
    if form.head in ("round", "float", "int") and ivs and len(ivs) <= 2 and not kwargs:
        return _rounded(form.head, ivs)
    if form.head in ("exp", "sqrt", "abs"):
        if len(ivs) == 1 and form.head == "exp":
            return (math.exp(ivs[0][0]) if ivs[0][0] > -math.inf else 0.0, math.exp(ivs[0][1]) if ivs[0][1] < math.inf else math.inf)
        return _HALF
    if form.head.startswith("op:"):
        return _LINE
    try:
        kind = env.head(form.head).kind
    except ExprError:
        return None  # an unknown head refuses in the compiler, naming the node
    if kind == "dist":
        return _dist_head_support(form.head, ivs, {k: v for k, v in kwargs.items() if v is not None}, env)
    if all(_point(iv) is not None for iv in ivs) and all(_point(v) is not None for v in kwargs.values()):
        return _evaluated(form, env)
    return _LINE


#: What the sign fold reads exactly; any other head over a non-point argument
#: folds to the whole line, and its refusal names this list.
FOLDED_FORMS = (
    "numbers, + - * / ** and unary -, pow, exp, log, sqrt, abs, min, max, round, float, int, "
    "sum([...]), `a if c else b`, and the draws " + ", ".join(SUPPORTED_DIST_HEADS)
)
_FOLDED_HEADS = frozenset(
    {"op:neg", "op:add", "op:sub", "op:mul", "op:div", "op:pow", "pow", "exp", "log", "sqrt", "abs",
     "min", "max", "round", "float", "int", "sum", "if"}
)

_NARROW = {"op:gt": "up", "op:ge": "up", "op:lt": "down", "op:le": "down"}
_FLIP = {"up": "down", "down": "up"}


def _branch_bound(cond: Any, branch: Any, taken: bool, env: Env) -> Optional[Interval]:
    """The bound a comparison puts on a branch that IS the compared name:
    ``x if x > c else e`` takes ``x`` only where ``x >= c`` (the clip idiom,
    ``base if base > 0 else 0.01``), and ``e`` only where ``x <= c`` when ``e``
    is ``x``. A name only — two inline draws are two values, never narrowed."""
    if not (isinstance(cond, Call) and cond.head in _NARROW and len(cond.args) == 2 and not cond.kwargs):
        return None
    if not isinstance(branch, Name):
        return None
    left, right = cond.args
    direction = _NARROW[cond.head]
    if left == branch:
        bound = _point(_interval(right, env))
    elif right == branch:
        bound, direction = _point(_interval(left, env)), _FLIP[direction]
    else:
        return None
    if bound is None:
        return None
    if not taken:
        direction = _FLIP[direction]
    return (bound, math.inf) if direction == "up" else (-math.inf, bound)


def _if_interval(form: Call, env: Env) -> Optional[Interval]:
    """``a if c else b``: the union of the branches' intervals. The condition
    is not folded, except that a branch which is the compared name is bounded
    by the comparison (:func:`_branch_bound`). ``None`` when either branch, or
    the condition, reads a pool."""
    cond, kw = form.kwargs.get("cond"), form.kwargs
    if cond is not None and _interval(cond, env) is None:
        return None
    if "then" not in kw or "else" not in kw:
        return _LINE
    hull: list[Interval] = []
    for key, taken in (("then", True), ("else", False)):
        iv = _interval(kw[key], env)
        if iv is None:
            return None
        bound = _branch_bound(cond, kw[key], taken, env)
        if bound is not None:
            iv = (max(iv[0], bound[0]), min(iv[1], bound[1]))
            if iv[0] > iv[1]:
                continue  # this branch never runs
        hull.append(iv)
    if not hull:
        return _LINE
    return (min(h[0] for h in hull), max(h[1] for h in hull))


def _rounded(head: str, ivs: Sequence[Interval]) -> Interval:
    """``round`` / ``int`` / ``float`` are monotone: they map the bounds."""
    digits = _point(ivs[1]) if len(ivs) == 2 else None
    if len(ivs) == 2 and (digits is None or head != "round"):
        return _LINE

    def f(x: float) -> float:
        if math.isinf(x):
            return x
        if head == "float":
            return x
        if head == "int":
            return float(int(x))
        return float(round(x, int(digits))) if digits is not None else float(round(x))

    lo, hi = ivs[0]
    return (f(lo), f(hi))


def _unfolded(form: Any, env: Env, depth: int = 0) -> Optional[str]:
    """The first head under ``form`` (through bound draws) the sign fold reads
    as the whole line because it is outside :data:`FOLDED_FORMS`."""
    if depth > 50:
        return None
    if isinstance(form, Name):
        drawn = _drawn_binding(form, env)
        return _unfolded(drawn[0], drawn[1], depth + 1) if drawn is not None else None
    if isinstance(form, Quoted):
        return _unfolded(form.form, env, depth + 1)
    if isinstance(form, (list, tuple)):
        return next((h for h in (_unfolded(x, env, depth + 1) for x in form) if h is not None), None)
    if not isinstance(form, Call) or form.head in MODULATION_HEADS:
        return None
    if form.head == "if":
        parts: list[Any] = [form.kwargs.get("then"), form.kwargs.get("else")]
    else:
        parts = [*form.args, *form.kwargs.values()]
        if form.head not in _FOLDED_HEADS:
            try:
                dist = env.head(form.head).kind == "dist"
            except ExprError:
                dist = False
            if not dist and _interval(form, env) == _LINE:
                return form.head
    return next((h for h in (_unfolded(x, env, depth + 1) for x in parts) if h is not None), None)


def _fold_note(form: Any, env: Env) -> str:
    head = _unfolded(form, env)
    if head is None:
        return ""
    shown = _CMP_SHOW.get(head, f"{head}(...)")
    return f" — the sign fold reads {shown} as the whole line; it covers {FOLDED_FORMS}"


_CMP_SHOW = {"op:gt": "a comparison", "op:ge": "a comparison", "op:lt": "a comparison", "op:le": "a comparison",
             "op:eq": "a comparison", "op:ne": "a comparison", "op:item": "an index", "op:attr": "an attribute"}


def _drawn_binding(name: Name, env: Env) -> Optional[tuple[Any, Env]]:
    """The form a name was bound to when that form draws (``k: !x normal(0.3,
    0.3)``), with its env; ``None`` for anything else. The draw happened at
    load, outside the law, so the bound value is one seed's number — judging
    it per seed refused 7 of 40 seeds mid-run (T091 J, T092). The sign rule
    folds the binding's FORM instead, so a bound draw gets the verdict the
    same draw gets inline. Covers file-level bindings (``Lazy``), through
    dotted steps into a mapping's form; a value bound already evaluated (a
    template argument) carries no form and is judged as the number it is."""
    first, *rest = name.path.split(".")
    raw = env.bindings.get(first)
    if not isinstance(raw, Lazy) or raw.state != "done":
        return None
    form, where = raw.form, raw.env
    for step in rest:
        if not (isinstance(form, Mapping) and step in form):
            return None
        form = form[step]
    return (form, where) if _draws(form, where) else None


def _draws(form: Any, env: Env) -> bool:
    """Whether evaluating ``form`` draws: it calls a distribution head (not
    under a quote — a quoted draw is a ``Dist`` value, judged by its support
    already), or names a binding that does."""
    if isinstance(form, Name):
        return _drawn_binding(form, env) is not None
    if isinstance(form, Mapping):
        return any(_draws(v, env) for v in form.values())
    if isinstance(form, (list, tuple)):
        return any(_draws(v, env) for v in form)
    if not isinstance(form, Call):
        return False
    if not form.head.startswith("op:") and form.head not in MODULATION_HEADS:
        try:
            if env.head(form.head).kind == "dist":
                return True
        except ExprError:
            return False
    return any(_draws(a, env) for a in form.args) or any(_draws(v, env) for v in form.kwargs.values())


def _evaluated(form: Any, env: Env) -> Interval:
    try:
        value = evaluate(form, env)
    except (ExprError, ArithmeticError, ValueError):
        return _LINE
    iv = _value_interval(value)
    return iv if iv is not None else _LINE


def _value_interval(value: Any) -> Optional[Interval]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return (float(value), float(value))
    if isinstance(value, QuotedForm):
        return _interval(value.form, value.env)
    if isinstance(value, Dist):
        support = support_of(value)
        return support if support is not None else _LINE
    return None


def _signed_factors(form: Any, sign: int = 1, divisor: bool = False) -> tuple[list[tuple[Any, bool]], int]:
    """The factors of the top-level product chain (multiplicands and divisors,
    through unary minus), each with whether it divides, and the sign the
    unary minuses carry."""
    if isinstance(form, Call) and form.head == "op:neg" and len(form.args) == 1 and not form.kwargs:
        return _signed_factors(form.args[0], -sign, divisor)
    if isinstance(form, Call) and form.head in ("op:mul", "op:div") and len(form.args) == 2 and not form.kwargs:
        left, sign = _signed_factors(form.args[0], sign, divisor)
        right, sign = _signed_factors(form.args[1], sign, divisor != (form.head == "op:div"))
        return left + right, sign
    return [(form, divisor)], sign


def _show(iv: Interval) -> str:
    return f"[{iv[0]:g}, {iv[1]:g}]"


def _describe(form: Any, env: Env) -> str:
    """A factor as the author wrote it; a bound name says what it is bound to."""
    if isinstance(form, Name):
        try:
            value = env.lookup(form.path)
        except ExprError:
            return form.path
        drawn = _drawn_binding(form, env)
        shown = drawn[0] if drawn is not None else value.form if isinstance(value, QuotedForm) else value
        return f"{form.path} (bound to {shown!r})"
    return repr(form)


def _modulation_param_forms(form: Call) -> dict[str, Any]:
    """A modulation call's parameter forms by name (positional after the pool, then keywords)."""
    positional, _extras = MODULATION_HEADS[form.head]
    out: dict[str, Any] = dict(zip(positional, form.args[1:]))
    out.update(form.kwargs)
    return out


def check_modulation_supports(form: Any, env: Env) -> None:
    """Refuse a modulation parameter whose support can leave its domain on some
    seed — the sign rule extended to ``hill`` / ``michaelis`` / ``activator``
    / ``inhibitor`` (T091 M2). ``K``, ``Ki``, ``Vmax`` and ``a`` are rate
    constants in all but name: each must have a non-negative support. A hill
    whose ``K`` can be 0 needs a point, non-negative integer ``n``
    (``rate_expr._check_modulation_params``); with ``K > 0`` on every seed
    ``n`` may be anything. A drawn ``Ki`` used to refuse per seed, after other
    trials had spent; a drawn ``K`` / ``Vmax`` / ``a`` ran at rate 0 on some
    seeds. Refused at LOAD, naming the parameter and the node."""
    if not isinstance(form, Call):
        return
    if form.head in MODULATION_HEADS:
        params = _modulation_param_forms(form)
        ivs = {name: _interval(value, env) for name, value in params.items()}
        for name, iv in ivs.items():
            if iv is None or name == "n":
                continue
            if not (iv[0] >= 0.0):
                raise env.error(
                    f"rate law: {form.head}.{name} can be negative — {_describe(params[name], env)} has support "
                    f"{_show(iv)}; a modulation parameter's support must be non-negative (refused at load, on every seed)"
                    f"{_fold_note(params[name], env)}"
                )
        if form.head == "hill":
            k_iv = ivs.get("K")
            n_iv = ivs.get("n", (2.0, 2.0))
            if k_iv is not None and k_iv[0] == 0.0 and n_iv is not None:
                n = _point(n_iv)
                if n is None or not (n >= 0.0 and n.is_integer()):
                    raise env.error(
                        f"rate law: hill.K can be 0 (support {_show(k_iv)}) with n support {_show(n_iv)} — "
                        "K == 0 needs a non-negative integer n on every seed (refused at load)"
                    )
    for arg in form.args:
        check_modulation_supports(arg, env)
    for arg in form.kwargs.values():
        check_modulation_supports(arg, env)


def check_constant_sign(form: Any, env: Env) -> None:
    """Refuse a rate law whose constant factor can be negative on some seed
    (the module docstring's sign rule), or whose modulation parameter can
    leave its domain (:func:`check_modulation_supports`). Pool-reading
    factors are skipped: their sign is the state's, read as 0 at runtime
    when negative."""
    check_modulation_supports(form, env)
    whole = _interval(form, env)
    if whole is not None:
        if whole[0] < 0.0:
            if whole[0] == whole[1]:
                raise _negative_constant(env, whole[0])
            raise env.error(
                f"rate law: negative rate constant possible — {_describe(form, env)} has support {_show(whole)}; "
                "a rate constant's support must be non-negative (refused at load, on every seed)"
                f"{_fold_note(form, env)}"
            )
        return
    factors, sign = _signed_factors(form)
    negatives = 0 if sign > 0 else 1
    folded = float(sign)
    for factor, divides in factors:
        iv = _interval(factor, env)
        if iv is None:
            continue
        if iv == (0.0, 0.0):
            return  # a zero factor: the law is 0 whatever the other signs
        if iv[0] < 0.0 < iv[1]:
            raise env.error(
                f"rate law: negative rate constant possible — the factor {_describe(factor, env)} has support {_show(iv)}; "
                "a rate constant's support must be non-negative (refused at load, on every seed)"
                f"{_fold_note(factor, env)}"
            )
        if iv[1] <= 0.0 and iv[0] < 0.0:
            negatives += 1
        point = _point(iv)
        if point is None or math.isnan(folded):
            folded = math.nan
        else:
            folded = folded / point if divides else folded * point
    if negatives % 2:
        if not math.isnan(folded):
            raise _negative_constant(env, folded)
        raise env.error(
            "rate law: negative rate constant — the law's constant factors multiply to a negative "
            "number on every seed; a rate is never negative (it ran as rate 0)"
        )


def _pool(form: Any, env: Env) -> str:
    """The modifier pool a modulation names: a string literal, or a bare name not bound in scope."""
    if isinstance(form, str):
        return env.pool(form)
    if isinstance(form, Name):
        try:
            env.lookup(form.path)
        except ExprError:
            return env.pool(form.path)
        raise env.error(
            f"rate law: {form.path!r} is bound in scope, so it cannot name a pool here — "
            f"quote it (\"{form.path}\") to mean the pool"
        )
    raise _refuse(env, f"a modulation over {type(form).__name__}")


def _modulation(form: Call, env: Env) -> ModulationSpec:
    kind = form.head
    positional, extras = MODULATION_HEADS[kind]
    if not form.args:
        raise env.error(f"rate law: {kind}(...) needs the modifier pool as its first argument")
    pool = _pool(form.args[0], env)
    params: dict[str, Dist[float]] = {}
    rest = list(form.args[1:])
    for name in positional:
        if rest:
            params[name] = _constant(rest.pop(0), env, f"{kind}.{name}")
        elif name in form.kwargs:
            params[name] = _constant(form.kwargs[name], env, f"{kind}.{name}")
        else:
            raise env.error(f"rate law: {kind}(...) is missing {name!r}")
    if rest:
        raise env.error(f"rate law: {kind}(...) takes {1 + len(positional)} positional arguments")
    for key, value in form.kwargs.items():
        if key in positional:
            continue
        if key not in extras:
            raise env.error(f"rate law: {kind}(...) has no parameter {key!r}")
        params[key] = _constant(value, env, f"{kind}.{key}")
    for key, default in _MODULATION_DEFAULTS[kind].items():
        params.setdefault(key, Constant(default))
    return ModulationSpec(pool=pool, kind=kind, params=params)


def compile_rate(
    value: Any,
    env: Env,
    *,
    reactants: Sequence[str] = (),
    products: Sequence[str] = (),
) -> RateLaw:
    """Compile a ``rate:`` value into a :class:`RateLaw`.

    ``value``: a number, a ``Dist``, or a :class:`QuotedForm` in the rate
    grammar. Raises :class:`ExprError` (with the node path) for anything the
    engine cannot run.
    """
    if value is None:
        return RateLaw(k=Constant(1.0))
    if isinstance(value, bool):
        raise env.error("rate: expected a number, a Dist or a quoted rate law, got a bool")
    if isinstance(value, (int, float)):
        if float(value) < 0.0:
            raise _negative_constant(env, float(value))
        return RateLaw(k=Constant(float(value)))
    if isinstance(value, QuotedForm):
        return _compile_form(value.form, value.env, reactants=reactants, products=products)
    if isinstance(value, Dist):
        support = support_of(value)
        if support is not None and support[0] < 0.0:
            raise env.error(
                f"rate: negative rate constant possible — {value!r} has support {_show(support)}; "
                "a rate constant's support must be non-negative (refused at load, on every seed)"
            )
        return RateLaw(k=value)
    raise env.error(f"rate: expected a number, a Dist or a quoted rate law, got {type(value).__name__}")


def _is_draw(form: Any, env: Env) -> bool:
    """A factor drawn at world build: a distribution call, a name bound to a
    non-constant Dist, or a quoted form."""
    if isinstance(form, Quoted):
        return True
    if isinstance(form, Name):
        try:
            value = env.lookup(form.path)
        except ExprError:
            return False
        return isinstance(value, Dist) and not isinstance(value, Constant)
    if isinstance(form, Call) and not form.head.startswith("op:") and form.head not in MODULATION_HEADS:
        try:
            return env.head(form.head).kind == "dist"
        except ExprError:
            return False
    return False


def _product_factors(form: Any) -> list[Any]:
    """The factors of a product chain, through unary minus."""
    if isinstance(form, Call) and form.head == "op:neg" and len(form.args) == 1:
        return _product_factors(form.args[0])
    if isinstance(form, Call) and form.head == "op:mul" and len(form.args) == 2 and not form.kwargs:
        return _product_factors(form.args[0]) + _product_factors(form.args[1])
    return [form]


def _refuse_drawn_products(form: Any, env: Env) -> None:
    """Refuse a product of two distributions anywhere in the law (T091 E9:
    ``lognormal(0,1) * lognormal(0,1) * A`` loaded and multiplied two draws)."""
    if not isinstance(form, Call):
        return
    if form.head in ("op:mul", "op:neg"):
        factors = _product_factors(form)
        if sum(1 for f in factors if _is_draw(f, env)) > 1:
            raise env.error("rate law: a product of two distributions; draw one rate constant")
        for f in factors:
            _refuse_drawn_products(f, env)
        return
    for arg in form.args:
        _refuse_drawn_products(arg, env)
    for arg in form.kwargs.values():
        _refuse_drawn_products(arg, env)


def _compile_form(form: Any, env: Env, *, reactants: Sequence[str], products: Sequence[str]) -> RateLaw:
    """The product form when the law has that shape; else the general expression."""
    _refuse_drawn_products(form, env)
    check_constant_sign(form, env)
    try:
        return _compile_product(form, env, reactants=reactants, products=products)
    except _NotProductForm:
        pass
    view_env = env.__class__(env.bindings, env.registry.view(RATE_VIEW_KINDS), env.ctx, env.ns, env.depth)
    expr = _compile_expr(form, view_env, consumed=set(reactants) | set(products))
    return RateLaw(k=Constant(1.0), expr=expr)


_UNARY_HEADS = {"exp", "log", "sqrt"}
_BINARY_OPS = {"op:add": "add", "op:sub": "sub", "op:mul": "mul", "op:div": "div", "op:pow": "pow"}


def _general_refuse(env: Env, what: str) -> ExprError:
    return env.error(f"rate law: {what} is outside the rate grammar")


def _compile_expr(form: Any, env: Env, *, consumed: set[str]) -> Any:
    """A form in the rate grammar -> a ``bio.rate_expr`` tree over pool names
    (with ``("dist", Dist)`` leaves for what is drawn at world build)."""
    if isinstance(form, bool):
        raise _general_refuse(env, "a bool")
    if isinstance(form, (int, float)):
        return rx.const(float(form))
    if isinstance(form, str):
        return rx.species(env.pool(form))
    if isinstance(form, Name):
        try:
            value = env.lookup(form.path)
        except ExprError:
            return rx.species(env.pool(form.path))
        if isinstance(value, bool):
            raise _general_refuse(env, f"{form.path!r} (a bool)")
        if isinstance(value, (int, float)):
            return rx.const(float(value))
        if isinstance(value, Dist):
            return ("dist", value)
        raise _general_refuse(env, f"{form.path!r} (bound to a {type(value).__name__})")
    if isinstance(form, Quoted):
        return ("dist", QuotedForm(form.form, env))
    if isinstance(form, Call):
        if form.head == "op:neg" and len(form.args) == 1:
            return ("neg", _compile_expr(form.args[0], env, consumed=consumed))
        if form.head in _BINARY_OPS and len(form.args) == 2 and not form.kwargs:
            a, b = (_compile_expr(x, env, consumed=consumed) for x in form.args)
            return (_BINARY_OPS[form.head], a, b)
        if form.head.startswith("op:"):
            raise _general_refuse(env, f"the operator {form.head[3:]!r}")
        if form.head in _UNARY_HEADS and len(form.args) == 1 and not form.kwargs:
            return (form.head, _compile_expr(form.args[0], env, consumed=consumed))
        if form.head in MODULATION_HEADS:
            spec = _modulation(form, env)
            return ("mod", spec.kind, spec.pool, dict(spec.params))
        head = env.head(form.head)  # unknown / out-of-view heads fail here, naming the node
        if head.kind in ("dist", "math"):
            _refuse_quoted_draw_argument(form, env)
            value = evaluate(form, env)
            if isinstance(value, bool):
                raise _general_refuse(env, f"{form.head}(...) (a bool)")
            if isinstance(value, (int, float)):
                return rx.const(float(value))
            if isinstance(value, Dist):
                return ("dist", value)
        raise _general_refuse(env, f"a call of {form.head!r}")
    raise _general_refuse(env, f"a {type(form).__name__}")


def _compile_product(form: Any, env: Env, *, reactants: Sequence[str], products: Sequence[str]) -> RateLaw:
    """The M47.3 product form: ``k * modulation * ...`` (refuses anything else)."""
    view_env = env.__class__(env.bindings, env.registry.view(RATE_VIEW_KINDS), env.ctx, env.ns, env.depth)
    k: Optional[Dist[float]] = None
    modulations: list[ModulationSpec] = []
    consumed = set(reactants) | set(products)
    for factor in _flatten_product(form):
        if isinstance(factor, Call) and factor.head in MODULATION_HEADS:
            spec = _modulation(factor, view_env)
            if spec.pool in consumed:
                raise _refuse(
                    view_env,
                    f"{factor.head}({spec.pool!r}, ...) over a reactant or product (substrate-saturation kinetics)",
                )
            modulations.append(spec)
            continue
        if isinstance(factor, Name) and view_env.pool(factor.path) in consumed:
            # A law naming a reactant is the whole rate (and one naming a
            # product only is a factor on mass action) — the expression
            # path's rule, so `0.2 * A` and `0.2 * A + 0.0` agree (T091 E4;
            # this branch used to drop the name as "inert"). Compared as the
            # pool the name denotes HERE: inside a template the reactants
            # arrive namespaced (`inst.S`) (T088 rate_law 1).
            raise _refuse(view_env, f"a factor naming the consumed pool {factor.path!r}")
        if isinstance(factor, Call) and factor.head.startswith("op:") and factor.head not in ("op:neg", "op:mul"):
            raise _refuse(view_env, f"the operator {factor.head[3:]!r}")
        if isinstance(factor, Call) and factor.head not in ("op:neg", "op:mul"):
            head = view_env.head(factor.head)  # unknown / out-of-view heads fail here
            if head.kind not in ("dist", "math"):
                raise _refuse(view_env, f"a call of {factor.head!r}")
        piece = _constant(factor, view_env, "a rate factor")
        k = piece if k is None else _scale(k, piece, view_env, "the rate constant")
    k = k if k is not None else Constant(1.0)
    return RateLaw(k=k, modulations=tuple(modulations))


__all__ = ["RateLaw", "ModulationSpec", "compile_rate", "hill", "michaelis", "activator", "inhibitor", "RATE_VIEW_KINDS"]
