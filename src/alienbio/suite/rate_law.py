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
a constant factor that can be negative.

**A rate law's constant factor is non-negative by construction** (T091 E9,
I1–I3). The rate-constant positions are the whole law when it reads no pool,
and each factor of its top-level product chain (multiplicands and divisors,
through unary minus) that reads no pool. Each such factor is folded at
compile — constant arithmetic (``k - 1`` with ``k = 0.5``, ``0.2 / -1``,
``exp(-1)``), bound numbers, bound and quoted distributions — to the interval
it can take *on any seed*: a number is a point, a distribution its support
(``normal`` the whole line, ``uniform(lo, hi)`` ``[lo, hi]``, ``lognormal`` /
``poisson`` / ``exponential`` ``[0, ∞)``, :func:`~alienbio.suite.dist.support_of`
for a ``Dist`` object). A factor whose interval straddles zero, or a product
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
from ..expr.env import Env, ExprError
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


def _dist_head_support(head: str, args: Sequence[Optional[Interval]]) -> Optional[Interval]:
    """The support of a distribution head called with these argument intervals."""
    if head == "normal":
        return _LINE
    if head == "uniform" and len(args) == 2 and args[0] is not None and args[1] is not None:
        return (min(args[0][0], args[1][0]), max(args[0][1], args[1][1]))
    if head in ("lognormal", "poisson", "exponential", "discrete"):
        return _HALF
    if head == "constant" and len(args) == 1:
        return args[0]
    return None


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
            return _interval_mul(a, b)
        return _interval_div(a, b)
    if form.head == "op:pow" and len(ivs) == 2:
        if _point(ivs[0]) is not None and _point(ivs[1]) is not None:
            return _evaluated(form, env)
        return _HALF if ivs[0][0] >= 0.0 else _LINE
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
        support = _dist_head_support(form.head, ivs)
        return support if support is not None else _LINE
    if all(_point(iv) is not None for iv in ivs) and all(_point(v) is not None for v in kwargs.values()):
        return _evaluated(form, env)
    return _LINE


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


def _signed_factors(form: Any, sign: int = 1) -> tuple[list[Any], int]:
    """The factors of the top-level product chain (multiplicands and divisors,
    through unary minus) and the sign the unary minuses carry."""
    if isinstance(form, Call) and form.head == "op:neg" and len(form.args) == 1 and not form.kwargs:
        return _signed_factors(form.args[0], -sign)
    if isinstance(form, Call) and form.head in ("op:mul", "op:div") and len(form.args) == 2 and not form.kwargs:
        left, sign = _signed_factors(form.args[0], sign)
        right, sign = _signed_factors(form.args[1], sign)
        return left + right, sign
    return [form], sign


def _show(iv: Interval) -> str:
    return f"[{iv[0]:g}, {iv[1]:g}]"


def _describe(form: Any, env: Env) -> str:
    """A factor as the author wrote it; a bound name says what it is bound to."""
    if isinstance(form, Name):
        try:
            value = env.lookup(form.path)
        except ExprError:
            return form.path
        shown = value.form if isinstance(value, QuotedForm) else value
        return f"{form.path} (bound to {shown!r})"
    return repr(form)


def check_constant_sign(form: Any, env: Env) -> None:
    """Refuse a rate law whose constant factor can be negative on some seed
    (the module docstring's sign rule). Pool-reading factors are skipped:
    their sign is the state's, read as 0 at runtime when negative."""
    whole = _interval(form, env)
    if whole is not None:
        if whole[0] < 0.0:
            if whole[0] == whole[1]:
                raise _negative_constant(env, whole[0])
            raise env.error(
                f"rate law: negative rate constant possible — {_describe(form, env)} has support {_show(whole)}; "
                "a rate constant's support must be non-negative (refused at load, on every seed)"
            )
        return
    factors, sign = _signed_factors(form)
    negatives = 0 if sign > 0 else 1
    folded = float(sign)
    for factor in factors:
        iv = _interval(factor, env)
        if iv is None:
            continue
        if iv == (0.0, 0.0):
            return  # a zero factor: the law is 0 whatever the other signs
        if iv[0] < 0.0 < iv[1]:
            raise env.error(
                f"rate law: negative rate constant possible — the factor {_describe(factor, env)} has support {_show(iv)}; "
                "a rate constant's support must be non-negative (refused at load, on every seed)"
            )
        if iv[1] <= 0.0 and iv[0] < 0.0:
            negatives += 1
        point = _point(iv)
        folded = folded * point if point is not None and not math.isnan(folded) else math.nan
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
