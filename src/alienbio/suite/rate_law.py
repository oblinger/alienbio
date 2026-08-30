"""Rate laws — the compiled tier of Expr (M47.3).

A ``rate:`` slot is **not** run by the interpreter. It is a number / ``Dist``
(the mass-action constant ``k``) or a quoted form in the **rate grammar**,
compiled once here into a :class:`RateLaw` the engine evaluates every step.

What compiles today is exactly what the engine vectorises: mass action over
the reactants (implicit — the engine multiplies by the reactant
concentrations itself) times a product of **modulations** by non-consumed
modifier pools — the four ``Modulation`` kinds ``bio/reaction.py`` implements:

    k
    k * hill(M, K, n=2)
    k * michaelis(M, K) * inhibitor(I, Ki)
    k * activator(A, a)

``k`` may be a number, a bound constant, or a bound ``Dist``; the modulation
parameters likewise. A bare name that is not bound in scope is a **pool**
(a quoted string always is). Anything else — a sum, a quotient, ``exp``,
substrate-saturation kinetics written over a *reactant* (``Vmax * S / (Km +
S)``) — is refused at load with the node path: the engine cannot run it, and
nothing falls back to per-step Python. Growing the compiler to the full rate
grammar on JAX is roadmap M47.10.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

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
    """A compiled rate law: ``k`` (a Dist) times zero or more modulations."""

    k: Dist[float]
    modulations: tuple[ModulationSpec, ...] = ()

    @property
    def modifier_pools(self) -> tuple[str, ...]:
        return tuple(m.pool for m in self.modulations)


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
            value = evaluate(form, env)
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
        return form
    if isinstance(form, Name):
        try:
            env.lookup(form.path)
        except ExprError:
            return form.path
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
