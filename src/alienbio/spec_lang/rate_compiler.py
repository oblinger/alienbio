"""Rate expression compiler for biological simulations.

Compiles rate expression strings (from !quote / !_ YAML tags) into
efficient callable functions. Constants are baked in at compile time;
substrate/product variables are looked up from state at runtime.

Supported kinetics:
- Constant: ``0.5``, ``k``
- Mass action: ``k * S``, ``k * S1 * S2``
- Michaelis-Menten: ``Vmax * S / (Km + S)``
- Hill equation: ``Vmax * S**n / (K**n + S**n)``
- Reversible: ``kf * S - kr * P``
"""

from __future__ import annotations

import math
from typing import Callable


# Safe math functions available in rate expressions
_RATE_MATH = {
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "pow": pow,
    "abs": abs,
    "max": max,
    "min": min,
}

# Restricted builtins — no imports, exec, eval, etc.
_RATE_BUILTINS: dict[str, object] = {"__builtins__": {}}


def compile_rate_expression(
    source: str,
    constants: dict[str, float],
) -> Callable[[dict[str, float]], float]:
    """Compile a rate expression string into a callable function.

    Constants are baked in at compile time (copied, not referenced).
    Variables (S, S1, S2, P, P1, P2, or molecule names) are looked up
    from the state dict passed at runtime.

    Args:
        source: Rate expression string, e.g. ``"k * S"``
        constants: Named constants to bake in, e.g. ``{"k": 0.1}``

    Returns:
        A function ``(state: dict[str, float]) -> float``
    """
    code = compile(source, "<rate>", "eval")
    baked = {**_RATE_MATH, **dict(constants)}  # copy constants

    def rate_fn(state: dict[str, float]) -> float:
        namespace = {**baked, **state}
        return float(eval(code, _RATE_BUILTINS, namespace))

    return rate_fn
