"""Module-doc findings on ``suite/rate_law.py``: the numeric ``hill`` /
``michaelis`` heads guard on ``denom > 0`` exactly as
``rate_expr.modulation_factor`` (what both simulators run) does.

Repro (before the fix): the heads tested ``if (K or m)``, so
``michaelis(-0.5, 0.5)`` divided by zero and ``michaelis(0.5, -1.0)`` came back
negative where the compiled law reads 0.
"""

from __future__ import annotations

import pytest

from alienbio.bio.rate_expr import modulation_factor
from alienbio.suite.rate_law import hill, michaelis


@pytest.mark.parametrize("m, K", [(-0.5, 0.5), (0.5, -1.0), (0.0, 0.0), (0.3, 0.5)])
def test_michaelis_matches_the_compiled_law(m, K) -> None:
    assert michaelis(m, K, Vmax=2.0) == modulation_factor("michaelis", m, {"K": K, "Vmax": 2.0})


@pytest.mark.parametrize("m, K, n", [(-1.0, 1.0, 1.0), (0.5, -1.0, 1.0), (0.0, 0.0, 2.0), (0.4, 0.5, 2.0)])
def test_hill_matches_the_compiled_law(m, K, n) -> None:
    assert hill(m, K, n=n) == modulation_factor("hill", m, {"K": K, "n": n})
