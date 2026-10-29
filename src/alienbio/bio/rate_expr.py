"""Compiled rate expressions — the one representation of a rate law both
simulators run (M47.10).

A rate law that is more than ``k × modulations`` (Michaelis–Menten written
over the substrate, a sum of terms, ``exp`` / ``log`` / ``sqrt`` algebra over
species) compiles to a small tree of tuples::

    ("const", 0.4)
    ("species", "S")                       # a concentration, by name (or id)
    ("neg", a) | ("add"|"sub"|"mul"|"div"|"pow", a, b)
    ("exp"|"log"|"sqrt", a)
    ("mod", "hill", "M", {"K": 0.5, "n": 2.0, "Vmax": 1.0})   # a modulation

The tree carries only numbers, species and operators — every bound constant
and every ``Dist`` was folded or drawn when the law was compiled and realised
— so it is JSON-able (a reaction's ``attributes()`` round-trips it) and it
evaluates the same way in Python (:func:`eval_rate`, the reference simulator)
and under JAX (:func:`lower_jax`, the vectorised core). The modulation math
is exactly ``WorldSimulatorImpl._modulation_factor``'s.

A law's **value is the whole rate** when it names a reactant (``Vmax * S /
(Km + S)`` over substrate ``S``); when it names no reactant, mass action over
the reactants is implicit and the law is the factor that multiplies it
(``k * hill(M, K)`` — the M47.3 form). :func:`implicit_mass_action` decides.

**Supported magnitudes.** The two simulators agree to 1e-9 (relative, or
absolute near zero: :func:`parity_agrees`, ``|a − b| ≤ PARITY_TOL ·
max(1, |a|, |b|)``, the one statement every conformance test asserts) for
concentrations, multiplicities and amounts from 0 to
1e6 — the range the conformance property draws (catalog pools are ~1–100).
Where IEEE / JAX semantics give NaN or inf, the reference gives the same NaN
or inf, never a different finite number. Pools far beyond that range, or
spread across more orders of magnitude than float64 carries (a 1e100 pool
refilled by a 1e6 one: JAX's fused update loses the 1e6 below the 1e100
pool's ulp, the reference's sequential update does not), are out of
contract (T091 C3).
"""

from __future__ import annotations

import math
from typing import Any, Callable, Hashable, Iterable, Mapping

#: Below this magnitude a concentration is float rounding of an exact zero, not
#: a real amount: both simulators snap a negative residue this small to zero
#: (M48.6), and a rate law divides by it as if it were zero. The one constant
#: both backends and the population pass import (T051 box 4 / T054 — the two
#: backends carried their own copies, and a `1/[x]` law amplified a 1e-16
#: residue on one of them into a RATE_CAP extent while the other read exactly 0).
ROUNDING_FLOOR = 1e-12


#: The parity contract between the reference and JAX simulators (module
#: docstring, § Supported magnitudes): see :func:`parity_agrees`.
PARITY_TOL = 1e-9


def parity_agrees(a: float, b: float) -> bool:
    """True when two simulator readings agree under the parity contract:
    ``|a − b| ≤ PARITY_TOL · max(1, |a|, |b|)`` — relative above 1, absolute
    below — or both NaN, or the same infinity. Float64 on both sides carries
    ~1e-16 relative per operation, so a reading off by more than 1e-9 of its
    own magnitude is a divergence in the arithmetic, not accumulated
    rounding."""
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= PARITY_TOL * max(1.0, abs(a), abs(b))


def snap_residue(value: float, pre: float) -> float:
    """``value`` with a negative rounding residue snapped to exactly zero.

    A pass that rations a pool to exhaustion leaves, in exact arithmetic,
    exactly zero; in float64 it leaves a residue on the order of the pool's
    own ulp. So the tolerance is RELATIVE: a post-pass value within
    ``ROUNDING_FLOOR * max(1, pre)`` below zero — ``pre`` the value the pass
    started from — is zero. (T091 C3: the absolute ``-1e-12`` snap left a
    rationed 1e5 pool at -1.1e-11, negative on both backends and
    disagreeing between them.) Every pass that draws a pool — reactions on
    both backends (:func:`snap_residue_jax` is the same arithmetic over
    arrays), the flow pass, the population pass — calls this one rule."""
    scale = pre if pre > 1.0 else 1.0
    return 0.0 if -ROUNDING_FLOOR * scale < value < 0.0 else value


def asks_all(demand: float, avail: float) -> bool:
    """Whether a pass asks a pool for everything it holds — the exhausted-pool
    test both reaction steppers share (:func:`asks_all_jax` is the same
    arithmetic over arrays).

    ``demand >= avail`` up to the same relative tolerance :func:`snap_residue`
    uses, ``ROUNDING_FLOOR * max(1, avail)``. Not ``ratio < 1``: the drawing
    reactions' ``k·dt`` summing to 1 makes the demand equal the pool to
    within an ulp, ``ratio`` rounds to 1.0, and the two backends — which sum
    the draws in different orders — land on opposite sides of an exact
    ``>=`` (T091 M1: 11 of 400 such pools left a residue on one backend
    only, which a ``1/[x]`` law amplified to a relative gap of 1.0)."""
    if not demand > 0.0:
        return False
    scale = avail if avail > 1.0 else 1.0
    return demand >= avail - ROUNDING_FLOOR * scale


def asks_all_jax(demand: Any, avail: Any) -> Any:
    """:func:`asks_all` over arrays, the same arithmetic as JAX ops."""
    import jax.numpy as jnp

    scale = jnp.where(avail > 1.0, avail, 1.0)
    return (demand > 0.0) & (demand >= avail - ROUNDING_FLOOR * scale)


def snap_residue_jax(value: Any, pre: Any) -> Any:
    """:func:`snap_residue` over arrays, the same arithmetic as JAX ops."""
    import jax.numpy as jnp

    scale = jnp.where(pre > 1.0, pre, 1.0)
    return jnp.where((value < 0.0) & (value > -ROUNDING_FLOOR * scale), 0.0, value)


#: The largest desired extent a reaction may ask for in one step: an infinite
#: rate means "all of it", and the rationing then bounds it by availability.
RATE_CAP = 1e150

RateNode = tuple  # see the module docstring


# IEEE-754 arithmetic for the reference path. Python refuses where XLA does not:
# ``0.0 ** -1.0`` raises ZeroDivisionError, ``10.0 ** 400`` and ``math.exp(1000)``
# raise OverflowError, ``(-1e-13) ** 0.5`` returns a COMPLEX, and ``m / 0.0``
# raises. JAX reads each as inf or NaN, and both steppers then clamp the
# same way (inf -> RATE_CAP, NaN -> no reaction). These three helpers are the
# one place the reference reads them as JAX does; on every input Python does
# accept they return Python's own result bit for bit (module-doc finding,
# 2026-10).


def _odd_integer(b: float) -> bool:
    return b == b and math.isfinite(b) and b == int(b) and int(b) % 2 == 1


def _integer(b: float) -> bool:
    return math.isfinite(b) and b == int(b)


def ieee_pow(a: float, b: float) -> float:
    """``a ** b`` as IEEE-754 / ``jnp.power`` reads it: inf on a zero base with
    a negative exponent or an overflow (signed for a negative base under an
    odd integer exponent), NaN where the real result does not exist — a
    negative base under a non-integer exponent is NaN on every path, the
    overflow included (CPython raises ``OverflowError`` for ``(-2.0) **
    1100.5`` before it would return a complex; T091 C1: read as inf, the
    reference consumed a whole reactant where JAX ran no reaction)."""
    try:
        result = a**b
    except (ZeroDivisionError, OverflowError):
        if a < 0.0 and not _integer(b):
            return math.nan
        negative = math.copysign(1.0, a) < 0.0 and _odd_integer(b)
        return -math.inf if negative else math.inf
    if isinstance(result, complex):
        return math.nan
    return result


def ieee_div(a: float, b: float) -> float:
    """``a / b`` as IEEE-754 reads it: a zero divisor gives a signed inf, or
    NaN when the numerator is zero or NaN. (A rate law's ``div`` node keeps
    its own rule — a divisor below ``ROUNDING_FLOOR`` is zero; this is the
    plain quotient the modulation arithmetic uses.)"""
    if b == 0.0:
        if a == 0.0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def ieee_exp(x: float) -> float:
    """``math.exp`` with overflow read as inf, as ``jnp.exp`` reads it."""
    try:
        return math.exp(x)
    except OverflowError:
        return math.inf

_BINARY = ("add", "sub", "mul", "div", "pow")
_UNARY = ("neg", "exp", "log", "sqrt")
MODULATION_KINDS = ("activator", "inhibitor", "michaelis", "hill")


def const(value: float) -> RateNode:
    return ("const", float(value))


def species(name: Hashable) -> RateNode:
    return ("species", name)


def modulation(kind: str, pool: Hashable, params: Mapping[str, float]) -> RateNode:
    """A modulation node. A negative or NaN ``Ki`` refuses, as ``Modulation``
    refuses it (T088 refresh 1: here it built an inhibitor that activates)."""
    if kind not in MODULATION_KINDS:
        raise ValueError(f"unknown modulation kind {kind!r}")
    out = {k: float(v) for k, v in params.items()}
    if "Ki" in out and not (out["Ki"] >= 0.0):
        raise ValueError(f"modulation: Ki must be >= 0, got {params['Ki']!r}")
    _check_modulation_params(kind, out)
    return ("mod", kind, pool, out)


def _check_modulation_params(kind: str, params: Mapping[str, Any]) -> None:
    """Refuse a hill whose ``K ** n`` has no real value or no finite one.

    A hill modulation is ``Vmax * m**n / (K**n + m**n)``. ``K`` (the
    half-saturation concentration) must be ``>= 0``; ``K == 0`` is allowed
    only with a non-negative integer ``n`` (the default is 2). Any ``n`` goes
    with ``K > 0``. Outside that, ``K ** n`` is complex (``K < 0`` under a
    fractional ``n``) or a division by zero (``K == 0, n < 0``): the JAX
    lowering computes it in Python at trace time and either raised
    ``ZeroDivisionError`` or cast a complex to real, while the reference read
    NaN (T091 C2). Refused here, at compile time, with one message for both
    simulators — :func:`modulation`, :func:`from_json` and
    :func:`check_rate_law` (which ``ReactionSpec`` calls) all run it."""
    if kind != "hill" or "K" not in params:
        return
    K = float(params["K"])
    n = float(params.get("n", 2.0))
    if not (K >= 0.0) or (K == 0.0 and not (n >= 0.0 and _integer(n))):
        raise ValueError(
            f"hill modulation: K={K!r} with n={n!r} has no finite real K**n — "
            "K must be >= 0, and K == 0 needs a non-negative integer n"
        )


def species_of(node: RateNode) -> set:
    """Every species the law reads."""
    tag = node[0]
    if tag == "species":
        return {node[1]}
    if tag == "mod":
        return {node[2]}
    if tag in _UNARY:
        return species_of(node[1])
    if tag in _BINARY:
        return species_of(node[1]) | species_of(node[2])
    return set()


def map_species(node: RateNode, fn: Callable[[Any], Any]) -> RateNode:
    """The same law over renamed species (names -> ids, for a simulator)."""
    tag = node[0]
    if tag == "species":
        return ("species", fn(node[1]))
    if tag == "mod":
        return ("mod", node[1], fn(node[2]), dict(node[3]))
    if tag in _UNARY:
        return (tag, map_species(node[1], fn))
    if tag in _BINARY:
        return (tag, map_species(node[1], fn), map_species(node[2], fn))
    return node


def implicit_mass_action(node: RateNode, reactants: Iterable[Any]) -> bool:
    """True when the law names no reactant: mass action over the reactants is
    then implicit and the law multiplies it."""
    return not (species_of(node) & set(reactants))


def inhibitor_ratio(m: float, Ki: float) -> float:
    """``m / Ki`` for an inhibitor's ``1 / (1 + m/Ki)``, with ``Ki = 0`` read
    as its limit: a perfect inhibitor — no inhibitor present (``m == 0``)
    leaves the rate alone (ratio 0, factor 1), any inhibitor stops it (ratio
    inf, factor 0). ``0 / 0`` would otherwise be NaN, which is no reaction,
    so ``Ki = 0`` stopped the reaction with no inhibitor present (T088
    jax_core 2). ``Modulation`` refuses a negative ``Ki``."""
    if m == 0.0:
        return 0.0
    return ieee_div(m, Ki)


def modulation_factor(kind: str, m: float, p: Mapping[str, float]) -> float:
    """One modulation's factor at modifier concentration ``m`` — the reference
    simulator's arithmetic, including its zero-denominator conventions."""
    if kind == "activator":
        return 1.0 + p["a"] * m
    if kind == "inhibitor":
        return ieee_div(1.0, 1.0 + inhibitor_ratio(m, p["Ki"]))
    if kind == "michaelis":
        denom = p["K"] + m
        return (p.get("Vmax", 1.0) * m / denom) if denom > 0.0 else 0.0
    if kind == "hill":
        n = p.get("n", 2.0)
        m_n = ieee_pow(m, n)
        denom = ieee_pow(p["K"], n) + m_n
        return (p.get("Vmax", 1.0) * m_n / denom) if denom > 0.0 else 0.0
    raise ValueError(f"unknown modulation kind {kind!r}")


def eval_rate(node: RateNode, conc: Callable[[Any], float]) -> float:
    """Evaluate the law with ``conc(species)`` giving each concentration."""
    tag = node[0]
    if tag == "const":
        return float(node[1])
    if tag == "species":
        return float(conc(node[1]))
    if tag == "mod":
        return modulation_factor(node[1], float(conc(node[2])), node[3])
    if tag == "neg":
        return -eval_rate(node[1], conc)
    if tag == "exp":
        return ieee_exp(eval_rate(node[1], conc))
    if tag == "log":
        x = eval_rate(node[1], conc)
        return math.log(x) if x > 0.0 else float("-inf")
    if tag == "sqrt":
        x = eval_rate(node[1], conc)
        return math.sqrt(x) if x > 0.0 else 0.0
    if tag not in _BINARY:
        # Checked before the operands are read: an unknown tag used to fail
        # with an unpacking TypeError/IndexError instead (module-doc finding).
        raise ValueError(f"unknown rate node {tag!r}")
    a, b = eval_rate(node[1], conc), eval_rate(node[2], conc)
    if tag == "add":
        return a + b
    if tag == "sub":
        return a - b
    if tag == "mul":
        return a * b
    if tag == "div":
        return a / b if abs(b) >= ROUNDING_FLOOR else 0.0
    return ieee_pow(a, b)  # tag == "pow", the last binary operator


def lower_jax(node: RateNode, S: Any, column: Callable[[Any], int]) -> Any:
    """The law over a state array ``S`` of shape ``[C, M]`` -> an array ``[C]``
    (one rate per compartment), as JAX ops — traced once under ``jit``.
    ``column(species)`` gives the molecule axis index."""
    import jax.numpy as jnp

    tag = node[0]
    if tag == "const":
        return jnp.full((S.shape[0],), float(node[1]), dtype=S.dtype)
    if tag == "species":
        return S[:, column(node[1])]
    if tag == "mod":
        m = S[:, column(node[2])]
        return _lower_modulation(node[1], m, node[3], jnp)
    if tag == "neg":
        return -lower_jax(node[1], S, column)
    if tag == "exp":
        return jnp.exp(lower_jax(node[1], S, column))
    if tag == "log":
        x: Any = lower_jax(node[1], S, column)
        safe: Any = jnp.where(x > 0.0, x, 1.0)
        return jnp.where(x > 0.0, jnp.log(safe), -jnp.inf)
    if tag == "sqrt":
        x = lower_jax(node[1], S, column)
        safe = jnp.where(x > 0.0, x, 0.0)
        return jnp.where(x > 0.0, jnp.sqrt(safe), 0.0)
    if tag not in _BINARY:
        raise ValueError(f"unknown rate node {tag!r}")
    a, b = lower_jax(node[1], S, column), lower_jax(node[2], S, column)
    if tag == "add":
        return a + b
    if tag == "sub":
        return a - b
    if tag == "mul":
        return a * b
    if tag == "div":
        live = jnp.abs(b) >= ROUNDING_FLOOR
        return jnp.where(live, a / jnp.where(live, b, 1.0), 0.0)
    return a**b  # tag == "pow", the last binary operator


def _lower_modulation(kind: str, m: Any, p: Mapping[str, float], jnp: Any) -> Any:
    if kind == "activator":
        return 1.0 + p["a"] * m
    if kind == "inhibitor":
        # ``inhibitor_ratio``'s Ki = 0 limit: no inhibitor, no effect.
        return 1.0 / (1.0 + jnp.where(m == 0.0, 0.0, m / p["Ki"]))
    if kind == "michaelis":
        denom = p["K"] + m
        return jnp.where(denom > 0.0, p.get("Vmax", 1.0) * m / jnp.where(denom > 0.0, denom, 1.0), 0.0)
    if kind == "hill":
        n = p.get("n", 2.0)
        m_n = m**n
        # ``_check_modulation_params`` admitted (K, n) at compile time, so this
        # trace-time constant is the reference's ``ieee_pow`` value.
        denom = ieee_pow(float(p["K"]), float(n)) + m_n
        return jnp.where(denom > 0.0, p.get("Vmax", 1.0) * m_n / jnp.where(denom > 0.0, denom, 1.0), 0.0)
    raise ValueError(f"unknown modulation kind {kind!r}")


def to_text(node: RateNode) -> str:
    """The law as inline Expr text (for messages and ``repr``)."""
    tag = node[0]
    if tag == "const":
        return repr(float(node[1]))
    if tag == "species":
        return str(node[1])
    if tag == "mod":
        params = ", ".join(f"{k}={v!r}" for k, v in node[3].items())
        return f"{node[1]}({node[2]}, {params})"
    if tag == "neg":
        return f"-({to_text(node[1])})"
    if tag in ("exp", "log", "sqrt"):
        return f"{tag}({to_text(node[1])})"
    if tag not in _BINARY:
        raise ValueError(f"unknown rate node {tag!r}")
    sym = {"add": "+", "sub": "-", "mul": "*", "div": "/", "pow": "**"}[tag]
    return f"({to_text(node[1])} {sym} {to_text(node[2])})"


def to_json(node: RateNode) -> list:
    """A JSON-able (nested lists) form of the tree."""
    tag = node[0]
    if tag in ("const", "species"):
        return [tag, node[1]]
    if tag == "mod":
        return ["mod", node[1], node[2], dict(node[3])]
    if tag in _UNARY:
        return [tag, to_json(node[1])]
    if tag in _BINARY:
        return [tag, to_json(node[1]), to_json(node[2])]
    raise ValueError(f"unknown rate node {tag!r}")


def _check_tree(node: Any) -> None:
    """Refuse a tuple tree with an unknown tag or the wrong arity, naming it."""
    if not isinstance(node, tuple) or not node:
        raise ValueError(f"not a rate expression: {node!r}")
    tag = node[0]
    if tag in ("const", "species"):
        if len(node) != 2:
            raise ValueError(f"rate node {tag!r} takes one operand: {node!r}")
    elif tag == "mod":
        if len(node) != 4 or node[1] not in MODULATION_KINDS or not isinstance(node[3], Mapping):
            raise ValueError(f"malformed modulation node: {node!r}")
        _check_modulation_params(node[1], node[3])
    elif tag in _UNARY:
        if len(node) != 2:
            raise ValueError(f"rate node {tag!r} takes one operand: {node!r}")
        _check_tree(node[1])
    elif tag in _BINARY:
        if len(node) != 3:
            raise ValueError(f"rate node {tag!r} takes two operands: {node!r}")
        _check_tree(node[1])
        _check_tree(node[2])
    else:
        raise ValueError(f"unknown rate node {tag!r}")


def check_rate_law(node: Any) -> None:
    """Refuse a malformed tree or a modulation no simulator can evaluate the
    same way (see :func:`_check_modulation_params`). ``ReactionSpec`` calls it,
    so both simulators refuse one law with one message at construction."""
    _check_tree(node)


def from_json(data: Any) -> RateNode:
    """The inverse of :func:`to_json`; a tuple tree passes through once its
    tags and arities are checked (a malformed one used to pass unseen and
    fail only when evaluated — module-doc finding, 2026-10)."""
    if isinstance(data, tuple):
        _check_tree(data)
        return data
    if not isinstance(data, list) or not data:
        raise ValueError(f"not a rate expression: {data!r}")
    tag = data[0]
    if tag in ("const", "species"):
        return (tag, data[1])
    if tag == "mod":
        node = ("mod", data[1], data[2], dict(data[3]))
        _check_tree(node)
        return node
    if tag in _UNARY:
        return (tag, from_json(data[1]))
    if tag in _BINARY:
        return (tag, from_json(data[1]), from_json(data[2]))
    raise ValueError(f"unknown rate node {tag!r}")


__all__ = [
    "MODULATION_KINDS",
    "PARITY_TOL",
    "RATE_CAP",
    "ROUNDING_FLOOR",
    "RateNode",
    "check_rate_law",
    "const",
    "eval_rate",
    "from_json",
    "implicit_mass_action",
    "inhibitor_ratio",
    "parity_agrees",
    "snap_residue",
    "snap_residue_jax",
    "lower_jax",
    "map_species",
    "modulation",
    "modulation_factor",
    "species",
    "species_of",
    "to_json",
    "to_text",
]
