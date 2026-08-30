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
"""

from __future__ import annotations

import math
from typing import Any, Callable, Hashable, Iterable, Mapping

RateNode = tuple  # see the module docstring

_BINARY = ("add", "sub", "mul", "div", "pow")
_UNARY = ("neg", "exp", "log", "sqrt")
MODULATION_KINDS = ("activator", "inhibitor", "michaelis", "hill")


def const(value: float) -> RateNode:
    return ("const", float(value))


def species(name: Hashable) -> RateNode:
    return ("species", name)


def modulation(kind: str, pool: Hashable, params: Mapping[str, float]) -> RateNode:
    if kind not in MODULATION_KINDS:
        raise ValueError(f"unknown modulation kind {kind!r}")
    return ("mod", kind, pool, {k: float(v) for k, v in params.items()})


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


def modulation_factor(kind: str, m: float, p: Mapping[str, float]) -> float:
    """One modulation's factor at modifier concentration ``m`` — the reference
    simulator's arithmetic, including its zero-denominator conventions."""
    if kind == "activator":
        return 1.0 + p["a"] * m
    if kind == "inhibitor":
        return 1.0 / (1.0 + m / p["Ki"])
    if kind == "michaelis":
        denom = p["K"] + m
        return (p.get("Vmax", 1.0) * m / denom) if denom > 0.0 else 0.0
    if kind == "hill":
        n = p.get("n", 2.0)
        m_n = m**n
        denom = p["K"] ** n + m_n
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
        return math.exp(eval_rate(node[1], conc))
    if tag == "log":
        x = eval_rate(node[1], conc)
        return math.log(x) if x > 0.0 else float("-inf")
    if tag == "sqrt":
        x = eval_rate(node[1], conc)
        return math.sqrt(x) if x > 0.0 else 0.0
    a, b = eval_rate(node[1], conc), eval_rate(node[2], conc)
    if tag == "add":
        return a + b
    if tag == "sub":
        return a - b
    if tag == "mul":
        return a * b
    if tag == "div":
        return a / b if b != 0.0 else 0.0
    if tag == "pow":
        return a**b
    raise ValueError(f"unknown rate node {tag!r}")


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
    a, b = lower_jax(node[1], S, column), lower_jax(node[2], S, column)
    if tag == "add":
        return a + b
    if tag == "sub":
        return a - b
    if tag == "mul":
        return a * b
    if tag == "div":
        return jnp.where(b != 0.0, a / jnp.where(b != 0.0, b, 1.0), 0.0)
    if tag == "pow":
        return a**b
    raise ValueError(f"unknown rate node {tag!r}")


def _lower_modulation(kind: str, m: Any, p: Mapping[str, float], jnp: Any) -> Any:
    if kind == "activator":
        return 1.0 + p["a"] * m
    if kind == "inhibitor":
        return 1.0 / (1.0 + m / p["Ki"])
    if kind == "michaelis":
        denom = p["K"] + m
        return jnp.where(denom > 0.0, p.get("Vmax", 1.0) * m / jnp.where(denom > 0.0, denom, 1.0), 0.0)
    if kind == "hill":
        n = p.get("n", 2.0)
        m_n = m**n
        denom = p["K"] ** n + m_n
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
    return [tag, to_json(node[1]), to_json(node[2])]


def from_json(data: Any) -> RateNode:
    """The inverse of :func:`to_json`; a tuple tree passes through."""
    if isinstance(data, tuple):
        return data
    if not isinstance(data, list) or not data:
        raise ValueError(f"not a rate expression: {data!r}")
    tag = data[0]
    if tag in ("const", "species"):
        return (tag, data[1])
    if tag == "mod":
        return ("mod", data[1], data[2], dict(data[3]))
    if tag in _UNARY:
        return (tag, from_json(data[1]))
    if tag in _BINARY:
        return (tag, from_json(data[1]), from_json(data[2]))
    raise ValueError(f"unknown rate node {tag!r}")


__all__ = [
    "MODULATION_KINDS",
    "RateNode",
    "const",
    "eval_rate",
    "from_json",
    "implicit_mass_action",
    "lower_jax",
    "map_species",
    "modulation",
    "modulation_factor",
    "species",
    "species_of",
    "to_json",
    "to_text",
]
