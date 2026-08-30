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
mass action. ``k`` and every parameter may be a number, a bound constant, a
bound ``Dist`` or a distribution call (drawn once, at world build). A bare
name that is not bound in scope is a **pool** (a quoted string always is).
What is still refused, at load with the node path: a head outside the rate
view (a world-building head, a Python-only function), a bool, a product of
two distributions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from ..bio import rate_expr as rx
from ..bio.reaction import Modulation
from ..expr.env import Env, ExprError
from ..expr.form import Call, Name, Quoted
from ..expr.interp import QuotedForm, evaluate
from ..expr.registry import fn
from .dist import Constant, Dist, Seed

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


@fn(kind="rate", summary="Hill response of a modifier: Vmax * m**n / (K**n + m**n)")
def hill(m: float, K: float, n: float = 2.0, Vmax: float = 1.0) -> float:
    return Vmax * m**n / (K**n + m**n) if (K or m) else 0.0


@fn(kind="rate", summary="Michaelis-Menten response of a modifier: Vmax * m / (K + m)")
def michaelis(m: float, K: float, Vmax: float = 1.0) -> float:
    return Vmax * m / (K + m) if (K or m) else 0.0


@fn(kind="rate", summary="linear activation: 1 + a * m")
def activator(m: float, a: float) -> float:
    return 1.0 + a * m


@fn(kind="rate", summary="linear inhibition: 1 / (1 + m / Ki)")
def inhibitor(m: float, Ki: float) -> float:
    return 1.0 / (1.0 + m / Ki)


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
        ``seed`` — the tree a ``ReactionImpl`` carries."""
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

    def __repr__(self) -> str:
        return f"_Scaled({self.base!r} * {self.factor})"


def _flatten_product(form: Any) -> list[Any]:
    if isinstance(form, Call) and form.head == "op:mul" and len(form.args) == 2 and not form.kwargs:
        return _flatten_product(form.args[0]) + _flatten_product(form.args[1])
    return [form]


def _refuse(env: Env, what: str) -> ExprError:
    return env.error(
        f"rate law: {what} is outside the engine's compilable subset "
        "(mass action × modulations by non-consumed pools) — M47.10"
    )


def _constant(form: Any, env: Env, what: str) -> Dist[float]:
    """A constant factor: a literal, a bound number, or a bound Dist."""
    if isinstance(form, bool):
        raise _refuse(env, f"{what} (a bool)")
    if isinstance(form, (int, float)):
        return Constant(float(form))
    if isinstance(form, Name):
        value = env.lookup(form.path)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return Constant(float(value))
        if isinstance(value, Dist):
            return value
        raise _refuse(env, f"{what} ({form.path!r} is bound to a {type(value).__name__})")
    if isinstance(form, Quoted):
        return QuotedForm(form.form, env)
    if isinstance(form, Call) and form.head in ("op:neg",):
        inner = _constant(form.args[0], env, what)
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
    raise _refuse(env, f"{what}: a product of two distributions")


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
        return RateLaw(k=Constant(float(value)))
    if isinstance(value, QuotedForm):
        return _compile_form(value.form, value.env, reactants=reactants, products=products)
    if isinstance(value, Dist):
        return RateLaw(k=value)
    raise env.error(f"rate: expected a number, a Dist or a quoted rate law, got {type(value).__name__}")


def _compile_form(form: Any, env: Env, *, reactants: Sequence[str], products: Sequence[str]) -> RateLaw:
    """The product form when the law has that shape; else the general expression."""
    try:
        return _compile_product(form, env, reactants=reactants, products=products)
    except ExprError as exc:
        if "compilable subset" not in str(exc):
            raise
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
        if isinstance(factor, Name) and factor.path in consumed:
            continue  # mass action over a reactant is implicit — naming it is allowed and inert
        if isinstance(factor, Call) and factor.head.startswith("op:") and factor.head not in ("op:neg", "op:mul"):
            raise _refuse(view_env, f"the operator {factor.head[3:]!r}")
        if isinstance(factor, Call) and factor.head not in ("op:neg", "op:mul"):
            head = view_env.head(factor.head)  # unknown / out-of-view heads fail here
            if head.kind not in ("dist", "math"):
                raise _refuse(view_env, f"a call of {factor.head!r}")
        piece = _constant(factor, view_env, "a rate factor")
        k = piece if k is None else _scale(k, piece, view_env, "the rate constant")
    return RateLaw(k=k if k is not None else Constant(1.0), modulations=tuple(modulations))


__all__ = ["RateLaw", "ModulationSpec", "compile_rate", "hill", "michaelis", "activator", "inhibitor", "RATE_VIEW_KINDS"]
