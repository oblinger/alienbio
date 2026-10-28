"""Module-doc findings on ``rate_expr``: a power (and the modulation kinds,
and ``exp``) that Python refuses must read on the reference the way JAX reads
it — an infinite rate is ``RATE_CAP`` after the clamps, an undefined one
(NaN, or a complex root of a negative residue) is no reaction.

Repro (before the fix): ``eval_rate`` raised ``ZeroDivisionError`` on
``0.0 ** -1.0`` where ``lower_jax`` gave inf; ``(-1e-13) ** 0.5`` came back
complex and failed later at ``max(0.0, rate)``; a hill modulation with
``n < 0`` at ``[m] = 0`` and an inhibitor with ``Ki = 0`` raised in Python
and read NaN -> 0 under JAX.
"""

from __future__ import annotations

import math

import pytest

from alienbio.bio import rate_expr as rx
from alienbio.bio.compartment_tree import CompartmentTreeImpl
from alienbio.bio.reaction import Modulation
from alienbio.bio.world_simulator import ReactionSpec, WorldSimulatorImpl
from alienbio.bio.world_state import WorldStateImpl


def _pow(a: float, b: float):
    return ("pow", rx.const(a), rx.const(b))


@pytest.mark.parametrize(
    "law, expect",
    [
        (_pow(0.0, -1.0), math.inf),
        (_pow(10.0, 400.0), math.inf),
        (_pow(-10.0, 401.0), -math.inf),
        (("exp", rx.const(1000.0)), math.inf),
        (("mod", "inhibitor", "M", {"Ki": 0.0}), math.nan),
        (("mod", "hill", "M", {"K": 0.5, "n": -2.0}), math.nan),
        (_pow(-1e-13, 0.5), math.nan),
    ],
)
def test_eval_rate_reads_what_ieee_reads(law, expect) -> None:
    got = rx.eval_rate(law, lambda _s: 0.0)
    assert isinstance(got, float)
    if math.isnan(expect):
        assert math.isnan(got)
    else:
        assert got == expect


def _world(m0: float):
    tree = CompartmentTreeImpl()
    tree.add_root("c")
    state = WorldStateImpl(
        tree=tree, num_molecules=3, compartment_ids=["c"], molecule_ids=["A", "B", "M"]
    )
    state.set(0, 0, 1.0)
    state.set(0, 2, m0)
    return tree, state


CASES = [
    # (rate_law over ids, modulators, M's concentration)
    (("mul", rx.const(0.1), _pow(0.0, -1.0)), None, 0.0),       # inf -> RATE_CAP
    (("mul", rx.const(0.1), _pow(-1e-13, 0.5)), None, 0.0),     # complex -> 0
    (("mod", "hill", 2, {"K": 0.5, "n": -2.0}), None, 0.0),      # nan -> 0
    (("mod", "inhibitor", 2, {"Ki": 0.0}), None, 1.0),           # 1/(1+inf) = 0
    (None, {2: Modulation(kind="hill", Vmax=1.0, K=0.5, n=-2.0)}, 0.0),
    (None, {2: Modulation(kind="inhibitor", Ki=0.0)}, 0.0),
    (None, {2: Modulation(kind="inhibitor", Ki=-1.0)}, 1.0),     # 1/(1+m/Ki) = 1/0
]


@pytest.mark.parametrize("law, mods, m0", CASES)
def test_the_reference_steps_and_matches_jax(law, mods, m0) -> None:
    tree, state = _world(m0)
    spec = ReactionSpec(
        name="r", reactants={0: 1.0}, products={1: 1.0}, rate_constant=0.5,
        modulators=mods, rate_law=law,
    )
    ref = WorldSimulatorImpl(
        tree=tree, reactions=[spec], flows=[], num_molecules=3, dt=0.1
    ).step(state)
    for mol in range(3):
        assert math.isfinite(ref.get(0, mol)) and ref.get(0, mol) >= 0.0
    pytest.importorskip("jax")
    from alienbio.bio.jax_simulator import JaxWorldSimulator

    jx = JaxWorldSimulator(tree, [spec], num_molecules=3, dt=0.1).step(state)
    for mol in range(3):
        assert jx.get(0, mol) == pytest.approx(ref.get(0, mol), abs=1e-9)


def test_an_infinite_law_takes_the_whole_pool() -> None:
    tree, state = _world(0.0)
    spec = ReactionSpec(
        name="r", reactants={0: 1.0}, products={1: 1.0},
        rate_law=("mul", rx.const(0.1), _pow(0.0, -1.0)),
    )
    out = WorldSimulatorImpl(
        tree=tree, reactions=[spec], flows=[], num_molecules=3, dt=0.1
    ).step(state)
    assert out.get(0, 0) == 0.0 and out.get(0, 1) == pytest.approx(1.0)
